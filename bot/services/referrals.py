"""لینک‌های رفرال تبلیغاتی و آمار قیف — پورت‌شده از ربات تیزگام.

- هر لینک رفرال = یک کمپین/کانال تبلیغاتی: ``t.me/<bot>?start=ref_<code>``
- مدیر می‌تواند **هر چند لینک** با **برچسب دلخواه** بسازد.
- اتریبیوشن **first-touch** و یکتا: هر کاربر فقط یک بار و فقط با اولین
  لینکی که با آن /start زده شمرده می‌شود؛ ورودهای بعدی (حتی با لینک
  دیگر) چیزی را تغییر نمی‌دهند.
- قیف آماری: به ازای هر لینک، تعداد کاربران یکتایی که به هر مرحله‌ی
  ثبت‌نام رسیده‌اند + ثبت‌نام‌های کامل + تفکیک پایه.
- «ارگانیک» = کاربرانی که بدون لینک رفرال ثبت‌نام‌شان را شروع کرده‌اند
  (``link_id IS NULL`` روی سطر ثبت‌نام).
"""

from __future__ import annotations

import csv
import io
import secrets

from bot.config import content
from bot.constants import REF_START_PREFIX
from bot.services import seminars
from bot.services.database import get_db, now_iso

# الفبای کد بدون حروف گیج‌کننده (l/1، o/0، i حذف شده‌اند)
_CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_CODE_LEN = 6
_PHRASE_LEN = 8

STEP_LABELS = {
    seminars.STEP_NAME: "نام",
    seminars.STEP_GRADE: "پایه",
    seminars.STEP_FIELD: "رشته",
    seminars.STEP_CITY: "شهر",
    seminars.STEP_PHONE: "شماره",
    seminars.STEP_SMS: "تایید شماره",
    seminars.STEP_DONE: "ثبت‌نام کامل",
}


# ---------------------------------------------------------------------------
# مدیریت لینک‌ها
# ---------------------------------------------------------------------------


def _new_unique(field: str, length: int) -> str:
    """مقدار یکتا برای ستون داده‌شده (code یا phrase)."""
    while True:
        value = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
        if (
            not get_db()
            .execute(f"SELECT 1 FROM referral_links WHERE {field} = ?", (value,))
            .fetchone()
        ):
            return value


def create_link(label: str) -> dict:
    """ساخت لینک رفرال جدید با برچسب مدیر؛ کد یکتا + رمز ورود کانال."""
    label = label.strip()[:64] or "بدون برچسب"
    for _ in range(20):  # احتمال تکراری بودن کد ۶کاراکتری عملاً صفر است
        code = _new_unique("code", _CODE_LEN)
        try:
            get_db().execute(
                "INSERT INTO referral_links (code, label, is_active, phrase, created_at)"
                " VALUES (?, ?, 1, ?, ?)",
                (code, label, _new_unique("phrase", _PHRASE_LEN), now_iso()),
            )
            get_db().commit()
        except Exception:  # noqa: BLE001 — کد تکراری؛ یک کد دیگر امتحان می‌شود
            continue
        link = get_link_by_code(code)
        assert link is not None
        return link
    raise RuntimeError("ساخت کد یکتای رفرال ناموفق بود")


def get_link_by_code(code: str) -> dict | None:
    row = get_db().execute("SELECT * FROM referral_links WHERE code = ?", (code,)).fetchone()
    return dict(row) if row else None


def get_link(link_id: int) -> dict | None:
    row = get_db().execute("SELECT * FROM referral_links WHERE link_id = ?", (link_id,)).fetchone()
    return dict(row) if row else None


def links() -> list[dict]:
    """همه‌ی لینک‌ها (جدیدترین اول)."""
    rows = get_db().execute("SELECT * FROM referral_links ORDER BY link_id DESC").fetchall()
    return [dict(r) for r in rows]


def set_active(link_id: int, active: bool) -> None:
    get_db().execute(
        "UPDATE referral_links SET is_active = ? WHERE link_id = ?",
        (1 if active else 0, link_id),
    )
    get_db().commit()


def reset_phrase(link_id: int) -> str:
    """رمز ورود جدید برای لینک — رمز قبلی بی‌اعتبار می‌شود."""
    phrase = _new_unique("phrase", _PHRASE_LEN)
    get_db().execute("UPDATE referral_links SET phrase = ? WHERE link_id = ?", (phrase, link_id))
    get_db().commit()
    return phrase


