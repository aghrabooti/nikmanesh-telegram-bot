"""دکمه‌های ثابت منوی کاربر (ریپلای کیبورد): وبینار فعال، درباره، ارتباط با ما."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import content
from bot.handlers.seminars import render_seminar_screen
from bot.keyboards import user as user_keyboards
from bot.services import seminars, settings


async def _send_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """ارسال یک صفحه‌ی ساده همراه با منوی ثابت."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=user_keyboards.reply_menu(),
    )


async def menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پاسخ به سه دکمه‌ی ثابت — گروه ۱، قبل از ویزارد.

    فیلتر هندلر فقط همین سه متن را می‌گیرد تا بقیه‌ی متن‌ها به ویزارد برسند
    (در هر گروه فقط اولین هندلرِ منطبق اجرا می‌شود).
    """
    text = (update.message.text or "").strip()

    if text == content.LBL_ABOUT:
        await _send_screen(update, context, settings.get_about_text())
    elif text == content.LBL_CONTACT:
        await _send_screen(update, context, content.CONTACT_TEXT)
    else:  # «وبینار …» — تطبیق با هر سمینار باز (کلیدهای قدیمی هم کار می‌کنند)
        target = None
        for seminar in seminars.list_seminars(open_only=True):
            if text == content.LBL_WEBINAR.format(title=seminar["title"]):
                target = seminar
                break
        if target is None:
            # کلید قدیمی/نامعتبر → منوی تازه با نام وبینار فعلی
            await _send_screen(update, context, content.WELCOME_TEXT)
        else:
            await render_seminar_screen(update, context, target["id"])
    raise ApplicationHandlerStop


def _menu_filter():
    """فقط متنِ سه دکمه‌ی ثابت (درباره/ارتباط دقیق، وبینار با پیشوند)."""
    return filters.Text([content.LBL_ABOUT, content.LBL_CONTACT]) | filters.Regex("^وبینار")


def register(app: Application) -> None:
    app.add_handler(MessageHandler(_menu_filter(), menu_buttons), group=1)
