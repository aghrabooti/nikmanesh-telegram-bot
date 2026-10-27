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


async def render_saved_screen(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int | None,
    message_id: int | None,
    text: str,
    reply_markup=None,
) -> None:
    """Edit a saved bot prompt after a text reply; fall back to a fresh screen."""
    if chat_id is not None and message_id is not None:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        except TelegramError as exc:
            if "not modified" in str(exc).lower():
                return
        else:
            return
    await render_screen(update, context, text=text, reply_markup=reply_markup)
