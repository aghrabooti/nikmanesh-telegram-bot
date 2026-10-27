"""پنل مدیریت: سمینارها (با زمان شروع/قالب اختصاصی)، آمار، خروجی‌ها،
پیام همگانی و کلید یادآورها."""

from __future__ import annotations

import csv
import html
import io
import logging
from datetime import date, datetime, timedelta

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot import navigation
from bot.config import content
from bot.config.settings import get_settings
from bot.constants import (
    ABOUT_STATE_KEY,
    ADMIN_REF_PROMPT_CHAT_ID_KEY,
    ADMIN_REF_PROMPT_MESSAGE_ID_KEY,
    BCAST_STATE_KEY,
    EDIT_STATE_KEY,
    EXPORT_RANGE_STATE_KEY,
    NEW_STATE_KEY,
    PATTERN_ADMIN_ABOUT,
    PATTERN_ADMIN_ADS,
    PATTERN_ADMIN_ADS_CSV,
    PATTERN_ADMIN_ADS_DELETE,
    PATTERN_ADMIN_ADS_DELETE2,
    PATTERN_ADMIN_ADS_KICK,
    PATTERN_ADMIN_ADS_MSG,
    PATTERN_ADMIN_ADS_NEW,
    PATTERN_ADMIN_ADS_REGS,
    PATTERN_ADMIN_ADS_REGS_CSV,
    PATTERN_ADMIN_ADS_REGS_XLSX,
    PATTERN_ADMIN_ADS_RESET_PHRASE,
    PATTERN_ADMIN_ADS_TOGGLE,
    PATTERN_ADMIN_ADS_VIEW,
    PATTERN_ADMIN_ADS_XLSX,
    PATTERN_ADMIN_BCAST,
    PATTERN_ADMIN_BCAST_GO,
    PATTERN_ADMIN_BCAST_NO,
    PATTERN_ADMIN_EXPORT_ALL,
    PATTERN_ADMIN_EXPORT_CANCEL,
    PATTERN_ADMIN_EXPORT_LEADS,
    PATTERN_ADMIN_EXPORT_STARTS,
    PATTERN_ADMIN_RANGE,
    PATTERN_ADMIN_REGS,
    PATTERN_ADMIN_REGS_CSV,
    PATTERN_ADMIN_REGS_CSV_COMPLETE,
    PATTERN_ADMIN_REGS_MSG,
    PATTERN_ADMIN_REGS_XLSX,
    PATTERN_ADMIN_REGS_XLSX_COMPLETE,
    PATTERN_ADMIN_REMINDERS,
    PATTERN_ADMIN_SEM_DELETE,
    PATTERN_ADMIN_SEM_DELETE2,
    PATTERN_ADMIN_SEM_EDIT,
    PATTERN_ADMIN_SEM_EDIT_FIELD,
    PATTERN_ADMIN_SEM_NEW,
    PATTERN_ADMIN_SEM_OPEN,
    PATTERN_ADMIN_SEM_PAGE,
    PATTERN_ADMIN_SEMS,
    PATTERN_ADMIN_USERS_CSV,
    PATTERN_ADMIN_USERS_XLSX,
    RANGE_STATE_KEY,
    REF_STATE_KEY,
    REGS_STATE_KEY,
    SEMINAR_FIELDS,
    WIDE_INVITE_PROMPT_CHAT_ID_KEY,
    WIDE_INVITE_PROMPT_MESSAGE_ID_KEY,
    WIDE_INVITE_STATE_KEY,
)
from bot.keyboards import admin as keyboards
from bot.services import referrals, reminders, seminars, sender, settings, users, wide_admins
from bot.utils.dates import parse_datetime_text
from bot.utils.excel import xlsx_bytes, xlsx_from_csv
from bot.utils.jalali import format_jalali, parse_jalali_text
from bot.utils.persian import to_en, to_fa

logger = logging.getLogger(__name__)

# مراحل ساخت سمینار جدید — فقط اسم و پیام آخر
_NEW_STEPS = ("title", "message_template")

fa_num = to_fa  # خوانایی ارقام فارسی در متن‌های پنل


def _esc(text: str) -> str:
    return html.escape(text or "")


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def _require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """دسترسی فقط برای ADMIN_IDS؛ در غیر این صورت پیام و توقف."""
    user = update.effective_user
    if user and user.id in get_settings().admin_ids:
        return True
    if update.callback_query:
        await context.bot.answer_callback_query(
            callback_query_id=update.callback_query.id, text=content.ADMIN_ONLY_TEXT
        )
    elif update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.ADMIN_ONLY_TEXT
        )
    return False


# ---------------------------------------------------------------------------
# صفحه‌ی اصلی پنل
# ---------------------------------------------------------------------------


