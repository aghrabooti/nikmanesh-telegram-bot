"""لایه‌ی SQLite: اتصال، اسکیما و مهاجرت‌های سبک برای دیتابیس‌های قدیمی."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seminars (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    date_text        TEXT NOT NULL DEFAULT '',
    starts_at        TEXT NOT NULL DEFAULT '',
    link             TEXT NOT NULL DEFAULT '',
    levels           TEXT NOT NULL DEFAULT '',
    message_template TEXT NOT NULL DEFAULT '',
    is_open          INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registrations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    seminar_id   INTEGER NOT NULL,
    name         TEXT NOT NULL DEFAULT '',
    level        TEXT NOT NULL DEFAULT '',
    city         TEXT NOT NULL DEFAULT '',
    phone        TEXT NOT NULL DEFAULT '',
    alternate_phone TEXT NOT NULL DEFAULT '',
    grade        TEXT NOT NULL DEFAULT '',
    field        TEXT NOT NULL DEFAULT '',
    current_step TEXT NOT NULL DEFAULT 'name',
    is_complete  INTEGER NOT NULL DEFAULT 0,
    link_id      INTEGER,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (user_id, seminar_id)
);

-- لینک‌های رفرال تبلیغاتی (مدیر می‌سازد؛ برچسب = اسم کمپین/کانال)
CREATE TABLE IF NOT EXISTS referral_links (
    link_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL UNIQUE,
    label      TEXT NOT NULL,
    is_active  INTEGER NOT NULL DEFAULT 1,
    phrase     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

-- ادمین‌های کانال: کسانی که با رمز ورود، دسترسی فقط-آماری به یک لینک گرفته‌اند
CREATE TABLE IF NOT EXISTS channel_admins (
    user_id  INTEGER NOT NULL,
    link_id  INTEGER NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (user_id, link_id)
);

-- استارت‌های یکتا (first-touch: هر کاربر فقط یک بار، با اولین لینک)
CREATE TABLE IF NOT EXISTS referral_starts (
    user_id    INTEGER PRIMARY KEY,
    link_id    INTEGER NOT NULL,
    started_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ref_starts_link ON referral_starts (link_id);

CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL DEFAULT '',
    username   TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    last_seen  TEXT NOT NULL
);

-- دفتر ضدتکرار یادآورها: هر یادآور برای هر کاربر/سمینار فقط یک‌بار
CREATE TABLE IF NOT EXISTS reminders (
    user_id    INTEGER NOT NULL,
    seminar_id INTEGER NOT NULL,
    kind       TEXT NOT NULL,
    times      INTEGER NOT NULL DEFAULT 0,
    last_sent  TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, seminar_id, kind)
);

-- تنظیمات سراسری ربات (مثل روشن/خاموش بودن یادآورها)
CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# ستون‌های اضافه‌شده در نسخه‌های جدیدتر (برای دیتابیس‌های موجود قدیمی).
# هر ستون جاافتاده با ALTER TABLE اضافه می‌شود تا دیتابیس قدیمی بدون از دست
# رفتن داده، با اسکیمای جدید کار کند.
_MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "seminars": [
        ("title", "TEXT NOT NULL DEFAULT ''"),
        ("description", "TEXT NOT NULL DEFAULT ''"),
        ("date_text", "TEXT NOT NULL DEFAULT ''"),
        ("starts_at", "TEXT NOT NULL DEFAULT ''"),
        ("link", "TEXT NOT NULL DEFAULT ''"),
        ("levels", "TEXT NOT NULL DEFAULT ''"),
        ("message_template", "TEXT NOT NULL DEFAULT ''"),
        ("is_open", "INTEGER NOT NULL DEFAULT 1"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
        ("updated_at", "TEXT NOT NULL DEFAULT ''"),
    ],
    "users": [
        ("first_name", "TEXT NOT NULL DEFAULT ''"),
        ("username", "TEXT NOT NULL DEFAULT ''"),
        ("started_at", "TEXT NOT NULL DEFAULT ''"),
        ("last_seen", "TEXT NOT NULL DEFAULT ''"),
    ],
    "referral_links": [
        ("code", "TEXT NOT NULL DEFAULT ''"),
        ("label", "TEXT NOT NULL DEFAULT ''"),
        ("is_active", "INTEGER NOT NULL DEFAULT 1"),
        ("phrase", "TEXT NOT NULL DEFAULT ''"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
    ],
    "registrations": [
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("level", "TEXT NOT NULL DEFAULT ''"),
        ("city", "TEXT NOT NULL DEFAULT ''"),
        ("phone", "TEXT NOT NULL DEFAULT ''"),
        ("alternate_phone", "TEXT NOT NULL DEFAULT ''"),
        ("grade", "TEXT NOT NULL DEFAULT ''"),
        ("field", "TEXT NOT NULL DEFAULT ''"),
        ("current_step", "TEXT NOT NULL DEFAULT 'name'"),
        ("is_complete", "INTEGER NOT NULL DEFAULT 0"),
        ("link_id", "INTEGER"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
        ("updated_at", "TEXT NOT NULL DEFAULT ''"),
    ],
}

# CREATE statement های جداگانه — برای بازسازی جدول در مهاجرت
_TABLE_SQL = {
    "users": """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL DEFAULT '',
    username   TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL DEFAULT '',
    last_seen  TEXT NOT NULL DEFAULT ''
)
""",
}

_conn: sqlite3.Connection | None = None


def now_iso() -> str:
    """زمان محلی سرور به فرمت «YYYY-MM-DD HH:MM:SS» — مبنای همه‌ی timestamp ها.

    جداکننده‌ی فاصله (نه T) عمداً انتخاب شده تا مقایسه‌ی رشته‌ای بازه‌های
    تاریخ در SQL درست کار کند.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db(path: str | Path) -> None:
    """اتصال (یا تعویض) دیتابیس و اجرای اسکیما/مهاجرت‌ها."""
    global _conn
    if _conn is not None:
        _conn.close()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(target)
    _conn.row_factory = sqlite3.Row
    _conn.executescript(_SCHEMA)
    _migrate(_conn)
    _backfill_link_phrases(_conn)
    _conn.commit()


