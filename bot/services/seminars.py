"""سرویس سمینارها و ثبت‌نام‌ها — تنها لایه‌ای که SQL سمینار می‌نویسد."""

from __future__ import annotations

from datetime import date, datetime

from bot.config import content
from bot.services.database import get_db, now_iso

# مراحل ویزارد ثبت‌نام (ترتیب مهم است):
# نام ← پایه ← رشته ← شهر ← شماره تلگرام ← شماره جایگزین ← پایان
STEP_NAME = "name"
STEP_GRADE = "grade"
STEP_FIELD = "field"
STEP_CITY = "city"
STEP_PHONE = "phone"
STEP_ALTERNATE_PHONE = "alternate_phone"
STEP_DONE = "done"

STEP_ORDER = (STEP_NAME, STEP_GRADE, STEP_FIELD, STEP_CITY, STEP_PHONE, STEP_ALTERNATE_PHONE)

# مراحل نسخه‌های قدیمی ↔ معادل جدید
LEGACY_STEP_MAP = {
    "level": STEP_GRADE,
    "confirm": STEP_ALTERNATE_PHONE,
    "sms": STEP_ALTERNATE_PHONE,
    "available_phone": STEP_ALTERNATE_PHONE,
}

# نام فیلد ادمین ↔ ستون دیتابیس
_FIELD_COLS = {"date": "date_text"}


def _row(r) -> dict:
    return dict(r) if r is not None else None


# ── سمینارها ──────────────────────────────────────────────────────────────


def create_seminar(
    *,
    title: str,
    description: str = "",
    date_text: str = "",
    starts_at: str = "",
    link: str = "",
    levels: list[str] | None = None,
    message_template: str = "",
    is_open: bool = True,
) -> dict:
    """ساخت سمینار جدید؛ starts_at به فرمت ISO، levels لیست گروه‌هاست."""
    now = now_iso()
    get_db().execute(
        """INSERT INTO seminars
           (title, description, date_text, starts_at, link, levels,
            message_template, is_open, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title.strip(),
            description.strip(),
            date_text.strip(),
            starts_at.strip(),
            link.strip(),
            ",".join(levels or []),
            message_template.strip(),
            int(is_open),
            now,
            now,
        ),
    )
    get_db().commit()
    return get_seminar(_last_id())


def _last_id() -> int:
    return get_db().execute("SELECT last_insert_rowid() AS id").fetchone()["id"]


def list_seminars(*, open_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM seminars"
    if open_only:
        sql += " WHERE is_open = 1"
    sql += " ORDER BY id"
    return [_row(r) for r in get_db().execute(sql)]


def list_with_counts(*, open_only: bool = False) -> list[dict]:
    """سمینارها + آمار ثبت‌نام هر کدام (reg_total / reg_done) — برای پنل."""
    sql = (
        "SELECT s.*, COUNT(r.user_id) AS reg_total, "
        "COALESCE(SUM(r.is_complete), 0) AS reg_done "
        "FROM seminars s LEFT JOIN registrations r ON r.seminar_id = s.id"
    )
    if open_only:
        sql += " WHERE s.is_open = 1"
    sql += " GROUP BY s.id ORDER BY s.id"
    return [_row(r) for r in get_db().execute(sql)]


def active_seminar() -> dict | None:
    """وبینار فعال فعلی: جدیدترین سمینار باز (هدف دکمه‌ی ثابت کاربر)."""
    r = (
        get_db()
        .execute("SELECT * FROM seminars WHERE is_open = 1 ORDER BY id DESC LIMIT 1")
        .fetchone()
    )
    return _row(r)


def get_seminar(seminar_id: int) -> dict | None:
    r = get_db().execute("SELECT * FROM seminars WHERE id = ?", (seminar_id,)).fetchone()
    return _row(r)


def update_seminar(seminar_id: int, **fields) -> None:
    """به‌روزرسانی فیلدهای مجاز سمینار."""
    cols, vals = [], []
    for key, value in fields.items():
        cols.append(f"{_FIELD_COLS.get(key, key)} = ?")
        vals.append(value)
    if not cols:
        return
    vals.extend([now_iso(), seminar_id])
    get_db().execute(f"UPDATE seminars SET {', '.join(cols)}, updated_at = ? WHERE id = ?", vals)
    get_db().commit()


def delete_seminar(seminar_id: int) -> None:
    """حذف سمینار به‌همراه ثبت‌نام‌ها و یادآورهای آن."""
    conn = get_db()
    conn.execute("DELETE FROM registrations WHERE seminar_id = ?", (seminar_id,))
    conn.execute("DELETE FROM reminders WHERE seminar_id = ?", (seminar_id,))
    conn.execute("DELETE FROM seminars WHERE id = ?", (seminar_id,))
    conn.commit()


def set_seminar_open(seminar_id: int, is_open: bool) -> None:
    update_seminar(seminar_id, is_open=int(is_open))


def split_levels(seminar: dict) -> list[str]:
    """گروه‌های سمینار به‌صورت لیست."""
    return [x for x in (seminar["levels"] or "").split(",") if x]


# ── زمان شروع ─────────────────────────────────────────────────────────────


def starts_at_dt(seminar: dict) -> datetime | None:
    """زمان شروع به‌صورت datetime محلی؛ نامشخص → None."""
    raw = seminar.get("starts_at") or ""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def parse_starts_at_text(text: str) -> str | None:
    """متن شمسی/میلادی → ISO؛ نامعتبر → None («-»/«هیچ» را هندلر هندل می‌کند)."""
    from bot.utils.dates import parse_datetime_text  # noqa: PLC0415

    parsed = parse_datetime_text(text)
    return parsed.isoformat(timespec="seconds") if parsed else None


def format_starts_at(seminar: dict) -> str:
    """نمایش فارسی زمان شروع: «۱۴۰۵/۰۸/۱۵ ساعت ۱۸:۰۰»."""
    from bot.utils.jalali import format_jalali  # noqa: PLC0415
    from bot.utils.persian import to_fa  # noqa: PLC0415

    dt = starts_at_dt(seminar)
    if dt is None:
        return ""
    return f"{to_fa(format_jalali(dt.date()))} ساعت {to_fa(dt.strftime('%H:%M'))}"


# ── ثبت‌نام‌ها ────────────────────────────────────────────────────────────


def get_registration(user_id: int, seminar_id: int) -> dict | None:
    r = (
        get_db()
        .execute(
            "SELECT * FROM registrations WHERE user_id = ? AND seminar_id = ?",
            (user_id, seminar_id),
        )
        .fetchone()
    )
    return _row(r)


def ensure_registration(user_id: int, seminar_id: int) -> dict:
    """ثبت‌نام را می‌سازد (اگر نباشد) و برمی‌گرداند.

    سطر تازه، لینک رفرالی را که کاربر با آن آمده (first-touch) می‌گیرد.
    """
    from bot.services import referrals  # noqa: PLC0415 — وابستگی چرخه‌ای در سطح ماژول

    now = now_iso()
    get_db().execute(
        """INSERT OR IGNORE INTO registrations
           (user_id, seminar_id, current_step, link_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, seminar_id, STEP_NAME, referrals.attributed_link_id(user_id), now, now),
    )
    get_db().commit()
    return get_registration(user_id, seminar_id)


