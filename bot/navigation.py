"""رندر یکنواخت صفحه‌ها — ویرایش برای callback، ارسال برای پیام تازه."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes


async def render_screen(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    reply_markup=None,
) -> None:
    """نمایش یک صفحه: اگر آپدیت callback بود همان پیام ویرایش می‌شود، وگرنه پیام جدید."""
    query = update.callback_query
    if query is not None:
        try:
            await query.edit_message_text(
                text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup
            )
        except TelegramError as exc:
            if "not modified" not in str(exc).lower():
                raise
        return
    if update.effective_chat is not None:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