def _overview_text() -> str:
    all_seminars = seminars.list_seminars()
    open_count = sum(1 for s in all_seminars if s["is_open"])
    reminders_label = (
        content.LBL_ADMIN_REMINDERS_ON if reminders.enabled() else content.LBL_ADMIN_REMINDERS_OFF
    ).removeprefix("⏰ یادآورها: ")
    return (
        content.ADMIN_MENU_HEADER
        + content.ADMIN_STATS_LINE.format(
            total=fa_num(len(all_seminars)),
            open_count=fa_num(open_count),
            users=fa_num(users.count_users()),
            reminders=reminders_label,
        )
        + content.ADMIN_MENU_HINT
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ورود به پنل: /admin"""
    if not await _require_admin(update, context):
        return
    context.user_data.pop(EXPORT_RANGE_STATE_KEY, None)
    await navigation.render_screen(
        update, context, text=_overview_text(), reply_markup=keyboards.overview()
    )


async def admin_reminders_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """روشن/خاموش کردن یادآورهای خودکار."""
    if not await _require_admin(update, context):
        return
    now_on = not reminders.enabled()
    reminders.set_enabled(now_on)
    await update.callback_query.answer(
        content.ADMIN_REMINDERS_ON_DONE if now_on else content.ADMIN_REMINDERS_OFF_DONE
    )
    await navigation.render_screen(
        update,
        context,
        text=_overview_text(),
        reply_markup=keyboards.overview(reminders_on=now_on),
    )


async def admin_about_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """شروع ویرایش متن صفحه‌ی «درباره آکادمی نیک منش»."""
    if not await _require_admin(update, context):
        return
    await update.callback_query.answer()
    context.user_data[ABOUT_STATE_KEY] = True
    await navigation.render_screen(update, context, text=content.ADMIN_ABOUT_PROMPT)


async def _handle_about_input(update, context) -> None:
    """دریافت متن جدید «درباره آکادمی» از مدیر."""
    context.user_data.pop(ABOUT_STATE_KEY, None)
    text = (update.message.text or "").strip()

    if text in ("پیش‌فرض", "پیش فرض"):
        settings.set_about_text("")  # بازگشت به متن اولیه
    elif len(text) > 2500:
        context.user_data[ABOUT_STATE_KEY] = True
        await navigation.render_screen(update, context, text=content.ADMIN_ABOUT_INVALID)
        return
    else:
        settings.set_about_text(text)

    await navigation.render_screen(update, context, text=content.ADMIN_ABOUT_SAVED_TEXT)
    await navigation.render_screen(
        update,
        context,
        text=_overview_text(),
        reply_markup=keyboards.overview(reminders_on=reminders.enabled()),
    )


# ---------------------------------------------------------------------------
# لیست سمینارها (با آمار جداگانه‌ی هر سمینار)
# ---------------------------------------------------------------------------


def _sems_text() -> str:
    rows = [
        f"{'🟢' if s['is_open'] else '🔴'} <b>{_esc(s['title'])}</b> — "
        f"ثبت‌نام <b>{fa_num(s['reg_total'])}</b> (کامل <b>{fa_num(s['reg_done'])}</b>)"
        for s in seminars.list_with_counts()
    ]
    return content.ADMIN_SEMS_HEADER + "\n".join(rows) + content.ADMIN_SEMS_FOOTER


async def _clear_admin_states(context) -> None:
    """پاک‌سازی state های معلق هنگام جابه‌جایی بین صفحه‌ها."""
    for key in (
        NEW_STATE_KEY,
        EDIT_STATE_KEY,
        RANGE_STATE_KEY,
        BCAST_STATE_KEY,
        ABOUT_STATE_KEY,
        EXPORT_RANGE_STATE_KEY,
        REF_STATE_KEY,
        ADMIN_REF_PROMPT_CHAT_ID_KEY,
        ADMIN_REF_PROMPT_MESSAGE_ID_KEY,
        WIDE_INVITE_STATE_KEY,
        WIDE_INVITE_PROMPT_CHAT_ID_KEY,
        WIDE_INVITE_PROMPT_MESSAGE_ID_KEY,
    ):
        context.user_data.pop(key, None)


async def admin_sems(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    await update.callback_query.answer()
    await _clear_admin_states(context)
    await navigation.render_screen(
        update, context, text=_sems_text(), reply_markup=keyboards.sems_list()
    )


# ---------------------------------------------------------------------------
# صفحه‌ی سمینار + آمار
# ---------------------------------------------------------------------------


def _seminar_text(seminar: dict) -> str:
    total, done = seminars.count_registrations(seminar["id"])
    funnel = seminars.funnel_counts(seminar["id"])
    levels = seminars.split_levels(seminar)
    lines = [
        f"{'🟢 باز' if seminar['is_open'] else '🔴 بسته'} | 🎓 <b>{_esc(seminar['title'])}</b>",
        "",
    ]
    if seminar["description"]:
        lines += [_esc(seminar["description"]), ""]
    if seminar["date_text"]:
        lines.append(f"🗓 {_esc(seminar['date_text'])}")
    if seminar["starts_at"]:
        lines.append(f"⏰ شروع: {fa_num(seminars.format_starts_at(seminar))}")
    if seminar["link"]:
        lines.append(f"🔗 {_esc(seminar['link'])}")
    if levels:
        lines.append("👥 " + "، ".join(_esc(x) for x in levels))
    lines.append(
        content.ADMIN_TEMPLATE_LABEL_OWN
        if seminar["message_template"]
        else content.ADMIN_TEMPLATE_LABEL_GLOBAL
    )
    lines += [
        "",
        f"📊 کل: <b>{fa_num(total)}</b> | کامل: <b>{fa_num(done)}</b> | "
        f"نیمه‌کاره: <b>{fa_num(total - done)}</b>",
    ]
    if total:
        steps = [
            ("نام", funnel[seminars.STEP_NAME]),
            ("پایه", funnel[seminars.STEP_GRADE]),
            ("رشته", funnel[seminars.STEP_FIELD]),
            ("شهر", funnel[seminars.STEP_CITY]),
            ("تلفن", funnel[seminars.STEP_PHONE]),
            ("شماره جایگزین", funnel[seminars.STEP_DONE]),
        ]
        lines += ["", "قیف: " + " ← ".join(f"{n} {to_fa(v)}" for n, v in steps)]
    return "\n".join(lines)


async def admin_sem_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    seminar = seminars.get_seminar(int(update.callback_query.data.split(":")[2]))
    if seminar is None:
        await update.callback_query.answer(content.SEM_NOT_FOUND_TEXT)
        return
    await update.callback_query.answer()
    await _clear_admin_states(context)
    await navigation.render_screen(
        update, context, text=_seminar_text(seminar), reply_markup=keyboards.seminar_page(seminar)
    )


async def admin_sem_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    sid = int(update.callback_query.data.split(":")[3])
    seminar = seminars.get_seminar(sid)
    if seminar is None:
        await update.callback_query.answer(content.SEM_NOT_FOUND_TEXT)
        return
    now_open = not seminar["is_open"]
    seminars.set_seminar_open(sid, now_open)
    await update.callback_query.answer(
        content.ADMIN_OPENED_DONE if now_open else content.ADMIN_CLOSED_DONE
    )
    seminar = seminars.get_seminar(sid)
    await navigation.render_screen(
        update, context, text=_seminar_text(seminar), reply_markup=keyboards.seminar_page(seminar)
    )


async def admin_sem_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تأیید دومرحله‌ای حذف."""
    if not await _require_admin(update, context):
        return
    seminar = seminars.get_seminar(int(update.callback_query.data.split(":")[3]))
    if seminar is None:
        await update.callback_query.answer(content.SEM_NOT_FOUND_TEXT)
        return
    await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=content.ADMIN_DELETE_HEADER.format(title=_esc(seminar["title"])),
        reply_markup=keyboards.delete_confirm(seminar),
    )


async def admin_sem_delete2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    seminars.delete_seminar(int(update.callback_query.data.split(":")[3]))
    await update.callback_query.answer(content.ADMIN_DELETED_TEXT)
    await navigation.render_screen(
        update, context, text=_sems_text(), reply_markup=keyboards.sems_list()
    )


# ---------------------------------------------------------------------------
# تبلیغات و رفرال — لینک‌های اسم‌دار (پورت ربات تیزگام)
# ---------------------------------------------------------------------------


