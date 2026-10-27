"""اتصال کارگر پشتیبان‌گیری به چرخه‌ی polling و webhook."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


async def test_polling_lifecycle_starts_and_stops_backups(monkeypatch, tmp_path):
    from bot import main

    monkeypatch.setenv("BOT_TOKEN", "123456:TEST-TOKEN")
    monkeypatch.setenv("ADMIN_IDS", "777")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "source.db"))
    monkeypatch.setattr(main, "_setup_commands", AsyncMock())
    monkeypatch.setattr(main.reminders, "ensure_task", Mock())
    monkeypatch.setattr(main.sender, "ensure_worker", Mock())
    start_backup = Mock()
    stop_backup = AsyncMock()
    monkeypatch.setattr(main.database_backups, "ensure_task", start_backup)
    monkeypatch.setattr(main.database_backups, "cancel_task", stop_backup)
    monkeypatch.setattr(main.reminders, "cancel_task", AsyncMock())
    monkeypatch.setattr(main.sender, "cancel_worker", AsyncMock())

    await main._on_startup(None)
    start_backup.assert_called_once_with(
        tmp_path / "source.db",
        tmp_path / "backups",
        interval_minutes=15,
        retention_days=30,
    )
    await main._on_shutdown(None)
    stop_backup.assert_awaited_once()


async def test_webhook_lifecycle_starts_and_stops_backups(monkeypatch, tmp_path):
    from bot import webhook
    from bot.services import database_backups, reminders, sender

    started = asyncio.Event()

    async def start_webhook(**_kwargs):
        started.set()

    app = SimpleNamespace(
        initialize=AsyncMock(),
        start=AsyncMock(),
        updater=SimpleNamespace(start_webhook=start_webhook, stop=AsyncMock()),
        stop=AsyncMock(),
        shutdown=AsyncMock(),
    )
    settings = SimpleNamespace(
        database_path=tmp_path / "source.db",
        database_backup_dir=tmp_path / "backups",
        database_backup_interval_minutes=7,
        database_backup_retention_days=12,
        bot_token="123456:TEST-TOKEN",
        webhook_port=8443,
        webhook_url="https://example.test/hook",
    )
    start_backup = Mock()
    stop_backup = AsyncMock()
    monkeypatch.setattr(database_backups, "ensure_task", start_backup)
    monkeypatch.setattr(database_backups, "cancel_task", stop_backup)
    monkeypatch.setattr(reminders, "ensure_task", Mock())
    monkeypatch.setattr(reminders, "cancel_task", AsyncMock())
    monkeypatch.setattr(sender, "ensure_worker", Mock())
    monkeypatch.setattr(sender, "cancel_worker", AsyncMock())

    task = asyncio.create_task(webhook._serve(app, settings))
    await asyncio.wait_for(started.wait(), timeout=2)
    start_backup.assert_called_once_with(
        settings.database_path,
        settings.database_backup_dir,
        interval_minutes=7,
        retention_days=12,
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    stop_backup.assert_awaited_once()
    app.updater.stop.assert_awaited_once()
    app.stop.assert_awaited_once()
    app.shutdown.assert_awaited_once()
