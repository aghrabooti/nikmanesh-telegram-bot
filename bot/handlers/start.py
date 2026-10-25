"""شروع، منوی اصلی و فرمان /id."""

from __future__ import annotations

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from bot import navigation
from bot.config import content
from bot.constants import PATTERN_MAIN, REF_START_PREFIX
from bot.keyboards import user as user_keyboards
from bot.services import referrals, users


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ورود کاربر — پیام خوش‌آمد + دکمه‌ی شیشه‌ای وبینار فعال + منوی ثابت.

    ورود با لینک رفرال (t.me/<bot>?start=ref_<کد>) فقط اتریبیوشن first-touch
    را ثبت می‌کند؛ بقیه‌ی جریان مثل استارت عادی است.

    تلگرام اجازه نمی‌دهد اینلاین و ریپلای کیبورد در یک پیام باشند؛
    پس منوی ثابت در پیام کوتاهِ بعدی ست می‌شود.
    """
    user = update.effective_user
    users.ensure_user(user.id, first_name=user.first_name or "", username=user.username or "")
    payload = context.args[0] if context.args else ""
    if payload.startswith(REF_START_PREFIX):
        referrals.attribute_start(user.id, payload[len(REF_START_PREFIX) :])
    await navigation.render_screen(
        update,
        context,
        text=content.WELCOME_TEXT,
        reply_markup=user_keyboards.start_inline(),
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=content.MENU_HINT_TEXT,
        reply_markup=user_keyboards.reply_menu(),
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """نمایش شناسه‌ی کاربر (برای تنظیم ADMIN_IDS)."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=content.ID_TEXT.format(user_id=update.effective_user.id),
        parse_mode="HTML",
    )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بازگشت به پیام خوش‌آمد (دکمه‌ی 🏠 در صفحات اینلاین مثل پنل ادمین)."""
    await update.callback_query.answer()
    await navigation.render_screen(
        update, context, text=content.WELCOME_TEXT, reply_markup=user_keyboards.start_inline()
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler(["start", "menu"], start_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CallbackQueryHandler(main_menu, pattern=PATTERN_MAIN))
