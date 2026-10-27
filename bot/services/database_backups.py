"""Automatic SQLite snapshots for started users, phone registrations and seminars.

The source database remains authoritative. This service refreshes small, separate
SQLite mirrors periodically and writes one full SQLite backup per day. Seminar
mirrors contain every registration row, including partial and complete ones.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None

_USERS_SCHEMA = """
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    last_seen TEXT NOT NULL
)
"""

_PHONE_USERS_SCHEMA = """
CREATE TABLE users_with_phone (
    user_id INTEGER NOT NULL,
    seminar_id INTEGER NOT NULL,
    first_name TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    grade TEXT NOT NULL DEFAULT '',
    field TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    telegram_phone TEXT NOT NULL DEFAULT '',
    alternate_phone TEXT NOT NULL DEFAULT '',
    current_step TEXT NOT NULL DEFAULT '',
    is_complete INTEGER NOT NULL DEFAULT 0,
    link_id INTEGER,
    seminar_title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, seminar_id)
)
"""

_SEMINAR_SCHEMA = """
CREATE TABLE seminar (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    date_text TEXT NOT NULL DEFAULT '',
    starts_at TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    levels TEXT NOT NULL DEFAULT '',
    message_template TEXT NOT NULL DEFAULT '',
    is_open INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE registrations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    seminar_id INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    alternate_phone TEXT NOT NULL DEFAULT '',
    grade TEXT NOT NULL DEFAULT '',
    field TEXT NOT NULL DEFAULT '',
    current_step TEXT NOT NULL DEFAULT 'name',
    is_complete INTEGER NOT NULL DEFAULT 0,
    link_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'نیمه‌کاره',
    UNIQUE (user_id, seminar_id)
);
CREATE INDEX idx_registrations_complete ON registrations (is_complete);
"""


def _secure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:
        logger.warning("Could not restrict backup directory permissions: %s", path)


def _secure_file(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        logger.warning("Could not restrict backup file permissions: %s", path)


def _atomic_sqlite(path: Path, build: Callable[[sqlite3.Connection], None]) -> None:
    """Build a standalone SQLite file beside its destination, then atomically replace it."""
    _secure_directory(path.parent)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        target = sqlite3.connect(temp_path)
        try:
            target.execute("PRAGMA journal_mode=DELETE")
            build(target)
            target.commit()
            integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise sqlite3.DatabaseError(f"Backup integrity check failed: {integrity}")
        finally:
            target.close()
        _secure_file(temp_path)
        os.replace(temp_path, path)
        _secure_file(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _rows(source: sqlite3.Connection, query: str, params: tuple = ()) -> list[sqlite3.Row]:
    return source.execute(query, params).fetchall()


def _refresh_started_users(source: sqlite3.Connection, path: Path) -> int:
    users = _rows(
        source,
        "SELECT user_id, first_name, username, started_at, last_seen "
        "FROM users ORDER BY started_at, user_id",
    )

    def build(target: sqlite3.Connection) -> None:
        target.execute(_USERS_SCHEMA)
        target.executemany(
            "INSERT INTO users (user_id, first_name, username, started_at, last_seen) "
            "VALUES (?, ?, ?, ?, ?)",
            [tuple(row) for row in users],
        )
        target.execute("CREATE TABLE snapshot_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        target.execute(
            "INSERT INTO snapshot_metadata VALUES ('refreshed_at', ?)",
            (datetime.now().isoformat(timespec="seconds"),),
        )

    _atomic_sqlite(path, build)
    return len(users)


def _refresh_users_with_phone(source: sqlite3.Connection, path: Path) -> int:
    rows = _rows(
        source,
        """SELECT
               r.user_id, r.seminar_id,
               COALESCE(u.first_name, '') AS first_name,
               COALESCE(u.username, '') AS username,
               r.name, r.grade, r.field, r.city,
               r.phone AS telegram_phone,
               r.alternate_phone,
               r.current_step, r.is_complete, r.link_id,
               COALESCE(s.title, '') AS seminar_title,
               r.created_at, r.updated_at
           FROM registrations AS r
           LEFT JOIN users AS u ON u.user_id = r.user_id
           LEFT JOIN seminars AS s ON s.id = r.seminar_id
           WHERE COALESCE(r.phone, '') != '' OR COALESCE(r.alternate_phone, '') != ''
           ORDER BY r.created_at, r.seminar_id, r.user_id""",
    )

    def build(target: sqlite3.Connection) -> None:
        target.execute(_PHONE_USERS_SCHEMA)
        target.executemany(
            """INSERT INTO users_with_phone (
                   user_id, seminar_id, first_name, username, name, grade, field, city,
                   telegram_phone, alternate_phone, current_step, is_complete, link_id,
                   seminar_title, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [tuple(row) for row in rows],
        )
        target.execute("CREATE TABLE snapshot_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        target.execute(
            "INSERT INTO snapshot_metadata VALUES ('refreshed_at', ?)",
            (datetime.now().isoformat(timespec="seconds"),),
        )

    _atomic_sqlite(path, build)
    return len(rows)