def find_link_by_phrase(phrase: str) -> dict | None:
    """لینکِ صاحب این رمز ورود (طبق رمز؛ وضعیت فعال/غیرفعال جداگانه چک می‌شود)."""
    row = (
        get_db()
        .execute("SELECT * FROM referral_links WHERE phrase = ?", ((phrase or "").strip().lower(),))
        .fetchone()
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# ادمین‌های کانال (دسترسی فقط-آماری با رمز ورود)
# ---------------------------------------------------------------------------


def add_channel_admin(user_id: int, link_id: int) -> None:
    get_db().execute(
        "INSERT OR IGNORE INTO channel_admins (user_id, link_id, added_at) VALUES (?, ?, ?)",
        (user_id, link_id, now_iso()),
    )
    get_db().commit()


def remove_channel_admin(user_id: int, link_id: int) -> None:
    get_db().execute(
        "DELETE FROM channel_admins WHERE user_id = ? AND link_id = ?", (user_id, link_id)
    )
    get_db().commit()


def is_channel_admin(user_id: int, link_id: int) -> bool:
    row = (
        get_db()
        .execute(
            "SELECT 1 FROM channel_admins WHERE user_id = ? AND link_id = ?", (user_id, link_id)
        )
        .fetchone()
    )
    return row is not None


def link_admins(link_id: int) -> list[dict]:
    """ادمین‌های کانالِ واردشده به این لینک (برای پنل مدیریت)."""
    rows = (
        get_db()
        .execute(
            "SELECT user_id, added_at FROM channel_admins WHERE link_id = ? ORDER BY added_at",
            (link_id,),
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


def all_channel_admin_ids() -> list[int]:
    """شناسه‌ی همه‌ی ادمین‌های کانالِ واردشده (برای پاک‌سازی scope دستورها)."""
    rows = get_db().execute("SELECT DISTINCT user_id FROM channel_admins").fetchall()
    return [r["user_id"] for r in rows]


def user_links(user_id: int) -> list[dict]:
    """لینک‌هایی که این کاربر به‌عنوان ادمین کانال به آمارشان دسترسی دارد."""
    rows = (
        get_db()
        .execute(
            "SELECT rl.* FROM channel_admins ca JOIN referral_links rl"
            " ON rl.link_id = ca.link_id WHERE ca.user_id = ? ORDER BY rl.link_id DESC",
            (user_id,),
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# اتریبیوشن (first-touch)
# ---------------------------------------------------------------------------


def attribute_start(user_id: int, code: str) -> int | None:
    """ثبت استارتِ یکتا با کد رفرال؛ link_id برگردانده می‌شود (یا None).

    - لینک باید موجود و فعال باشد.
    - هر کاربر فقط بار اول شمرده می‌شود (INSERT OR IGNORE).
    """
    link = get_link_by_code(code)
    if link is None or not link["is_active"]:
        return None
    get_db().execute(
        "INSERT OR IGNORE INTO referral_starts (user_id, link_id, started_at) VALUES (?, ?, ?)",
        (user_id, link["link_id"], now_iso()),
    )
    get_db().commit()
    return int(link["link_id"])


def attributed_link_id(user_id: int) -> int | None:
    """لینکی که این کاربر را آورده است (اولین /start با رفرال)."""
    row = (
        get_db()
        .execute("SELECT link_id FROM referral_starts WHERE user_id = ?", (user_id,))
        .fetchone()
    )
    return int(row["link_id"]) if row else None


# ---------------------------------------------------------------------------
# آمار قیف
# ---------------------------------------------------------------------------


def _link_filter(link_id: int | None) -> tuple[str, list]:
    """بخش WHERE برای فیلتر ثبت‌نام‌های یک لینک (None = ارگانیک)."""
    if link_id is None:
        return "link_id IS NULL", []
    return "link_id = ?", [link_id]


def funnel(link_id: int | None) -> dict:
    """قیف کامل یک لینک (یا ارگانیک) به‌صورت dict.

    کلیدها: ``starts``، ``steps`` (dict مرحله→تعداد)، ``completed``،
    ``grades`` (dict پایه→تعداد کامل‌شده‌ها) و ``last_start``.
    """
    db = get_db()
    where, params = _link_filter(link_id)

    if link_id is None:
        starts = db.execute(
            f"SELECT COUNT(*) AS c FROM registrations WHERE {where}", params
        ).fetchone()
        last = None
    else:
        starts = db.execute(
            "SELECT COUNT(*) AS c FROM referral_starts WHERE link_id = ?", (link_id,)
        ).fetchone()
        last = db.execute(
            "SELECT MAX(started_at) AS m FROM referral_starts WHERE link_id = ?", (link_id,)
        ).fetchone()

    # شمارش «رسیده به هر مرحله» — همان منطق funnel_counts با فیلتر لینک
    rows = db.execute(
        f"SELECT current_step, is_complete, COUNT(*) AS n FROM registrations "
        f"WHERE {where} GROUP BY current_step, is_complete",
        params,
    ).fetchall()
    total = sum(r["n"] for r in rows)
    at_step = {r["current_step"]: r["n"] for r in rows}
    steps: dict[str, int] = {}
    seen_before = 0
    for step in seminars.STEP_ORDER:
        steps[step] = total - seen_before
        seen_before += at_step.get(step, 0)
    steps[seminars.STEP_DONE] = sum(r["n"] for r in rows if r["is_complete"])

    grade_rows = db.execute(
        f"SELECT grade, COUNT(*) AS n FROM registrations "
        f"WHERE {where} AND is_complete = 1 GROUP BY grade",
        params,
    ).fetchall()
    by_grade = {r["grade"]: r["n"] for r in grade_rows}
    grades = {g: by_grade.get(g, 0) for g in content.WIZ_GRADE_OPTIONS}

    return {
        "starts": int(starts["c"]) if starts else 0,
        "steps": steps,
        "completed": steps[seminars.STEP_DONE],
        "grades": grades,
        "last_start": (last["m"] if last else None),
    }


def link_registrations(link_id: int) -> list[dict]:
    """ثبت‌نام‌های نسبت‌داده‌شده به یک لینک رفرال (با عنوان سمینار)."""
    rows = (
        get_db()
        .execute(
            "SELECT r.*, s.title AS seminar_title FROM registrations r "
            "LEFT JOIN seminars s ON s.id = r.seminar_id "
            "WHERE r.link_id = ? ORDER BY r.created_at, r.rowid",
            (link_id,),
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


def link_regs_csv(link: dict) -> str:
    """خروجی CSV ثبت‌نامی‌های یک لینک (اسم + شماره‌ها + وضعیت)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "ردیف",
            "نام",
            "پایه",
            "رشته",
            "شهر",
            "شماره تلگرام",
            "شماره پیامک",
            "وضعیت",
            "سمینار",
            "تاریخ ثبت",
        ]
    )
    for i, reg in enumerate(link_registrations(int(link["link_id"])), 1):
        writer.writerow(
            [
                i,
                reg["name"],
                reg["grade"],
                reg["field"],
                reg["city"],
                reg["phone"],
                reg["sms_phone"],
                "کامل" if reg["is_complete"] else "نیمه‌کاره",
                reg["seminar_title"] or "—",
                reg["created_at"],
            ]
        )
    return buf.getvalue()


def link_url(bot_username: str, code: str) -> str:
    """لینک قابل‌اشتراک برای کانال تبلیغاتی (با پیشوند ref_)."""
    return f"https://t.me/{bot_username}?start={REF_START_PREFIX}{code}"


def ads_csv(bot_username: str) -> str:
    """خروجی CSV آمار تبلیغات (سازگار با Excel فارسی)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    header = ["code", "label", "active", "created_at", "link", "starts"]
    header += [f"step_{STEP_LABELS[s]}" for s in seminars.STEP_ORDER]
    header += ["completed", "grade_406", "grade_407", "grade_408", "conversion_percent"]
    writer.writerow(header)
    for link in links():
        f = funnel(int(link["link_id"]))
        conv = round(f["completed"] * 100 / f["starts"], 1) if f["starts"] else 0
        row = [
            link["code"],
            link["label"],
            "yes" if link["is_active"] else "no",
            link["created_at"],
            link_url(bot_username, link["code"]),
            f["starts"],
        ]
        row += [f["steps"][s] for s in seminars.STEP_ORDER]
        row += [
            f["completed"],
            f["grades"][content.WIZ_GRADE_OPTIONS[0]],
            f["grades"][content.WIZ_GRADE_OPTIONS[1]],
            f["grades"][content.WIZ_GRADE_OPTIONS[2]],
            conv,
        ]
        writer.writerow(row)
    return buf.getvalue()