def _fa_dt(iso: str | None) -> str:
    """«2026-10-23 14:30:00» → «۱۴۰۵/۰۸/۰۱ — ۱۴:۳۰»."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{to_fa(format_jalali(dt.date()))} — {to_fa(dt.strftime('%H:%M'))}"


def _funnel_line(f: dict) -> str:
    """سطر قیف مرحله‌به‌مرحله: نام ۵۰ → پایه ۴۲ → … → ✅ ۱۰"""
    parts = [
        f"{referrals.STEP_LABELS[step]} {fa_num(f['steps'][step])}" for step in seminars.STEP_ORDER
    ]
    parts.append(f"✅ {fa_num(f['completed'])}")
    return " → ".join(parts)


def _grades_line(f: dict) -> str:
    return " | ".join(f"{g.split()[-1]}: {fa_num(n)}" for g, n in f["grades"].items())


def _ads_hub_text() -> str:
    """متن هاب مدیریت تبلیغات."""
    body = content.ADS_HUB_WITH_LINKS if referrals.links() else content.ADS_HUB_EMPTY
    return "\n".join([content.ADS_HUB_TITLE, "", body, "", content.ADS_HUB_FOOTER])


def _ads_link_rows() -> list[list]:
    """دکمه‌ی ورود به صفحه‌ی مدیریت هر لینک رفرال."""
    rows = []
    for link in referrals.links():
        prefix = "" if link["is_active"] else "⏸ "
        rows.append(
            [
                keyboards._btn(
                    f"{prefix}{link['label']} — {link['code']}",
                    f"adm:ads:v:{link['link_id']}",
                )
            ]
        )
    return rows


def _ads_link_detail_text(link: dict, bot_username: str) -> str:
    """متن صفحه‌ی مدیریت یک لینک رفرال."""
    f = referrals.funnel(int(link["link_id"]))
    pct = (f["completed"] * 100 / f["starts"]) if f["starts"] else 0.0
    url = referrals.link_url(bot_username, link["code"])
    status = "✅ فعال" if link["is_active"] else "⏸ غیرفعال"
    owner_id = link.get("owner_user_id")
    if owner_id:
        owner = next(
            (item for item in wide_admins.list_wide_admins() if item["user_id"] == owner_id),
            None,
        )
        owner_name = _esc((owner or {}).get("first_name") or str(owner_id))
        owner_label = f"ادمین گستردهٔ {owner_name} ({owner_id})"
    else:
        owner_label = "ادمین اصلی"
    lines = [
        f"📣 <b>{_esc(link['label'])}</b>",
        "",
        f"🔗 لینک کامل: <code>{_esc(url)}</code>",
        f"🕒 ساخته شده: <code>{_fa_dt(link['created_at'])}</code>",
        f"🔘 وضعیت: {status}",
        content.WIDE_LINK_OWNER_LINE.format(owner=owner_label),
        "",
        f"👥 تعداد ورودی (استارت): <b>{fa_num(f['starts'])}</b>",
        f"✅ ثبت‌نام کامل: <b>{fa_num(f['completed'])}</b>"
        f" — <b>{fa_num(round(pct, 1))}٪</b> از استارت‌ها",
        "",
        "📊 قیف ثبت‌نام:",
        _funnel_line(f),
        f"🎓 {_grades_line(f)}",
    ]
    if f["last_start"]:
        lines.append(f"🕒 آخرین استارت: <code>{_fa_dt(f['last_start'])}</code>")
    lines.append(content.ADS_PHRASE_LINE.format(phrase=_esc(link["phrase"])))
    admins = referrals.link_admins(int(link["link_id"]))
    if admins:
        lines.append(content.ADS_ADMINS_HEADER)
        for entry in admins:
            u = users.get_user(entry["user_id"])
            name = _esc((u or {}).get("first_name") or str(entry["user_id"]))
            uname = _esc((u or {}).get("username") or "—")
            lines.append(f"  • {name} (@{uname} | <code>{entry['user_id']}</code>)")
    else:
        lines.append(content.ADS_ADMINS_EMPTY)
    return "\n".join(lines)


def _ads_text(bot_username: str) -> str:
    """متن کامل آمار تبلیغات (پیامی) — ارگانیک + همه‌ی لینک‌ها."""
    links = referrals.links()
    lines = [content.ADS_STATS_TITLE, ""]
    organic = referrals.funnel(None)
    pct = (organic["completed"] * 100 / organic["starts"]) if organic["starts"] else 0.0
    lines += [
        content.ADS_ORGANIC_TITLE,
        f"شروع ثبت‌نام: <b>{fa_num(organic['starts'])}</b>"
        f" | نهایی: <b>{fa_num(organic['completed'])}</b>"
        f" ({fa_num(round(pct, 1))}٪)",
        _funnel_line(organic),
        "",
    ]
    if links:
        for i, link in enumerate(links, start=1):
            f = referrals.funnel(int(link["link_id"]))
            p = (f["completed"] * 100 / f["starts"]) if f["starts"] else 0.0
            lines += [
                f"{fa_num(i)}. <b>{_esc(link['label'])}</b>"
                f" — <code>ref_{_esc(link['code'])}</code>"
                + (" ✅ فعال" if link["is_active"] else " ⏸ غیرفعال"),
                f"استارت: <b>{fa_num(f['starts'])}</b>"
                f" | نهایی: <b>{fa_num(f['completed'])}</b>"
                f" ({fa_num(round(p, 1))}٪)",
                _funnel_line(f),
                f"🎓 {_grades_line(f)}",
                "",
            ]
    else:
        lines += [content.ADS_NO_LINKS, ""]
    return "\n".join(lines)


async def admin_ads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هاب تبلیغات: ورود به صفحه‌ی هر لینک + خروجی‌ها."""
    if not await _require_admin(update, context):
        return
    await update.callback_query.answer()
    await _clear_admin_states(context)
    await navigation.render_screen(
        update, context, text=_ads_hub_text(), reply_markup=keyboards.ads(_ads_link_rows())
    )


async def admin_ads_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """صفحه‌ی مدیریت یک لینک رفرال: لینک کامل، زمان ساخت و آمار قیف."""
    if not await _require_admin(update, context):
        return
    link = referrals.get_link(int(context.match.group(1)))
    if link is None:
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return await admin_ads(update, context)
    await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=_ads_link_detail_text(link, context.bot.username or "bot"),
        reply_markup=keyboards.ads_link_detail(link),
    )


async def admin_ads_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تأیید دو مرحله‌ای حذف دائمی لینک؛ فقط ادمین اصلی."""
    if not await _require_admin(update, context):
        return
    link_id = int(context.match.group(1))
    link = referrals.get_link(link_id)
    if link is None:
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return
    await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=content.ADS_DELETE_PROMPT.format(label=_esc(link["label"])),
        reply_markup=keyboards.ads_delete_confirm(link),
    )


async def admin_ads_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """حذف دائمی لینک پس از تأیید؛ ثبت‌نام‌ها و first-touch حفظ می‌شوند."""
    if not await _require_admin(update, context):
        return
    link_id = int(context.match.group(1))
    if not referrals.delete_link(link_id):
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return
    await update.callback_query.answer(content.ADS_DELETE_DONE, show_alert=True)
    await navigation.render_screen(
        update,
        context,
        text=_ads_hub_text(),
        reply_markup=keyboards.ads(_ads_link_rows()),
    )


async def admin_ads_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """شروع ساخت لینک رفرال: دریافت برچسب به‌صورت پیام."""
    if not await _require_admin(update, context):
        return
    if context.user_data.get(REF_STATE_KEY):
        await update.callback_query.answer(content.ADS_LABEL_PENDING, show_alert=True)
        return
    await update.callback_query.answer()
    await _clear_admin_states(context)
    context.user_data[REF_STATE_KEY] = True
    prompt_message = update.callback_query.message
    if prompt_message is not None:
        context.user_data[ADMIN_REF_PROMPT_CHAT_ID_KEY] = prompt_message.chat_id
        context.user_data[ADMIN_REF_PROMPT_MESSAGE_ID_KEY] = prompt_message.message_id
    await navigation.render_screen(
        update, context, text=content.ADS_NEW_PROMPT, reply_markup=keyboards.ads_prompt()
    )


async def _handle_ads_label_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دریافت برچسب لینک جدید از مدیر (state موقت REF_STATE_KEY)."""
    label = (update.message.text or "").strip()
    if not label:
        context.user_data[REF_STATE_KEY] = True
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.ADS_LABEL_EMPTY
        )
        return
    context.user_data.pop(REF_STATE_KEY, None)
    link = referrals.create_link(label)
    username = context.bot.username or "bot"
    url = referrals.link_url(username, link["code"])
    logger.info("لینک رفرال جدید ساخته شد: %s (%s)", link["code"], label)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=content.ADS_CREATED_TEXT.format(
            label=_esc(label), url=_esc(url), phrase=_esc(link["phrase"])
        ),
        parse_mode="HTML",
    )
    prompt_chat_id = context.user_data.pop(ADMIN_REF_PROMPT_CHAT_ID_KEY, None)
    prompt_message_id = context.user_data.pop(ADMIN_REF_PROMPT_MESSAGE_ID_KEY, None)
    await navigation.render_saved_screen(
        update,
        context,
        chat_id=prompt_chat_id,
        message_id=prompt_message_id,
        text=_ads_hub_text(),
        reply_markup=keyboards.ads(_ads_link_rows()),
    )


async def admin_ads_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """روشن/خاموش کردن یک لینک رفرال (آمار قبلی حفظ می‌شود)."""
    if not await _require_admin(update, context):
        return
    link = referrals.get_link(int(context.match.group(1)))
    if link is None:
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return
    referrals.set_active(int(link["link_id"]), not link["is_active"])
    state = "فعال" if not link["is_active"] else "غیرفعال"
    await update.callback_query.answer(f"لینک {state} شد.")
    fresh = referrals.get_link(int(link["link_id"]))
    await navigation.render_screen(
        update,
        context,
        text=_ads_link_detail_text(fresh, context.bot.username or "bot"),
        reply_markup=keyboards.ads_link_detail(fresh),
    )


async def admin_ads_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """آمار تبلیغات به‌صورت پیام تلگرامی (خواندن سریع + فوروارد)."""
    if not await _require_admin(update, context):
        return
    await update.callback_query.answer()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=_ads_text(context.bot.username or "bot"),
        parse_mode="HTML",
    )


