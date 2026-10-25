"""سرویس کاربران — هر که ربات را استارت کرده (برای پیام همگانی)."""

from __future__ import annotations

from bot.services.database import get_db, now_iso


def ensure_user(user_id: int, *, first_name: str = "", username: str = "") -> None:
    """ثبت/به‌روزرسانی کاربر هنگام استارت."""
    now = now_iso()
    get_db().execute(
        """INSERT INTO users (user_id, first_name, username, started_at, last_seen)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
               first_name = excluded.first_name,
               username = excluded.username,
               last_seen = excluded.last_seen""",
        (user_id, first_name or "", username or "", now, now),
    )
    get_db().commit()


def get_user(user_id: int) -> dict | None:
    """کاربر استارت‌کرنده بر اساس شناسه (برای نمایش نام در پنل)."""
    row = get_db().execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def count_users() -> int:
    """شمار همه‌ی کاربرانی که ربات را استارت کرده‌اند."""
    row = get_db().execute("SELECT COUNT(*) AS n FROM users").fetchone()
    return row["n"]


def all_user_ids() -> list[int]:
    """شناسه‌ی همه‌ی کاربران — گیرنده‌های پیام همگانی."""
    return [row["user_id"] for row in get_db().execute("SELECT user_id FROM users")]