def _refresh_seminar(
    source: sqlite3.Connection, seminar: sqlite3.Row, path: Path
) -> tuple[int, int]:
    seminar_id = int(seminar["id"])
    registrations = _rows(
        source,
        """SELECT rowid AS id, user_id, seminar_id, name, level, city, phone, alternate_phone,
                  grade, field, current_step, is_complete, link_id, created_at, updated_at
           FROM registrations WHERE seminar_id = ? ORDER BY created_at, rowid""",
        (seminar_id,),
    )

    def build(target: sqlite3.Connection) -> None:
        target.executescript(_SEMINAR_SCHEMA)
        target.execute(
            """INSERT INTO seminar (
                   id, title, description, date_text, starts_at, link, levels,
                   message_template, is_open, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(
                seminar[key]
                for key in (
                    "id",
                    "title",
                    "description",
                    "date_text",
                    "starts_at",
                    "link",
                    "levels",
                    "message_template",
                    "is_open",
                    "created_at",
                    "updated_at",
                )
            ),
        )
        target.executemany(
            """INSERT INTO registrations (
                   id, user_id, seminar_id, name, level, city, phone, alternate_phone,
                   grade, field, current_step, is_complete, link_id, created_at, updated_at,
                   status
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(*tuple(row), "کامل" if row["is_complete"] else "نیمه‌کاره") for row in registrations],
        )
        target.execute("CREATE TABLE snapshot_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        target.executemany(
            "INSERT INTO snapshot_metadata VALUES (?, ?)",
            [
                ("refreshed_at", datetime.now().isoformat(timespec="seconds")),
                ("registration_count", str(len(registrations))),
                ("complete_count", str(sum(int(row["is_complete"]) for row in registrations))),
            ],
        )

    _atomic_sqlite(path, build)
    complete = sum(int(row["is_complete"]) for row in registrations)
    return len(registrations), complete


def _refresh_full_backup(database_path: Path, path: Path) -> None:
    """Use sqlite3's online backup API so a live source database is copied consistently."""
    _secure_directory(path.parent)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    source = sqlite3.connect(database_path, timeout=30)
    target = sqlite3.connect(temp_path)
    try:
        source.backup(target)
        target.commit()
        integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise sqlite3.DatabaseError(f"Full backup integrity check failed: {integrity}")
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        target.close()
        source.close()
    _secure_file(temp_path)
    os.replace(temp_path, path)
    _secure_file(path)


def _prune_full_backups(full_dir: Path, retention_days: int, now: datetime) -> None:
    cutoff = now.timestamp() - retention_days * 24 * 60 * 60
    for path in full_dir.glob("main-*.db"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            logger.exception("Failed to prune old full database backup: %s", path)


def create_backups(
    database_path: str | Path,
    backup_dir: str | Path,
    *,
    retention_days: int = 30,
    now: datetime | None = None,
) -> dict[str, int]:
    """Refresh mirror databases and the current daily full backup.

    ``users_with_phone.db`` is one row per user/seminar registration with either
    phone populated. ``seminars/seminar-<id>.db`` includes every registration,
    and exposes both ``is_complete`` and a Persian ``status`` column.
    """
    source_path = Path(database_path)
    root = Path(backup_dir)
    if not source_path.is_file():
        raise FileNotFoundError(f"Main database does not exist: {source_path}")
    _secure_directory(root)
    current = now or datetime.now()
    reports: dict[str, int] = {}

    source = sqlite3.connect(source_path, timeout=30)
    source.row_factory = sqlite3.Row
    try:
        reports["users_started"] = _refresh_started_users(source, root / "users-started.db")
        reports["users_with_phone"] = _refresh_users_with_phone(
            source, root / "users-with-phone.db"
        )
        seminars_dir = root / "seminars"
        _secure_directory(seminars_dir)
        seminar_rows = _rows(source, "SELECT * FROM seminars ORDER BY id")
        for seminar in seminar_rows:
            total, complete = _refresh_seminar(
                source, seminar, seminars_dir / f"seminar-{int(seminar['id'])}.db"
            )
            reports[f"seminar_{int(seminar['id'])}_total"] = total
            reports[f"seminar_{int(seminar['id'])}_complete"] = complete
    finally:
        source.close()

    full_dir = root / "full"
    _secure_directory(full_dir)
    _refresh_full_backup(source_path, full_dir / f"main-{current:%Y-%m-%d}.db")
    _prune_full_backups(full_dir, max(1, retention_days), current)
    logger.info("Automatic database snapshots refreshed: %s", reports)
    return reports


async def _run_task(
    database_path: Path, backup_dir: Path, interval_minutes: int, retention_days: int
) -> None:
    while True:
        try:
            await asyncio.to_thread(
                create_backups,
                database_path,
                backup_dir,
                retention_days=retention_days,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automatic database backup failed")
        await asyncio.sleep(max(1, interval_minutes) * 60)


def ensure_task(
    database_path: str | Path,
    backup_dir: str | Path,
    *,
    interval_minutes: int = 15,
    retention_days: int = 30,
) -> bool:
    """Start immediate and periodic snapshots once per process/event loop."""
    global _task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    if _task is None or _task.done():
        _task = loop.create_task(
            _run_task(
                Path(database_path),
                Path(backup_dir),
                max(1, interval_minutes),
                max(1, retention_days),
            )
        )
        return True
    return False


async def cancel_task() -> None:
    """Stop the periodic backup worker cleanly during shutdown."""
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