async def admin_ads_regs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """لیست ثبت‌نامی‌های یک لینک رفرال (اسم + شماره‌ها) به‌صورت پیام."""
    if not await _require_admin(update, context):
        return
    link = referrals.get_link(int(context.match.group(1)))
    if link is None:
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return
    await update.callback_query.answer()
    regs = referrals.link_registrations(int(link["link_id"]))
    if not regs:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.ADS_REGS_EMPTY
        )
        return
    lines = [content.ADS_REGS_TITLE.format(label=_esc(link["label"]))]
    for i, reg in enumerate(regs, 1):
        parts = [
            f"{fa_num(i)}. {_esc(reg['name'] or '—')}",
            _esc(reg["grade"] or "—"),
            _esc(reg["field"] or "—"),
            _esc(reg["city"] or "—"),
            f"تلگرام: {_esc(reg['phone'] or '—')}",
            f"شماره جایگزین: {_esc(reg['alternate_phone'] or '—')}",
        ]
        status = "✅" if reg["is_complete"] else "⏳"
        lines.append(" • ".join(parts) + f" {status} — {_esc(reg['seminar_title'] or '—')}")
    # بلوک‌های ۴۰تایی تا سقف پیام تلگرام
    for chunk_start in range(0, len(lines), 41):
        chunk = lines[chunk_start : chunk_start + 41]
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="\n".join(chunk), parse_mode=ParseMode.HTML
        )


async def admin_ads_regs_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """CSV ثبت‌نامی‌های یک لینک رفرال (اسم + شماره‌ها + وضعیت)."""
    if not await _require_admin(update, context):
        return
    link = referrals.get_link(int(context.match.group(1)))
    if link is None:
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return
    await update.callback_query.answer("در حال ساخت فایل…")
    csv_bytes = ("\ufeff" + referrals.link_regs_csv(link)).encode("utf-8")  # BOM برای Excel
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(csv_bytes),
        filename=f"ref-{link['code']}-regs.csv",
        caption=content.ADS_REGS_CAPTION.format(label=link["label"]),
    )


async def admin_ads_regs_xlsx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """فایل Excel ثبت‌نامی‌های یک لینک رفرال."""
    if not await _require_admin(update, context):
        return
    link = referrals.get_link(int(context.match.group(1)))
    if link is None:
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return
    await update.callback_query.answer("در حال ساخت فایل…")
    document = xlsx_from_csv(referrals.link_regs_csv(link), sheet_name="ثبت‌نام‌ها")
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(document),
        filename=f"ref-{link['code']}-regs.xlsx",
        caption=content.ADS_REGS_CAPTION.format(label=link["label"]),
    )


async def admin_ads_reset_phrase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """رمز ورود جدید برای لینک — رمز قبلی بی‌اعتبار می‌شود (دسترسی‌ها می‌مانند)."""
    if not await _require_admin(update, context):
        return
    link = referrals.get_link(int(context.match.group(1)))
    if link is None:
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return
    referrals.reset_phrase(int(link["link_id"]))
    await update.callback_query.answer(content.ADS_RESET_DONE)
    fresh = referrals.get_link(int(link["link_id"]))
    await navigation.render_screen(
        update,
        context,
        text=_ads_link_detail_text(fresh, context.bot.username or "bot"),
        reply_markup=keyboards.ads_link_detail(fresh),
    )


async def admin_ads_kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بیرون کردن یک ادمین کانال از دسترسی آماری لینک."""
    if not await _require_admin(update, context):
        return
    link = referrals.get_link(int(context.match.group(1)))
    kicked_id = int(context.match.group(2))
    if link is None:
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return
    referrals.remove_channel_admin(kicked_id, int(link["link_id"]))
    await update.callback_query.answer(content.ADS_KICK_DONE)
    await navigation.render_screen(
        update,
        context,
        text=_ads_link_detail_text(link, context.bot.username or "bot"),
        reply_markup=keyboards.ads_link_detail(link),
    )


async def admin_ads_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ارسال خروجی CSV آمار تبلیغات."""
    if not await _require_admin(update, context):
        return
    await update.callback_query.answer("در حال ساخت فایل…")
    username = context.bot.username or "bot"
    csv_bytes = ("\ufeff" + referrals.ads_csv(username)).encode("utf-8")  # BOM برای Excel
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(csv_bytes),
        filename="nikmanesh-ads.csv",
        caption=content.ADS_CAPTION,
    )


async def admin_ads_xlsx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """فایل Excel آمار تبلیغات."""
    if not await _require_admin(update, context):
        return
    await update.callback_query.answer("در حال ساخت فایل…")
    username = context.bot.username or "bot"
    document = xlsx_from_csv(referrals.ads_csv(username), sheet_name="آمار تبلیغات")
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(document),
        filename="nikmanesh-ads.xlsx",
        caption=content.ADS_CAPTION,
    )


# ---------------------------------------------------------------------------
# ساخت سمینار جدید (فرم متنی ۶ مرحله‌ای پشت‌سرهم)
# ---------------------------------------------------------------------------


def _new_prompt(step_index: int) -> str:
    return getattr(content, f"ADMIN_NEW_{_NEW_STEPS[step_index].upper()}_PROMPT")


async def admin_sem_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    await update.callback_query.answer()
    context.user_data[NEW_STATE_KEY] = {"step": 0, "data": {}}
    await navigation.render_screen(update, context, text=_new_prompt(0))


async def _handle_new_input(update, context) -> None:
    state = context.user_data[NEW_STATE_KEY]
    step = _NEW_STEPS[state["step"]]
    text = (update.message.text or "").strip()
    data = state["data"]

    if step == "title":
        if not 3 <= len(text) <= 80:
            await navigation.render_screen(update, context, text=content.ADMIN_TITLE_INVALID)
            return
        data["title"] = text
    elif step == "message_template":
        if len(text) > 800:
            await navigation.render_screen(update, context, text=content.ADMIN_TEMPLATE_INVALID)
            return
        data["message_template"] = "" if text == "-" else text

    state["step"] += 1
    if state["step"] < len(_NEW_STEPS):
        await navigation.render_screen(update, context, text=_new_prompt(state["step"]))
        return

    # پایان فرم → ساخت سمینار
    context.user_data.pop(NEW_STATE_KEY, None)
    seminar = seminars.create_seminar(**data)
    await navigation.render_screen(
        update,
        context,
        text=content.ADMIN_CREATED_TEXT.format(title=_esc(seminar["title"]))
        + "\n\n"
        + _seminar_text(seminar),
        reply_markup=keyboards.seminar_page(seminar),
    )


# ---------------------------------------------------------------------------
# ویرایش فیلدها (۷ فیلد — از جمله زمان شروع و پیام نهایی اختصاصی)
# ---------------------------------------------------------------------------


def _edit_menu_text(seminar: dict) -> str:
    return content.ADMIN_EDIT_HEADER.format(title=_esc(seminar["title"]))


async def admin_sem_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    seminar = seminars.get_seminar(int(update.callback_query.data.split(":")[3]))
    if seminar is None:
        await update.callback_query.answer(content.SEM_NOT_FOUND_TEXT)
        return
    await update.callback_query.answer()
    await _clear_admin_states(context)
    await navigation.render_screen(
        update, context, text=_edit_menu_text(seminar), reply_markup=keyboards.edit_menu(seminar)
    )


