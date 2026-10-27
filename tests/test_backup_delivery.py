"""Nightly database backup delivery to the configured Telegram admins."""

from __future__ import annotations

import gzip
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from bot.services import database_backups
from bot.services.database import close_db, init_db


async def test_daily_backup_is_compressed_sent_to_all_admins_and_deduplicated(tmp_path):
    database_path = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    init_db(database_path)
    close_db()
    bot = SimpleNamespace(send_document=AsyncMock())
    today = datetime.now(ZoneInfo("Asia/Tehran")).date()

    delivered = await database_backups._deliver_backup_date(
        database_path,
        backup_dir,
        bot,
        (777, 888),
        today,
        retention_days=30,
    )

    assert delivered is True
    assert [call.kwargs["chat_id"] for call in bot.send_document.await_args_list] == [777, 888]
    assert all(
        call.kwargs["document"].filename == f"main-{today.isoformat()}.db.gz"
        for call in bot.send_document.await_args_list
    )

    archive = backup_dir / "full" / f"main-{today.isoformat()}.db.gz"
    restored_db = tmp_path / "restored.db"
    with gzip.open(archive, "rb") as compressed, restored_db.open("wb") as restored:
        restored.write(compressed.read())
    with sqlite3.connect(restored_db) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    state = database_backups._load_delivery_state(
        backup_dir / database_backups._DELIVERY_STATE_NAME
    )
    assert state[today.isoformat()] == {777, 888}

    # Restart/re-check on the same Tehran day must not send a duplicate.
    await database_backups._deliver_backup_date(
        database_path,
        backup_dir,
        bot,
        (777, 888),
        today,
        retention_days=30,
    )
    assert bot.send_document.await_count == 2


async def test_failed_admin_delivery_is_retried_without_resending_to_successful_admin(
    tmp_path,
):
    database_path = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    init_db(database_path)
    close_db()
    bot = SimpleNamespace(
        send_document=AsyncMock(side_effect=[None, RuntimeError("temporary Telegram error")])
    )
    today = datetime.now(ZoneInfo("Asia/Tehran")).date()

    delivered = await database_backups._deliver_backup_date(
        database_path,
        backup_dir,
        bot,
        (777, 888),
        today,
        retention_days=30,
    )
    assert delivered is False
    assert [call.kwargs["chat_id"] for call in bot.send_document.await_args_list] == [777, 888]

    bot.send_document = AsyncMock()
    delivered = await database_backups._deliver_backup_date(
        database_path,
        backup_dir,
        bot,
        (777, 888),
        today,
        retention_days=30,
    )
    assert delivered is True
    assert [call.kwargs["chat_id"] for call in bot.send_document.await_args_list] == [888]


def test_next_backup_run_is_tehran_midnight_not_server_midnight():
    just_before_midnight_utc = datetime(2026, 10, 27, 20, 29, tzinfo=timezone.utc)

    next_run = database_backups._next_tehran_midnight(just_before_midnight_utc)

    assert next_run.isoformat() == "2026-10-28T00:00:00+03:30"