def save_registration(user_id: int, seminar_id: int, *, next_step: str, **fields) -> None:
    """ذخیره‌ی فیلدهای ویزارد و رفتن به مرحله‌ی بعد."""
    cols = ["current_step = ?", "updated_at = ?"]
    vals: list = [next_step, now_iso()]
    for key, value in fields.items():
        cols.append(f"{key} = ?")
        vals.append(value)
    vals.extend([user_id, seminar_id])
    get_db().execute(
        f"UPDATE registrations SET {', '.join(cols)} WHERE user_id = ? AND seminar_id = ?",
        vals,
    )
    get_db().commit()


def complete_registration(user_id: int, seminar_id: int) -> None:
    get_db().execute(
        "UPDATE registrations SET is_complete = 1, current_step = ?, updated_at = ? "
        "WHERE user_id = ? AND seminar_id = ?",
        (STEP_DONE, now_iso(), user_id, seminar_id),
    )
    get_db().commit()


def _range_conds(since: date | None, until: date | None) -> tuple[str, list]:
    """شرط‌های SQL بازه‌ی تاریخ ثبت (با پیشوند « AND » — به WHERE موجود می‌چسبند)."""
    conds, params = [], []
    if since is not None:
        conds.append("created_at >= ?")
        params.append(f"{since.isoformat()} 00:00:00")
    if until is not None:
        conds.append("created_at <= ?")
        params.append(f"{until.isoformat()} 23:59:59")
    return (f" AND {' AND '.join(conds)}" if conds else ""), params


def list_registrations(
    seminar_id: int,
    *,
    since: date | None = None,
    until: date | None = None,
    completed_only: bool = False,
) -> list[dict]:
    conds, params = _range_conds(since, until)
    if completed_only:
        conds += " AND is_complete = 1"
    # rowid به‌جای id — در دیتابیس‌های قدیمیِ بدون ستون id هم کار می‌کند
    sql = f"SELECT * FROM registrations WHERE seminar_id = ?{conds} ORDER BY created_at, rowid"
    return [_row(r) for r in get_db().execute(sql, [seminar_id, *params])]