async def admin_sem_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پرامپت ویرایش یک فیلد — data: adm:sem:ef:{id}:{field}"""
    if not await _require_admin(update, context):
        return
    _, _, _, sid, field = update.callback_query.data.split(":", 4)
    seminar = seminars.get_seminar(int(sid))
    if seminar is None or field not in SEMINAR_FIELDS:
        await update.callback_query.answer(content.SEM_NOT_FOUND_TEXT)
        return
    await update.callback_query.answer()
    context.user_data[EDIT_STATE_KEY] = {"seminar_id": int(sid), "field": field}
    await navigation.render_screen(update, context, text=content.ADMIN_EDIT_PROMPTS[field])


async def _handle_edit_input(update, context) -> None:
    state = context.user_data.pop(EDIT_STATE_KEY)
    seminar = seminars.get_seminar(state["seminar_id"])
    field, text = state["field"], (update.message.text or "").strip()

    if seminar is None:
        await navigation.render_screen(update, context, text=content.SEM_NOT_FOUND_TEXT)
        return

    value: str
    if field == "title":
        if not 3 <= len(text) <= 80:
            context.user_data[EDIT_STATE_KEY] = state
            await navigation.render_screen(update, context, text=content.ADMIN_TITLE_INVALID)
            return
        value = text
    elif field == "starts_at":
        if to_en(text).strip() in ("هیچ", "-", "بدون"):
            value = ""  # حذف زمان شروع
        else:
            parsed = seminars.parse_starts_at_text(text)
            if parsed is None:
                context.user_data[EDIT_STATE_KEY] = state
                await navigation.render_screen(
                    update, context, text=content.ADMIN_STARTS_AT_INVALID
                )
                return
            value = parsed
    elif field == "message_template":
        if text in ("پیش‌فرض", "پیش فرض"):
            value = ""  # بازگشت به پیام سراسری
        elif len(text) > 800:
            context.user_data[EDIT_STATE_KEY] = state
            await navigation.render_screen(update, context, text=content.ADMIN_TEMPLATE_INVALID)
            return
        else:
            value = text
    else:
        return

    seminars.update_seminar(seminar["id"], **{field: value})
    seminar = seminars.get_seminar(seminar["id"])
    await navigation.render_screen(
        update,
        context,
        text=content.ADMIN_SAVED_TEXT.format(field=content.ADMIN_FIELD_LABELS[field]),
    )
    await navigation.render_screen(
        update, context, text=_edit_menu_text(seminar), reply_markup=keyboards.edit_menu(seminar)
    )


# ---------------------------------------------------------------------------
# ثبت‌نام‌ها + بازه‌ی تاریخ + خروجی‌ها
# ---------------------------------------------------------------------------


def _set_regs_state(
    context, seminar_id: int, since: date | None, until: date | None, *, code: str = ""
) -> None:
    context.user_data[REGS_STATE_KEY] = {
        "seminar_id": seminar_id,
        "since": since.isoformat() if since else None,
        "until": until.isoformat() if until else None,
        "code": code,
    }


def _get_regs_state(context) -> dict:
    return context.user_data.get(REGS_STATE_KEY) or {}


def _range_dates(state: dict) -> tuple[date | None, date | None]:
    since = date.fromisoformat(state["since"]) if state.get("since") else None
    until = date.fromisoformat(state["until"]) if state.get("until") else None
    return since, until


def _range_desc(state: dict) -> str:
    code = state.get("code") or ""
    if code == "all":
        return content.ADMIN_RANGE_ALL_DESC
    if code == "today":
        return content.ADMIN_RANGE_TODAY_DESC
    if code in ("7", "30", "90"):
        return content.ADMIN_RANGE_DAYS_DESC.format(days=to_fa(code))
    since, until = _range_dates(state)
    if since is None and until is None:
        return content.ADMIN_RANGE_ALL_DESC
    if since == until == date.today():
        return content.ADMIN_RANGE_TODAY_DESC
    if since and until:
        return content.ADMIN_RANGE_CUSTOM_DESC.format(
            since=to_fa(format_jalali(since)), until=to_fa(format_jalali(until))
        )
    if since:
        return content.ADMIN_RANGE_CUSTOM_DESC.format(
            since=to_fa(format_jalali(since)), until="امروز"
        )
    return content.ADMIN_RANGE_CUSTOM_DESC.format(since="ابتدا", until=to_fa(format_jalali(until)))


def _regs_page_text(seminar: dict, state: dict) -> str:
    since, until = _range_dates(state)
    total, done = seminars.count_registrations(seminar["id"], since=since, until=until)
    return (
        content.ADMIN_REGS_HEADER.format(title=_esc(seminar["title"]))
        + content.ADMIN_REGS_RANGE_LINE.format(desc=_range_desc(state))
        + content.ADMIN_REGS_COUNT_LINE.format(
            total=fa_num(total), done=fa_num(done), partial=fa_num(total - done)
        )
        + content.ADMIN_REGS_EXPORT_HINT
    )


async def admin_regs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    sid = int(update.callback_query.data.split(":")[2])
    seminar = seminars.get_seminar(sid)
    if seminar is None:
        await update.callback_query.answer(content.SEM_NOT_FOUND_TEXT)
        return
    await update.callback_query.answer()
    await _clear_admin_states(context)
    _set_regs_state(context, sid, None, None, code="all")
    await navigation.render_screen(
        update,
        context,
        text=_regs_page_text(seminar, _get_regs_state(context)),
        reply_markup=keyboards.regs_page(sid),
    )


async def admin_range_quick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بازه‌های آماده: امروز/۷/۳۰/۹۰/همه/دلخواه."""
    if not await _require_admin(update, context):
        return
    code = update.callback_query.data.split(":")[2]
    state = _get_regs_state(context)
    seminar = seminars.get_seminar(state.get("seminar_id", 0))
    if seminar is None:
        await update.callback_query.answer(content.SEM_NOT_FOUND_TEXT)
        return

    if code == "custom":
        await update.callback_query.answer()
        context.user_data[RANGE_STATE_KEY] = {"seminar_id": seminar["id"]}
        await navigation.render_screen(update, context, text=content.ADMIN_RANGE_CUSTOM_PROMPT)
        return

    today = date.today()
    quick = {
        "today": (today, today),
        "7": (today - timedelta(days=6), today),
        "30": (today - timedelta(days=29), today),
        "90": (today - timedelta(days=89), today),
        "all": (None, None),
    }
    since, until = quick.get(code, (None, None))
    await update.callback_query.answer()
    _set_regs_state(context, seminar["id"], since, until, code=code)
    await navigation.render_screen(
        update,
        context,
        text=_regs_page_text(seminar, _get_regs_state(context)),
        reply_markup=keyboards.regs_page(seminar["id"]),
    )


async def _handle_range_input(update, context) -> None:
    """بازه‌ی دلخواه: «۱۴۰۵/۰۷/۰۱ تا ۱۴۰۵/۰۷/۱۵» (هر دو طرف اختیاری)."""
    state = context.user_data.pop(RANGE_STATE_KEY)
    seminar = seminars.get_seminar(state["seminar_id"])
    if seminar is None:
        await navigation.render_screen(update, context, text=content.SEM_NOT_FOUND_TEXT)
        return

    raw = (update.message.text or "").strip()
    left, sep, right = raw.partition("تا")
    since = parse_jalali_text(left.strip())
    until = parse_jalali_text(right.strip()) if sep else None
    if (left.strip() and since is None) or (sep and right.strip() and until is None):
        context.user_data[RANGE_STATE_KEY] = state
        await navigation.render_screen(update, context, text=content.ADMIN_RANGE_INVALID)
        return

    _set_regs_state(context, seminar["id"], since, until)
    await navigation.render_screen(
        update,
        context,
        text=_regs_page_text(seminar, _get_regs_state(context)),
        reply_markup=keyboards.regs_page(seminar["id"]),
    )