def _backfill_link_phrases(conn: sqlite3.Connection) -> None:
    """رمز ورود برای لینک‌های قدیمیِ بی‌رمز تولید می‌کند."""
    import secrets  # noqa: PLC0415

    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    rows = conn.execute(
        "SELECT link_id FROM referral_links WHERE phrase IS NULL OR phrase = ''"
    ).fetchall()
    for row in rows:
        while True:
            phrase = "".join(secrets.choice(alphabet) for _ in range(8))
            dup = conn.execute(
                "SELECT 1 FROM referral_links WHERE phrase = ? AND link_id != ?",
                (phrase, row["link_id"]),
            ).fetchone()
            if dup is None:
                break
        conn.execute(
            "UPDATE referral_links SET phrase = ? WHERE link_id = ?", (phrase, row["link_id"])
        )


def get_db() -> sqlite3.Connection:
    """اتصال جاری؛ پیش از استفاده باید init_db صدا زده شده باشد."""
    if _conn is None:
        raise RuntimeError("init_db() پیش از استفاده صدا زده نشده است")
    return _conn


def close_db() -> None:
    """بستن اتصال (پایان تست/پروسه)."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def get_setting(key: str, default: str = "") -> str:
    """خواندن یک تنظیم از app_settings."""
    row = get_db().execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    """نوشتن یک تنظیم در app_settings."""
    get_db().execute(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    get_db().commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """افزودن ستون‌های جاافتاده به جدول‌های موجود (ALTER TABLE سبک).

    جدول‌هایی که ساختارشان با نسخه‌ی فعلی ناسازگار است (بدون کلیدهای
    اصلی مورد انتظار) از نو ساخته می‌شوند — users فقط کش گیرنده‌های
    همگانی است و registrations ناسازگار یعنی دیتای نسخه‌ی بسیار قدیمی.
    """
    recreate: list[str] = []
    for table, columns in _MIGRATIONS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if table == "registrations" and "alternate_phone" not in existing:
            legacy_column = next(
                (column for column in ("available_phone", "sms_phone") if column in existing),
                None,
            )
            if legacy_column:
                conn.execute(
                    f"ALTER TABLE registrations RENAME COLUMN {legacy_column} TO alternate_phone"
                )
                existing.remove(legacy_column)
                existing.add("alternate_phone")
        keys = {
            "users": ("user_id",),
            "registrations": ("user_id", "seminar_id"),
        }.get(table, ())
        if existing and keys and not all(k in existing for k in keys):
            recreate.append(table)
            continue
        for column, decl in columns:
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    for table in recreate:
        conn.execute(f"DROP TABLE {table}")
        conn.execute(_TABLE_SQL[table])

    # داده‌های دیتابیس‌های میان‌دوره‌ای را به نام نهایی منتقل کن.
    registration_columns = {row["name"] for row in conn.execute("PRAGMA table_info(registrations)")}
    for legacy_column in ("available_phone", "sms_phone"):
        if legacy_column in registration_columns and "alternate_phone" in registration_columns:
            conn.execute(
                f"UPDATE registrations SET alternate_phone = {legacy_column} "
                f"WHERE (alternate_phone IS NULL OR alternate_phone = '') "
                f"AND {legacy_column} IS NOT NULL AND {legacy_column} != ''"
            )
    conn.execute(
        "UPDATE registrations SET current_step = 'alternate_phone' "
        "WHERE current_step IN ('sms', 'available_phone', 'confirm')"
    )
    conn.commit()
