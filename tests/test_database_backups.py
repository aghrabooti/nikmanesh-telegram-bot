"""پشتیبان‌گیری خودکار: کاربران شروع‌کننده، شماره‌دارها و دیتابیس هر سمینار."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta

from bot.services import database_backups, seminars, users
from bot.services.database import close_db, get_db, init_db


def test_create_backups_keeps_started_users_and_phone_records(tmp_path):
    database_path = tmp_path / "source" / "seminar.db"
    backup_dir = tmp_path / "backups"
    init_db(database_path)
    try:
        seminar = seminars.create_seminar(title="سمینار پشتیبان", link="https://t.me/room")
        users.ensure_user(101, first_name="ناتمام", username="partial")
        users.ensure_user(202, first_name="کامل", username="complete")

        # شماره دارد ولی فرم را کامل نکرده است: باید در هر دو مجموعه حفظ شود.
        seminars.ensure_registration(101, seminar["id"])
        seminars.save_registration(
            101,
            seminar["id"],
            next_step=seminars.STEP_ALTERNATE_PHONE,
            name="ناتمام",
            phone="+989111111111",
        )

        seminars.ensure_registration(202, seminar["id"])
        seminars.save_registration(
            202,
            seminar["id"],
            next_step=seminars.STEP_ALTERNATE_PHONE,
            name="کامل",
            phone="+989122222222",
            alternate_phone="09122222222",
        )
        seminars.complete_registration(202, seminar["id"])

        backup_now = datetime(2026, 10, 27, 12, 0)
        old_full = backup_dir / "full" / "main-2026-09-01.db"
        old_full.parent.mkdir(parents=True)
        old_full.write_bytes(b"old snapshot")
        old_time = (backup_now - timedelta(days=31)).timestamp()
        os.utime(old_full, (old_time, old_time))

        report = database_backups.create_backups(
            database_path,
            backup_dir,
            now=backup_now,
        )

        assert report["users_started"] == 2
        assert report["users_with_phone"] == 2
        assert report[f"seminar_{seminar['id']}_total"] == 2
        assert report[f"seminar_{seminar['id']}_complete"] == 1

        with sqlite3.connect(backup_dir / "users-started.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2

        with sqlite3.connect(backup_dir / "users-with-phone.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM users_with_phone").fetchone()[0] == 2
            states = conn.execute(
                "SELECT user_id, is_complete FROM users_with_phone ORDER BY user_id"
            ).fetchall()
            assert states == [(101, 0), (202, 1)]

        seminar_backup = backup_dir / "seminars" / f"seminar-{seminar['id']}.db"
        with sqlite3.connect(seminar_backup) as conn:
            assert conn.execute("SELECT title FROM seminar").fetchone()[0] == "سمینار پشتیبان"
            assert conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] == 2
            assert (
                conn.execute("SELECT COUNT(*) FROM registrations WHERE status = 'کامل'").fetchone()[
                    0
                ]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM registrations WHERE status = 'نیمه‌کاره'"
                ).fetchone()[0]
                == 1
            )

        full_backup = backup_dir / "full" / "main-2026-10-27.db"
        assert full_backup.is_file()
        assert not old_full.exists()
        with sqlite3.connect(full_backup) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] == 2
    finally:
        close_db()


def test_previous_phone_column_migrates_to_alternate_name(tmp_path):
    database_path = tmp_path / "previous.db"
    conn = sqlite3.connect(database_path)
    conn.execute(
        """CREATE TABLE registrations (
               user_id INTEGER NOT NULL,
               seminar_id INTEGER NOT NULL,
               name TEXT NOT NULL DEFAULT '',
               phone TEXT NOT NULL DEFAULT '',
               available_phone TEXT NOT NULL DEFAULT '',
               current_step TEXT NOT NULL DEFAULT 'name',
               is_complete INTEGER NOT NULL DEFAULT 0,
               created_at TEXT NOT NULL DEFAULT '',
               updated_at TEXT NOT NULL DEFAULT '',
               UNIQUE(user_id, seminar_id)
           )"""
    )
    conn.execute(
        """INSERT INTO registrations
           (user_id, seminar_id, name, available_phone, current_step, created_at, updated_at)
           VALUES (66, 8, 'کاربر قبلی', '09112223344', 'available_phone',
                   '2026-10-01', '2026-10-01')"""
    )
    conn.commit()
    conn.close()

    init_db(database_path)
    try:
        reg = seminars.get_registration(66, 8)
        assert reg["alternate_phone"] == "09112223344"
        assert reg["current_step"] == seminars.STEP_ALTERNATE_PHONE
        columns = {row["name"] for row in get_db().execute("PRAGMA table_info(registrations)")}
        assert "alternate_phone" in columns and "available_phone" not in columns
    finally:
        close_db()


def test_legacy_phone_column_migrates_and_resumes(tmp_path):
    database_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(database_path)
    conn.execute(
        """CREATE TABLE registrations (
               user_id INTEGER NOT NULL,
               seminar_id INTEGER NOT NULL,
               name TEXT NOT NULL DEFAULT '',
               phone TEXT NOT NULL DEFAULT '',
               sms_phone TEXT NOT NULL DEFAULT '',
               current_step TEXT NOT NULL DEFAULT 'name',
               is_complete INTEGER NOT NULL DEFAULT 0,
               created_at TEXT NOT NULL DEFAULT '',
               updated_at TEXT NOT NULL DEFAULT '',
               UNIQUE(user_id, seminar_id)
           )"""
    )
    conn.execute(
        """INSERT INTO registrations
           (user_id, seminar_id, name, phone, sms_phone, current_step, created_at, updated_at)
           VALUES (55, 7, 'کاربر قدیمی', '+989111111111', '09112223333', 'sms', '2026-10-01',
                   '2026-10-01')"""
    )
    conn.commit()
    conn.close()

    init_db(database_path)
    try:
        reg = seminars.get_registration(55, 7)
        assert reg["alternate_phone"] == "09112223333"
        assert reg["current_step"] == seminars.STEP_ALTERNATE_PHONE
        columns = {row["name"] for row in get_db().execute("PRAGMA table_info(registrations)")}
        assert "alternate_phone" in columns and "sms_phone" not in columns
    finally:
        close_db()