async def admin_regs_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """خروجی پیامِ لیست ثبت‌نام‌ها."""
    if not await _require_admin(update, context):
        return
    sid = int(update.callback_query.data.split(":")[3])
    seminar = seminars.get_seminar(sid)
    state = _get_regs_state(context)
    if seminar is None or state.get("seminar_id") != sid:
        await update.callback_query.answer(content.SEM_NOT_FOUND_TEXT)
        return
    await update.callback_query.answer()
    since, until = _range_dates(state)
    regs = seminars.list_registrations(sid, since=since, until=until)
    total, done = seminars.count_registrations(sid, since=since, until=until)

    if not regs:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.ADMIN_REGS_EMPTY
        )
        return

    lines = [
        content.ADMIN_REGS_MSG_HEADER.format(
            title=_esc(seminar["title"]), range_desc=_range_desc(state)
        )
    ]
    for i, reg in enumerate(regs, 1):
        parts = [f"{fa_num(i)}. {_esc(reg['name'])}"]
        parts += [
            _esc(reg["grade"] or "—"),
            _esc(reg["field"] or "—"),
            _esc(reg["city"] or "—"),
            f"تلگرام: {_esc(reg['phone'] or '—')}",
            f"شماره جایگزین: {_esc(reg['alternate_phone'] or '—')}",
        ]
        status = "✅" if reg["is_complete"] else "⏳"
        lines.append(" • ".join(parts) + f" {status}")
    lines.append(
        content.ADMIN_REGS_MSG_FOOTER.format(
            total=fa_num(total), done=fa_num(done), partial=fa_num(total - done)
        )
    )
    # بلوک‌های ۴۰تایی تا سقف پیام تلگرام
    for chunk_start in range(0, len(lines), 41):
        chunk = lines[chunk_start : chunk_start + 41]
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="\n".join(chunk), parse_mode=ParseMode.HTML
        )


async def admin_regs_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """CSV همه‌ی ثبت‌نام‌های سمینار (کامل و نیمه‌کاره)."""
    await _admin_regs_export(update, context, completed_only=False, excel=False)


async def admin_regs_csv_complete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """CSV فقط ثبت‌نام‌های کامل‌شده‌ی سمینار."""
    await _admin_regs_export(update, context, completed_only=True, excel=False)


async def admin_regs_xlsx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """فایل واقعی Excel شامل همه‌ی ثبت‌نام‌های سمینار."""
    await _admin_regs_export(update, context, completed_only=False, excel=True)


async def admin_regs_xlsx_complete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """فایل واقعی Excel فقط برای ثبت‌نام‌های کامل‌شده."""
    await _admin_regs_export(update, context, completed_only=True, excel=True)


async def _admin_regs_export(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    completed_only: bool,
    excel: bool,
) -> None:
    if not await _require_admin(update, context):
        return
    sid = int(update.callback_query.data.split(":")[3])
    seminar = seminars.get_seminar(sid)
    state = _get_regs_state(context)
    if seminar is None or state.get("seminar_id") != sid:
        await update.callback_query.answer(content.SEM_NOT_FOUND_TEXT)
        return
    await update.callback_query.answer()
    since, until = _range_dates(state)
    regs = seminars.list_registrations(sid, since=since, until=until, completed_only=completed_only)
    if not regs:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.ADMIN_REGS_EMPTY
        )
        return

    headers = [
        "ردیف",
        "نام",
        "پایه",
        "رشته",
        "شهر",
        "شماره تلگرام",
        "شماره جایگزین",
        "وضعیت",
        "تاریخ ثبت",
    ]
    rows = [
        [
            index,
            reg["name"],
            reg["grade"],
            reg["field"],
            reg["city"],
            reg["phone"],
            reg["alternate_phone"],
            "کامل" if reg["is_complete"] else "نیمه‌کاره",
            reg["created_at"],
        ]
        for index, reg in enumerate(regs, 1)
    ]
    suffix = "completed" if completed_only else "all"
    if excel:
        document = xlsx_bytes(headers, rows, sheet_name="ثبت‌نام‌ها")
        filename = f"seminar-{sid}-registrations-{suffix}.xlsx"
    else:
        buffer = io.StringIO()
        buffer.write("\ufeff")  # BOM برای نمایش درست فارسی در Excel
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(rows)
        document = buffer.getvalue().encode("utf-8")
        filename = f"seminar-{sid}-registrations-{suffix}.csv"

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(document),
        filename=filename,
    )


async def admin_users_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """CSV همه‌ی افرادی که ربات را استارت کرده‌اند."""
    if not await _require_admin(update, context):
        return
    await update.callback_query.answer()
    rows = users.list_users()
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(["شناسه تلگرام", "نام", "نام کاربری", "زمان شروع", "آخرین بازدید"])
    for row in rows:
        writer.writerow(
            [
                row["user_id"],
                row["first_name"],
                row["username"],
                row["started_at"],
                row["last_seen"],
            ]
        )
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(buffer.getvalue().encode("utf-8")),
        filename="users-started.csv",
    )


async def admin_users_xlsx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """فایل Excel برای همه‌ی افرادی که ربات را استارت کرده‌اند."""
    if not await _require_admin(update, context):
        return
    await update.callback_query.answer()
    rows = users.list_users()
    document = xlsx_bytes(
        ["شناسه تلگرام", "نام", "نام کاربری", "زمان شروع", "آخرین بازدید"],
        [
            [
                row["user_id"],
                row["first_name"],
                row["username"],
                row["started_at"],
                row["last_seen"],
            ]
            for row in rows
        ],
        sheet_name="کاربران",
    )
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(document),
        filename="users-started.xlsx",
    )


# ---------------------------------------------------------------------------
# خروجی‌های سراسری اکسل: لیدهای دارای شماره و شروع فرم ثبت‌نام
# ---------------------------------------------------------------------------


_EXPORT_KIND_TITLES = {
    "leads": "لید تماس",
    "starts": "شروع‌های ثبت‌نام",
}

_EXPORT_STEP_LABELS = {
    seminars.STEP_NAME: "در انتظار نام",
    seminars.STEP_GRADE: "در انتظار انتخاب پایه",
    seminars.STEP_FIELD: "در انتظار انتخاب رشته",
    seminars.STEP_CITY: "در انتظار ثبت شهر",
    seminars.STEP_PHONE: "در انتظار ثبت شماره تماس",
    seminars.STEP_ALTERNATE_PHONE: "در انتظار تأیید/شماره جایگزین",
    seminars.STEP_DONE: "تکمیل‌شده",
}


def _parse_export_datetime_range(raw: str) -> tuple[datetime, datetime] | None:
    """پارس بازهٔ شمسی/میلادی با ساعت؛ دقیقهٔ پایان هم کامل در بازه است."""
    left, separator, right = (raw or "").partition("تا")
    if not separator:
        return None
    left, right = to_en(left).strip(), to_en(right).strip()
    if not left or not right or not any(sep in left for sep in (" ", "T")):
        return None
    if not any(sep in right for sep in (" ", "T")):
        return None
    since, until = parse_datetime_text(left), parse_datetime_text(right)
    if since is None or until is None or until < since:
        return None
    # زمان ورودی تا دقت دقیقه است؛ دقیقهٔ انتخاب‌شده را به طور کامل شامل کن.
    return since, until + timedelta(minutes=1)


def _export_datetime_text(value: str | None) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return f"{to_fa(format_jalali(parsed.date()))} {to_fa(parsed.strftime('%H:%M'))}"


def _export_workbook(kind: str, rows: list[dict]) -> tuple[bytes, str, str]:
    if kind == "leads":
        headers = [
            "ردیف",
            "شناسه تلگرام",
            "نام",
            "شماره تماس",
            "شماره جایگزین",
            "سمینار",
            "پایه",
            "رشته",
            "شهر",
            "وضعیت فرم",
            "تاریخ و ساعت شروع ثبت‌نام",
        ]
        values = [
            [
                index,
                row["user_id"],
                row["name"] or row["telegram_first_name"] or "—",
                row["phone"],
                row["alternate_phone"],
                row["seminar_title"] or "—",
                row["grade"],
                row["field"],
                row["city"],
                "کامل" if row["is_complete"] else "نیمه‌کاره",
                _export_datetime_text(row["created_at"]),
            ]
            for index, row in enumerate(rows, 1)
        ]
        return (
            xlsx_bytes(headers, values, sheet_name="لیدهای تماس"),
            "contact-leads.xlsx",
            "خروجی لیدهای دارای شماره تماس",
        )

    headers = [
        "ردیف",
        "شناسه تلگرام",
        "نام ثبت‌شده",
        "نام تلگرام",
        "نام کاربری",
        "سمینار",
        "مرحله فعلی",
        "شماره تماس",
        "شماره جایگزین",
        "وضعیت ثبت‌نام",
        "تاریخ و ساعت شروع ثبت‌نام",
    ]
    values = [
        [
            index,
            row["user_id"],
            row["name"] or "—",
            row["telegram_first_name"] or "—",
            row["telegram_username"] or "—",
            row["seminar_title"] or "—",
            _EXPORT_STEP_LABELS.get(row["current_step"], row["current_step"] or "—"),
            row["phone"] or "—",
            row["alternate_phone"] or "—",
            "کامل" if row["is_complete"] else "نیمه‌کاره",
            _export_datetime_text(row["created_at"]),
        ]
        for index, row in enumerate(rows, 1)
    ]
    return (
        xlsx_bytes(headers, values, sheet_name="شروع‌های ثبت‌نام"),
        "registration-starts.xlsx",
        "خروجی تمام شروع‌های فرم ثبت‌نام؛ شامل موارد نیمه‌کاره",
    )


