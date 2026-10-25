"""هندلر خطای سراسری + پیام پیش‌فرض برای ورودی‌های بدون هندلر."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import content

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ثبت خطا و اطلاع به کاربر (در صورت امکان)."""
    logger.error("خطا در پردازش آپدیت", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=content.ERROR_TEXT
            )
        except TelegramError:
            pass


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پاسخ پیش‌فرض به متن‌های بدون معنی."""
    await context.bot.send_message(chat_id=update.effective_chat.id, text=content.FALLBACK_TEXT)


def register(app: Application) -> None:
    # گروه ۲ — آخرین هندلر متنی، بعد از ویزارد (۱) و پنل ادمین (۰)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback), group=2)
    app.add_error_handler(error_handler)
