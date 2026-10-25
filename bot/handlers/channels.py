"""بخش کانال‌ها (/channels) — دسترسی فقط-آماری برای ادمین‌های کانال.

جریان:
- هر لینک رفرال یک «رمز ورود» دارد که هنگام ساخت تولید می‌شود.
- ادمین کانال (طرف تبلیغ) با /channels رمز را می‌فرستد → به لیست
  کانال‌های مدیریتی‌اش اضافه می‌شود و فقط آمار تجمیعی می‌بیند
  (تعداد ورودی، وضعیت ثبت‌نام، قیف و پایه‌ها) — هیچ اطلاعات
  شخصی (نام/شماره/…) نمایش داده نمی‌شود.
- ورود هر شخص به ادمین ربات اطلاع داده می‌شود؛ ادمین ربات می‌تواند
  رمز را از پنل /admin جدید کند یا شخص را بیرون بیندازد.

نکته‌ی معماری: ورودی رمز (متن غیر-فرمان) در ابتدای ``wizard_text``
(گروه ۱) مصرف می‌شود — تابع :func:`maybe_consume_phrase`.
"""

from __future__ import annotations

from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from bot import navigation
from bot.config import content
from bot.config.settings import get_settings
from bot.constants import CB_MAIN, CHANNELS_STATE_KEY, PATTERN_CH_LINK
from bot.keyboards import user as user_keyboards
from bot.services import referrals, seminars
from bot.utils.persian import to_fa


def _esc(text: str) -> str:
    return escape(text or "")


# ---------------------------------------------------------------------------
# صفحات (فقط آمار تجمیعی — بدون هیچ داده‌ی شخصی)
# ---------------------------------------------------------------------------


def _stats_text(link: dict) -> str:
    """آمار تجمیعی یک لینک برای ادمین کانال — بدون نام/شماره‌ی هیچ کاربری."""
    f = referrals.funnel(int(link["link_id"]))
    starts = f["starts"]
    completed = f["completed"]
    started_form = f["steps"][seminars.STEP_NAME]
    partial = started_form - completed
    pct = (completed * 100 / starts) if starts else 0.0
    grades = " | ".join(f"{g.split()[-1]}: {to_fa(n)}" for g, n in f["grades"].items())
    funnel_parts = [
        f"{referrals.STEP_LABELS[step]} {to_fa(f['steps'][step])}" for step in seminars.STEP_ORDER
    ]
    funnel_parts.append(f"✅ {to_fa(completed)}")
    return "\n".join(
        [
            f"📊 <b>{_esc(link['label'])}</b>",
            "",
            f"👥 تعداد ورودی (استارت): <b>{to_fa(starts)}</b>",
            f"✅ ثبت‌نام کامل: <b>{to_fa(completed)}</b> ({to_fa(f'{pct:.1f}')}٪)",
            f"⏳ نیمه‌کاره: <b>{to_fa(partial)}</b>",
            "",
            "📊 وضعیت مراحل:",
            " ← ".join(funnel_parts),
            f"🎓 {grades}",
        ]
    )


def _list_keyboard(links: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"{'📡' if lnk['is_active'] else '⏸'} {lnk['label']}",
                callback_data=f"ch:l:{lnk['link_id']}",
            )
        ]
        for lnk in links
    ]
    rows.append([InlineKeyboardButton(content.LBL_HOME, callback_data=CB_MAIN)])
    return InlineKeyboardMarkup(rows)


def _link_keyboard(link: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(content.LBL_CH_PAGE_BACK, callback_data="ch:home")],
            [InlineKeyboardButton(content.LBL_HOME, callback_data=CB_MAIN)],
        ]
    )


async def _render_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    links = referrals.user_links(update.effective_user.id)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="\n".join([content.CH_TITLE, "", content.CH_HINT]),
        parse_mode="HTML",
        reply_markup=_list_keyboard(links),
    )


# ---------------------------------------------------------------------------
# ورود با رمز
# ---------------------------------------------------------------------------