def count_registrations(
    seminar_id: int, *, since: date | None = None, until: date | None = None
) -> tuple[int, int]:
    """(کل، کامل) در بازه‌ی داده‌شده."""
    conds, params = _range_conds(since, until)
    row = (
        get_db()
        .execute(
            f"SELECT COUNT(*) AS total, COALESCE(SUM(is_complete), 0) AS done "
            f"FROM registrations WHERE seminar_id = ?{conds}",
            [seminar_id, *params],
        )
        .fetchone()
    )
    return row["total"], row["done"]


def _registration_datetime_conds(
    since: datetime | None, until_exclusive: datetime | None
) -> tuple[str, list[str]]:
    """شرط‌های بازهٔ تاریخ/ساعت برای زمان شروع ثبت‌نام."""
    conds, params = [], []
    if since is not None:
        conds.append("r.created_at >= ?")
        params.append(since.strftime("%Y-%m-%d %H:%M:%S"))
    if until_exclusive is not None:
        conds.append("r.created_at < ?")
        params.append(until_exclusive.strftime("%Y-%m-%d %H:%M:%S"))
    return (f" AND {' AND '.join(conds)}" if conds else ""), params


def _registration_export_rows(
    *,
    since: datetime | None,
    until_exclusive: datetime | None,
    phone_required: bool,
) -> list[dict]:
    conds, params = _registration_datetime_conds(since, until_exclusive)
    phone_filter = " AND TRIM(COALESCE(r.phone, '')) != ''" if phone_required else ""
    rows = (
        get_db()
        .execute(
            """SELECT r.rowid AS registration_rowid, r.*,
                  COALESCE(s.title, '') AS seminar_title,
                  COALESCE(u.first_name, '') AS telegram_first_name,
                  COALESCE(u.username, '') AS telegram_username
           FROM registrations AS r
           LEFT JOIN seminars AS s ON s.id = r.seminar_id
           LEFT JOIN users AS u ON u.user_id = r.user_id
           WHERE 1 = 1"""
            + phone_filter
            + conds
            + " ORDER BY r.created_at, r.rowid",
            params,
        )
        .fetchall()
    )
    return [dict(row) for row in rows]


def list_contact_leads(
    *, since: datetime | None = None, until_exclusive: datetime | None = None
) -> list[dict]:
    """لیدهای دارای شماره، یک ردیف برای هر شناسهٔ تلگرام.

    اگر یک کاربر در بازهٔ انتخابی چند سمینار داشته باشد، تازه‌ترین ثبت‌نام
    دارای شماره برای او نگه داشته می‌شود. فیلتر زمانی بر اساس شروع فرم است.
    """
    rows = _registration_export_rows(
        since=since, until_exclusive=until_exclusive, phone_required=True
    )
    latest_by_user: dict[int, dict] = {}
    for row in rows:
        latest_by_user[int(row["user_id"])] = row
    return sorted(
        latest_by_user.values(),
        key=lambda row: (row["created_at"], int(row["user_id"])),
    )


def list_registration_starts(
    *, since: datetime | None = None, until_exclusive: datetime | None = None
) -> list[dict]:
    """همهٔ شروع‌های فرم ثبت‌نام، حتی موارد نیمه‌کاره و بدون شماره."""
    return _registration_export_rows(
        since=since, until_exclusive=until_exclusive, phone_required=False
    )


def funnel_counts(seminar_id: int) -> dict[str, int]:
    """شمارش رسیدن به هر مرحله (برای قیف آماری)."""
    order = list(STEP_ORDER)
    rows = (
        get_db()
        .execute(
            "SELECT current_step, is_complete, COUNT(*) AS n FROM registrations "
            "WHERE seminar_id = ? GROUP BY current_step, is_complete",
            (seminar_id,),
        )
        .fetchall()
    )
    total = sum(r["n"] for r in rows)
    at_step = {r["current_step"]: r["n"] for r in rows}
    reached: dict[str, int] = {}
    seen_before = 0
    for step in order:
        reached[step] = total - seen_before
        seen_before += at_step.get(step, 0)
    reached[STEP_DONE] = sum(r["n"] for r in rows if r["is_complete"])
    return reached


def final_message(seminar: dict, registration: dict) -> str:
    """پیام پایانی ثبت‌نام — قالب اختصاصی سمینار بر قالب سراسری مقدم است."""
    template = (seminar.get("message_template") or "").strip()
    values = {
        "name": registration["name"] or "کاربر",
        "seminar": seminar["title"],
        "date": seminar["date_text"] or "—",
        "link": seminar["link"] or "",
    }
    if template:
        try:
            return template.format(**values)
        except (KeyError, IndexError, ValueError):
            pass  # جای‌گذار نامعتبر → قالب سراسری
    return content.FINAL_MSG.format(**values)
