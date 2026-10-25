"""یادآورهای خودکار — ناتمام‌ها روزانه (هر ۲۴ ساعت)، کامل‌شده‌ها ۱۲ و ۲ ساعت قبل از شروع.

قواعد ضد اسپم:
- هر یادآور برای هر (کاربر، سمینار، نوع) فقط یک‌بار ارسال می‌شود (جدول reminders).
- بعد از شروع سمینار هیچ یادآوری نمی‌آید (نه ناتمام، نه کامل).
- سمینار بدون زمان شروع: حداکثر NUDGE_CAP_NO_DATE یادآور ناتمامی (نه تا ابد).
- سمینار بسته یا کلید خاموش پنل = بدون یادآور.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import content
from bot.constants import CB_SEMINAR_REGISTER
from bot.services import seminars, sender
from bot.services.database import get_db, get_setting, now_iso, set_setting

logger = logging.getLogger(__name__)

# انواع یادآور
KIND_NUDGE = "nudge"  # ناتمام‌ها
KIND_PRE12 = "pre12"  # ۱۲ ساعت قبل از شروع
KIND_PRE2 = "pre2"  # ۲ ساعت قبل از شروع

NUDGE_INTERVAL = timedelta(days=1)  # فاصله‌ی یادآور ناتمامی — روزانه
NUDGE_CAP_NO_DATE = 8  # سقف یادآور ناتمامی وقتی زمان شروع نامشخص است
CHECK_INTERVAL = 600  # هر ۱۰ دقیقه بررسی (ثانیه)

_ENABLED_KEY = "reminders_enabled"
_task: asyncio.Task | None = None


# ── کلید روشن/خاموش ───────────────────────────────────────────────────────


def enabled() -> bool:
    """یادآورها روشن‌اند؟ (پیش‌فرض: روشن)"""
    return get_setting(_ENABLED_KEY, "1") != "0"


def set_enabled(value: bool) -> None:
    set_setting(_ENABLED_KEY, "1" if value else "0")


# ── دفتر ضدتکرار ──────────────────────────────────────────────────────────


def _reminder_row(user_id: int, seminar_id: int, kind: str):
    return (
        get_db()
        .execute(
            "SELECT times, last_sent FROM reminders "
            "WHERE user_id = ? AND seminar_id = ? AND kind = ?",
            (user_id, seminar_id, kind),
        )
        .fetchone()
    )


def _sent_times(user_id: int, seminar_id: int, kind: str) -> int:
    row = _reminder_row(user_id, seminar_id, kind)
    return row["times"] if row else 0


def _is_sent(user_id: int, seminar_id: int, kind: str) -> bool:
    return _sent_times(user_id, seminar_id, kind) > 0


def _log_sent(user_id: int, seminar_id: int, kind: str) -> None:
    """ثبت ارسال یادآور (افزایش شمارنده)."""
    get_db().execute(
        """INSERT INTO reminders (user_id, seminar_id, kind, times, last_sent)
           VALUES (?, ?, ?, 1, ?)
           ON CONFLICT(user_id, seminar_id, kind)
           DO UPDATE SET times = times + 1, last_sent = excluded.last_sent""",
        (user_id, seminar_id, kind, now_iso()),
    )
    get_db().commit()


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


# ── ارسال یادآورها ────────────────────────────────────────────────────────


async def _send_nudge(app, user_id: int, seminar: dict) -> None:
    await app.bot.send_message(
        chat_id=user_id,
        text=content.REMINDER_NUDGE_TEXT.format(seminar=seminar["title"]),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        content.LBL_RESUME_REGISTRATION,
                        callback_data=CB_SEMINAR_REGISTER.format(seminar_id=seminar["id"]),
                    )
                ]
            ]
        ),
    )


async def _send_pre(app, user_id: int, seminar: dict, kind: str) -> None:
    text = (
        content.REMINDER_PRE12_TEXT if kind == KIND_PRE12 else content.REMINDER_PRE2_TEXT
    ).format(seminar=seminar["title"], date=seminar["date_text"] or "—", link=seminar["link"])
    rows = []
    if seminar["link"]:
        rows.append([InlineKeyboardButton(content.LBL_ENTER_SEMINAR, url=seminar["link"])])
    await app.bot.send_message(
        chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(rows) if rows else None
    )


async def _dispatch(send) -> bool:
    """ارسال از صف انبوه (نرخ ۵ در ثانیه + هندل خطای 429)."""
    future = sender.submit(send)
    return future is not None and await future


async def run_due_reminders(app) -> dict[str, int]:
    """بررسی و ارسال همه‌ی یادآورهای سررسید — مستقیم قابل فراخوانی برای تست."""
    report = {"nudge": 0, "pre12": 0, "pre2": 0, "failed": 0}
    if not enabled():
        return report

    now = datetime.now()
    for seminar in seminars.list_seminars(open_only=True):
        starts = seminars.starts_at_dt(seminar)
        started = starts is not None and now >= starts

        for reg in seminars.list_registrations(seminar["id"]):
            user_id = reg["user_id"]
            if reg["is_complete"]:
                if started or starts is None:
                    continue  # بدون زمان شروع یا شروع‌شده → هیچ
                remaining = starts - now
                if timedelta(0) < remaining <= timedelta(hours=2):
                    kind, key = KIND_PRE2, "pre2"
                elif timedelta(hours=2) < remaining <= timedelta(hours=12):
                    kind, key = KIND_PRE12, "pre12"
                else:
                    continue
                if _is_sent(user_id, seminar["id"], kind):
                    continue  # قبلاً ارسال شده
                if await _dispatch(
                    lambda uid=user_id, sem=seminar, k=kind: _send_pre(app, uid, sem, k)
                ):
                    _log_sent(user_id, seminar["id"], kind)
                    report[key] += 1
                else:
                    report["failed"] += 1
            else:
                if started:
                    continue  # بعد از شروع سمینار، ناتمام‌ها یادآوری نمی‌شوند
                row = _reminder_row(user_id, seminar["id"], KIND_NUDGE)
                anchor = _parse_ts(row["last_sent"] if row else "") or _parse_ts(reg["updated_at"])
                if anchor and now - anchor < NUDGE_INTERVAL:
                    continue  # هنوز یک روز کامل نشده
                if (
                    starts is None
                    and _sent_times(user_id, seminar["id"], KIND_NUDGE) >= NUDGE_CAP_NO_DATE
                ):
                    continue  # سقف یادآور بدون زمان شروع
                if await _dispatch(lambda uid=user_id, sem=seminar: _send_nudge(app, uid, sem)):
                    _log_sent(user_id, seminar["id"], KIND_NUDGE)
                    report["nudge"] += 1
                else:
                    report["failed"] += 1
    return report


# ── حلقه‌ی پس‌زمینه ───────────────────────────────────────────────────────


async def _reminder_loop(app) -> None:
    """هر CHECK_INTERVAL ثانیه یک‌بار بررسی — اولین چک بعد از یک دوره کامل."""
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        try:
            await run_due_reminders(app)
        except Exception:  # noqa: BLE001 — حلقه هرگز نباید بمیرد
            logger.exception("خطا در حلقه‌ی یادآورها")


def ensure_task(app) -> None:
    """شروع حلقه‌ی یادآور (اگر قبلاً روشن نیست)."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_reminder_loop(app))
        logger.info("حلقه‌ی یادآورها روشن شد (هر %s ثانیه)", CHECK_INTERVAL)


async def cancel_task() -> None:
    """توقف حلقه‌ی یادآور هنگام خاموش شدن ربات."""
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
        logger.info("حلقه‌ی یادآورها متوقف شد")