def _is_bot_admin(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/channels — ورود ادمین کانال (رمز) یا لیست کانال‌های قبلی."""
    user = update.effective_user
    if _is_bot_admin(user.id):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "🛠 مدیریت کانال‌ها (رمزها، حذف دسترسی، آمار کامل) در پنل"
                " /admin ← «📣 تبلیغات و رفرال» است."
            ),
        )
        return
    if referrals.user_links(user.id):
        context.user_data.pop(CHANNELS_STATE_KEY, None)
        await _render_list(update, context)
        return
    context.user_data[CHANNELS_STATE_KEY] = True
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=content.CH_LOGIN_PROMPT,
        reply_markup=user_keyboards.channels_cancel_keyboard(),
    )


def maybe_consume_phrase(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """آیا این پیام باید به‌عنوان رمز ورود کانال مصرف شود؟"""
    return bool(context.user_data.get(CHANNELS_STATE_KEY))


async def consume_phrase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """مصرف متن به‌عنوان رمز ورود — موفق: دسترسی + اطلاع به ادمین ربات."""
    text = (update.message.text or "").strip()
    user = update.effective_user
    context.user_data.pop(CHANNELS_STATE_KEY, None)

    if text == content.CH_LOGIN_CANCEL_LBL:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=content.CH_NO_ACCESS_YET,
            reply_markup=user_keyboards.reply_menu(),
        )
        return

    link = referrals.find_link_by_phrase(text)
    if link is None:
        context.user_data[CHANNELS_STATE_KEY] = True  # بماند و دوباره بپرسد
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.CH_LOGIN_WRONG
        )
        return
    if not link["is_active"]:
        context.user_data[CHANNELS_STATE_KEY] = True
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.CH_LOGIN_INACTIVE
        )
        return

    # دسترسی ثبت + اطلاع به ادمین‌های ربات
    referrals.add_channel_admin(user.id, int(link["link_id"]))
    await _notify_bot_admins(context, user, link)

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=content.CH_GRANTED.format(label=_esc(link["label"]))
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=_stats_text(link),
        parse_mode="HTML",
        reply_markup=_link_keyboard(link),
    )


async def _notify_bot_admins(context: ContextTypes.DEFAULT_TYPE, user, link: dict) -> None:
    """اطلاع ورود شخص به همه‌ی ادمین‌های ربات."""
    text = content.CH_ADMIN_NOTIFY.format(
        name=_esc(user.first_name or "—"),
        username=_esc(user.username or "—"),
        user_id=user.id,
        label=_esc(link["label"]),
    )
    for admin_id in get_settings().admin_ids:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except TelegramError:
            continue  # ادمین هنوز ربات را استارت نکرده است


# ---------------------------------------------------------------------------
# صفحه‌ی آمار یک کانال (داخل چت ادمین کانال)
# ---------------------------------------------------------------------------


async def channels_link_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """صفحه‌ی آمار تجمیعی یک لینک — فقط برای ادمینِ همان کانال."""
    query = update.callback_query
    link = referrals.get_link(int(context.match.group(1)))
    if link is None or not referrals.is_channel_admin(
        update.effective_user.id, int(link["link_id"])
    ):
        await query.answer(content.CH_ACCESS_DENIED, show_alert=True)
        return
    await query.answer()
    await navigation.render_screen(
        update, context, text=_stats_text(link), reply_markup=_link_keyboard(link)
    )


async def channels_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه‌ی «کانال‌های من» — بازگشت به لیست کانال‌های همین کاربر."""
    query = update.callback_query
    await query.answer()
    links = referrals.user_links(update.effective_user.id)
    await navigation.render_screen(
        update,
        context,
        text="\n".join([content.CH_TITLE, "", content.CH_HINT]),
        reply_markup=_list_keyboard(links),
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("channels", channels_command))
    app.add_handler(CallbackQueryHandler(channels_link_page, pattern=PATTERN_CH_LINK))
    app.add_handler(CallbackQueryHandler(channels_home, pattern=r"^ch:home$"))