async def _send_registration_export(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    kind: str,
    since: datetime | None = None,
    until_exclusive: datetime | None = None,
) -> None:
    if kind == "leads":
        rows = seminars.list_contact_leads(since=since, until_exclusive=until_exclusive)
    else:
        rows = seminars.list_registration_starts(since=since, until_exclusive=until_exclusive)

    if not rows:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.ADMIN_EXPORT_EMPTY
        )
    else:
        document, filename, caption = _export_workbook(kind, rows)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=io.BytesIO(document),
            filename=filename,
            caption=caption,
        )

    context.user_data.pop(EXPORT_RANGE_STATE_KEY, None)
    await navigation.render_screen(
        update,
        context,
        text=_overview_text(),
        reply_markup=keyboards.overview(reminders_on=reminders.enabled()),
    )


async def admin_export_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """شروع انتخاب بازه برای یکی از دو خروجی اکسل."""
    if not await _require_admin(update, context):
        return
    kind = update.callback_query.data.rsplit(":", 1)[-1]
    if kind not in _EXPORT_KIND_TITLES:
        await update.callback_query.answer()
        return
    await _clear_admin_states(context)
    context.user_data[EXPORT_RANGE_STATE_KEY] = kind
    await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=content.ADMIN_EXPORT_RANGE_PROMPT.format(title=_EXPORT_KIND_TITLES[kind]),
        reply_markup=keyboards.export_range_prompt(kind),
    )


async def admin_export_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ارسال خروجی بدون محدودیت تاریخ."""
    if not await _require_admin(update, context):
        return
    kind = context.match.group(1)
    await update.callback_query.answer()
    await _send_registration_export(update, context, kind=kind)


async def admin_export_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    context.user_data.pop(EXPORT_RANGE_STATE_KEY, None)
    await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=_overview_text(),
        reply_markup=keyboards.overview(reminders_on=reminders.enabled()),
    )


async def _handle_export_range_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kind = context.user_data.get(EXPORT_RANGE_STATE_KEY)
    if kind not in _EXPORT_KIND_TITLES:
        context.user_data.pop(EXPORT_RANGE_STATE_KEY, None)
        return
    parsed = _parse_export_datetime_range(update.message.text or "")
    if parsed is None:
        await navigation.render_screen(
            update,
            context,
            text=(
                content.ADMIN_EXPORT_RANGE_INVALID
                + "\n\n"
                + content.ADMIN_EXPORT_RANGE_PROMPT.format(title=_EXPORT_KIND_TITLES[kind])
            ),
            reply_markup=keyboards.export_range_prompt(kind),
        )
        return
    since, until_exclusive = parsed
    await _send_registration_export(
        update,
        context,
        kind=kind,
        since=since,
        until_exclusive=until_exclusive,
    )


# ---------------------------------------------------------------------------
# پیام همگانی (broadcast) به همه‌ی کاربرانی که ربات را استارت کرده‌اند
# ---------------------------------------------------------------------------


def _bcast_preview(update: Update) -> str:
    """پیش‌نمایش کوتاه پیام مدیر برای صفحه‌ی تأیید."""
    message = update.message
    if message is None:
        return "—"
    if message.text:
        return _truncate(message.text, 160)
    for attr, label in (
        ("photo", "📷 عکس"),
        ("video", "🎬 ویدیو"),
        ("document", "📎 فایل"),
        ("audio", "🎵 موسیقی"),
        ("voice", "🎤 پیام صوتی"),
        ("video_note", "🎞 ویدیو-پیام"),
        ("sticker", "🌟 استیکر"),
        ("animation", "🎞 GIF"),
    ):
        if getattr(message, attr, None):
            caption = f" با متن «{_truncate(message.caption or '', 60)}»" if message.caption else ""
            return f"{label}{caption}"
    return "📨 پیام"


async def admin_bcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """شروع پیام همگانی: مدیر پیام بعدی‌اش برای همه ارسال می‌شود."""
    if not await _require_admin(update, context):
        return
    context.user_data[BCAST_STATE_KEY] = True
    await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=content.BCAST_PROMPT,
        reply_markup=keyboards.bcast_prompt(),
    )


async def admin_bcast_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دریافت پیام مدیر (متن/عکس/ویدیو/فوروارد) و نمایش تأییدیه."""
    message = update.message
    if message is None:
        return
    context.user_data[BCAST_STATE_KEY] = {
        "chat_id": message.chat_id,
        "message_id": message.message_id,
    }
    count = users.count_users()
    if count == 0:
        context.user_data.pop(BCAST_STATE_KEY, None)  # state پاک شود
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=content.BCAST_EMPTY_TEXT,
        )
        raise ApplicationHandlerStop
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=content.BCAST_CONFIRM_TEXT.format(
            count=fa_num(count), preview=_esc(_bcast_preview(update))
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.bcast_confirm(fa_num(count)),
    )
    raise ApplicationHandlerStop  # پیام مصرف شد؛ به هندلرهای بعدی نرسد


async def _bcast_send_all(context: ContextTypes.DEFAULT_TYPE, state: dict) -> tuple[int, int]:
    """ارسال کپی پیام مدیر از صف انبوه — نرخ ۵ در ثانیه + هندل 429."""
    targets = users.all_user_ids()
    futures = [
        sender.submit(
            lambda uid=user_id: context.bot.copy_message(
                chat_id=uid,
                from_chat_id=state["chat_id"],
                message_id=state["message_id"],
            )
        )
        for user_id in targets
    ]
    ok = 0
    for future in futures:
        if future is not None and await future:
            ok += 1
    return ok, len(targets) - ok


