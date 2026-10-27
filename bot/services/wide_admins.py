"""مدیریت نقش ادمین گسترده و دعوت‌های یک‌بارمصرفِ متصل به شناسهٔ تلگرام."""

from __future__ import annotations

import hashlib
import secrets

from bot.services.database import get_db, now_iso

_INVITE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_INVITE_LENGTH = 16


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.strip().lower().encode("utf-8")).hexdigest()


def is_wide_admin(user_id: int) -> bool:
    row = get_db().execute("SELECT 1 FROM wide_admins WHERE user_id = ?", (user_id,)).fetchone()
    return row is not None


def create_invite(target_user_id: int, created_by: int) -> str:
    """ساخت رمز دعوت یکتا و یک‌بارمصرف که فقط برای شناسهٔ هدف معتبر است."""
    if target_user_id <= 0:
        raise ValueError("شناسهٔ تلگرام باید عددی مثبت باشد")
    if is_wide_admin(target_user_id):
        raise ValueError("این کاربر از قبل ادمین گسترده است")

    token = "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(_INVITE_LENGTH))
    db = get_db()
    now = now_iso()
    # دعوت قبلیِ استفاده‌نشده برای همین شناسه بی‌اعتبار می‌شود.
    db.execute(
        "UPDATE wide_admin_invites SET used_at = ? WHERE target_user_id = ? AND used_at = ''",
        (now, target_user_id),
    )
    db.execute(
        """INSERT INTO wide_admin_invites
           (target_user_id, token_hash, created_by, created_at, used_at)
           VALUES (?, ?, ?, ?, '')""",
        (target_user_id, _token_hash(token), created_by, now),
    )
    db.commit()
    return token


def redeem_invite(user_id: int, token: str) -> bool:
    """فعال‌سازی دعوت فقط برای همان شناسه؛ رمز خام پس از مصرف ذخیره نمی‌شود."""
    if user_id <= 0 or not token.strip():
        return False
    db = get_db()
    row = db.execute(
        """SELECT invite_id, created_by FROM wide_admin_invites
           WHERE target_user_id = ? AND token_hash = ? AND used_at = ''""",
        (user_id, _token_hash(token)),
    ).fetchone()
    if row is None:
        return False

    now = now_iso()
    claimed = db.execute(
        "UPDATE wide_admin_invites SET used_at = ? WHERE invite_id = ? AND used_at = ''",
        (now, row["invite_id"]),
    )
    if claimed.rowcount != 1:
        db.rollback()
        return False
    db.execute(
        "INSERT OR IGNORE INTO wide_admins (user_id, created_by, created_at) VALUES (?, ?, ?)",
        (user_id, row["created_by"], now),
    )
    db.commit()
    return True


def list_wide_admins() -> list[dict]:
    rows = (
        get_db()
        .execute(
            """SELECT wa.user_id, wa.created_by, wa.created_at,
                  COALESCE(u.first_name, '') AS first_name,
                  COALESCE(u.username, '') AS username
           FROM wide_admins AS wa
           LEFT JOIN users AS u ON u.user_id = wa.user_id
           ORDER BY wa.created_at, wa.user_id"""
        )
        .fetchall()
    )
    return [dict(row) for row in rows]


def revoke_wide_admin(user_id: int) -> bool:
    """لغو نقش و بی‌اعتبارکردن دعوت‌های استفاده‌نشدهٔ همان شناسه."""
    db = get_db()
    db.execute(
        "UPDATE wide_admin_invites SET used_at = ? WHERE target_user_id = ? AND used_at = ''",
        (now_iso(), user_id),
    )
    cursor = db.execute("DELETE FROM wide_admins WHERE user_id = ?", (user_id,))
    db.commit()
    return cursor.rowcount > 0