async def admin_bcast_go(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تأیید ارسال همگانی → ارسال به همه + گزارش."""
    if not await _require_admin(update, context):
        return
    state = context.user_data.pop(BCAST_STATE_KEY, None)
    if not state or "message_id" not in state:
        await update.callback_query.answer()
        return
    await update.callback_query.answer(content.BCAST_SENDING_ANSWER)
    ok, fail = await _bcast_send_all(context, state)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=content.BCAST_REPORT_TEXT.format(ok=fa_num(ok), fail=fa_num(fail)),
        parse_mode=ParseMode.HTML,
    )
    await navigation.render_screen(
        update,
        context,
        text=_overview_text(),
        reply_markup=keyboards.overview(reminders_on=reminders.enabled()),
    )


async def admin_bcast_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """انصراف از ارسال همگانی."""
    if not await _require_admin(update, context):
        return
    context.user_data.pop(BCAST_STATE_KEY, None)
    await update.callback_query.answer(content.BCAST_CANCEL_ANSWER)
    await navigation.render_screen(
        update,
        context,
        text=_overview_text(),
        reply_markup=keyboards.overview(reminders_on=reminders.enabled()),
    )


# ---------------------------------------------------------------------------
# دیسپچر واحد ورودی مدیر (گروه ۰ — متن و رسانه)
# ---------------------------------------------------------------------------


async def admin_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """همه‌ی ورودی‌های مدیر: پیام همگانی (هر نوع پیام) + state های متنی."""
    if context.user_data.get(WIDE_INVITE_STATE_KEY):
        from bot.handlers.wide_admin import handle_owner_input  # noqa: PLC0415

        await handle_owner_input(update, context)
        raise ApplicationHandlerStop
    if context.user_data.get(BCAST_STATE_KEY):
        await admin_bcast_input(update, context)  # خودش ApplicationHandlerStop می‌دهد
        return
    if context.user_data.get(ABOUT_STATE_KEY):
        await _handle_about_input(update, context)
        raise ApplicationHandlerStop
    if context.user_data.get(REF_STATE_KEY):
        await _handle_ads_label_input(update, context)
        raise ApplicationHandlerStop
    if context.user_data.get(EXPORT_RANGE_STATE_KEY):
        kind = context.user_data[EXPORT_RANGE_STATE_KEY]
        if update.message is not None and update.message.text is not None:
            await _handle_export_range_input(update, context)
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    content.ADMIN_EXPORT_RANGE_INVALID
                    + "\n\n"
                    + content.ADMIN_EXPORT_RANGE_PROMPT.format(
                        title=_EXPORT_KIND_TITLES.get(kind, "خروجی")
                    )
                ),
                reply_markup=keyboards.export_range_prompt(kind),
            )
        raise ApplicationHandlerStop
    if update.message is None or update.message.text is None:
        return  # رسانه‌ی بدون state فعال → نادیده گرفته می‌شود
    if context.user_data.get(NEW_STATE_KEY):
        await _handle_new_input(update, context)
        raise ApplicationHandlerStop
    if context.user_data.get(EDIT_STATE_KEY):
        await _handle_edit_input(update, context)
        raise ApplicationHandlerStop
    if context.user_data.get(RANGE_STATE_KEY):
        await _handle_range_input(update, context)
        raise ApplicationHandlerStop
    # بدون state → به گروه‌های بعدی (ویزارد/fallback) واگذار می‌شود


class _AdminFilter(filters.MessageFilter):
    """فقط پیام‌های مدیران."""

    def filter(self, message) -> bool:
        user = message.from_user
        return bool(user and user.id in get_settings().admin_ids)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(admin_sems, pattern=PATTERN_ADMIN_SEMS))
    app.add_handler(CallbackQueryHandler(admin_sem_new, pattern=PATTERN_ADMIN_SEM_NEW))
    app.add_handler(CallbackQueryHandler(admin_sem_page, pattern=PATTERN_ADMIN_SEM_PAGE))
    app.add_handler(CallbackQueryHandler(admin_sem_edit, pattern=PATTERN_ADMIN_SEM_EDIT))
    app.add_handler(
        CallbackQueryHandler(admin_sem_edit_field, pattern=PATTERN_ADMIN_SEM_EDIT_FIELD)
    )
    app.add_handler(CallbackQueryHandler(admin_sem_open, pattern=PATTERN_ADMIN_SEM_OPEN))
    app.add_handler(CallbackQueryHandler(admin_sem_delete, pattern=PATTERN_ADMIN_SEM_DELETE))
    app.add_handler(CallbackQueryHandler(admin_sem_delete2, pattern=PATTERN_ADMIN_SEM_DELETE2))
    app.add_handler(CallbackQueryHandler(admin_ads, pattern=PATTERN_ADMIN_ADS))
    app.add_handler(CallbackQueryHandler(admin_ads_new, pattern=PATTERN_ADMIN_ADS_NEW))
    app.add_handler(CallbackQueryHandler(admin_ads_view, pattern=PATTERN_ADMIN_ADS_VIEW))
    app.add_handler(CallbackQueryHandler(admin_ads_delete_prompt, pattern=PATTERN_ADMIN_ADS_DELETE))
    app.add_handler(CallbackQueryHandler(admin_ads_delete, pattern=PATTERN_ADMIN_ADS_DELETE2))
    app.add_handler(CallbackQueryHandler(admin_ads_toggle, pattern=PATTERN_ADMIN_ADS_TOGGLE))
    app.add_handler(CallbackQueryHandler(admin_ads_msg, pattern=PATTERN_ADMIN_ADS_MSG))
    app.add_handler(CallbackQueryHandler(admin_ads_regs, pattern=PATTERN_ADMIN_ADS_REGS))
    app.add_handler(CallbackQueryHandler(admin_ads_regs_csv, pattern=PATTERN_ADMIN_ADS_REGS_CSV))
    app.add_handler(CallbackQueryHandler(admin_ads_regs_xlsx, pattern=PATTERN_ADMIN_ADS_REGS_XLSX))
    app.add_handler(
        CallbackQueryHandler(admin_ads_reset_phrase, pattern=PATTERN_ADMIN_ADS_RESET_PHRASE)
    )
    app.add_handler(CallbackQueryHandler(admin_ads_kick, pattern=PATTERN_ADMIN_ADS_KICK))
    app.add_handler(CallbackQueryHandler(admin_ads_csv, pattern=PATTERN_ADMIN_ADS_CSV))
    app.add_handler(CallbackQueryHandler(admin_ads_xlsx, pattern=PATTERN_ADMIN_ADS_XLSX))
    app.add_handler(CallbackQueryHandler(admin_regs, pattern=PATTERN_ADMIN_REGS))
    app.add_handler(CallbackQueryHandler(admin_regs_msg, pattern=PATTERN_ADMIN_REGS_MSG))
    app.add_handler(CallbackQueryHandler(admin_regs_csv, pattern=PATTERN_ADMIN_REGS_CSV))
    app.add_handler(
        CallbackQueryHandler(admin_regs_csv_complete, pattern=PATTERN_ADMIN_REGS_CSV_COMPLETE)
    )
    app.add_handler(CallbackQueryHandler(admin_regs_xlsx, pattern=PATTERN_ADMIN_REGS_XLSX))
    app.add_handler(
        CallbackQueryHandler(admin_regs_xlsx_complete, pattern=PATTERN_ADMIN_REGS_XLSX_COMPLETE)
    )
    app.add_handler(CallbackQueryHandler(admin_users_csv, pattern=PATTERN_ADMIN_USERS_CSV))
    app.add_handler(CallbackQueryHandler(admin_users_xlsx, pattern=PATTERN_ADMIN_USERS_XLSX))
    app.add_handler(CallbackQueryHandler(admin_export_prompt, pattern=PATTERN_ADMIN_EXPORT_LEADS))
    app.add_handler(CallbackQueryHandler(admin_export_prompt, pattern=PATTERN_ADMIN_EXPORT_STARTS))
    app.add_handler(CallbackQueryHandler(admin_export_all, pattern=PATTERN_ADMIN_EXPORT_ALL))
    app.add_handler(CallbackQueryHandler(admin_export_cancel, pattern=PATTERN_ADMIN_EXPORT_CANCEL))
    app.add_handler(CallbackQueryHandler(admin_range_quick, pattern=PATTERN_ADMIN_RANGE))
    app.add_handler(CallbackQueryHandler(admin_bcast, pattern=PATTERN_ADMIN_BCAST))
    app.add_handler(CallbackQueryHandler(admin_bcast_go, pattern=PATTERN_ADMIN_BCAST_GO))
    app.add_handler(CallbackQueryHandler(admin_bcast_no, pattern=PATTERN_ADMIN_BCAST_NO))
    app.add_handler(CallbackQueryHandler(admin_reminders_toggle, pattern=PATTERN_ADMIN_REMINDERS))
    app.add_handler(CallbackQueryHandler(admin_about_edit, pattern=PATTERN_ADMIN_ABOUT))
    # دیسپچر واحد ورودی مدیر (گروه ۰ — متن و رسانه؛ قبل از ویزارد و fallback)
    app.add_handler(
        MessageHandler(~filters.COMMAND & _AdminFilter(), admin_message_input),
        group=0,
    )
