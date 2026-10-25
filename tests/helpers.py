"""ابزار ساخت آپدیت‌های تستی و خواندن خروجی‌های بات ماک."""

from __future__ import annotations

import itertools
from datetime import datetime, timezone

from telegram import (
    CallbackQuery,
    Chat,
    Contact,
    InlineKeyboardMarkup,
    Message,
    MessageEntity,
    PhotoSize,
    Update,
    User,
)

# کاربران تستی: 777 = مدیر، 555 = کاربر عادی
USER = User(id=777, first_name="Tester", is_bot=False)
NON_ADMIN = User(id=555, first_name="Guest", is_bot=False)
CHAT = Chat(id=USER.id, type=Chat.PRIVATE)
NON_ADMIN_CHAT = Chat(id=NON_ADMIN.id, type=Chat.PRIVATE)

_ids = itertools.count(1000)


def _next_id() -> int:
    return next(_ids)


def make_message(text=None, *, user=USER, chat=None, **kwargs) -> Message:
    """پیام متنی/رسانه‌ای ساختگی."""
    msg = Message(
        message_id=_next_id(),
        date=datetime.now(tz=timezone.utc),
        chat=chat or (NON_ADMIN_CHAT if user.id == NON_ADMIN.id else CHAT),
        from_user=user,
        text=text,
        **kwargs,
    )
    return msg


async def send_text(app, bot, text, *, user=USER) -> None:
    msg = make_message(text, user=user)
    msg.set_bot(bot)
    await app.process_update(Update(update_id=_next_id(), message=msg))


async def send_command(app, bot, text, *, user=USER) -> None:
    """فرمان مثل «/start» — با entity لازم برای CommandHandler."""
    cmd, _, _rest = text.partition(" ")
    msg = make_message(
        text,
        user=user,
        entities=[MessageEntity(type=MessageEntity.BOT_COMMAND, offset=0, length=len(cmd))],
    )
    msg.set_bot(bot)
    await app.process_update(Update(update_id=_next_id(), message=msg))


async def tap(app, bot, data, *, user=USER) -> None:
    """فشردن یک دکمه‌ی inline."""
    msg = make_message("screen", user=user)
    msg.set_bot(bot)
    cq = CallbackQuery(
        id=str(_next_id()),
        from_user=user,
        chat_instance="test",
        data=data,
        message=msg,
    )
    cq.set_bot(bot)
    await app.process_update(Update(update_id=_next_id(), callback_query=cq))


async def share_contact(app, bot, *, user=USER, phone="+989121234567") -> None:
    """ارسال مخاطب (دکمه‌ی اشتراک شماره)."""
    contact = Contact(phone_number=phone, first_name=user.first_name, user_id=user.id)
    msg = make_message(None, user=user, contact=contact)
    msg.set_bot(bot)
    await app.process_update(Update(update_id=_next_id(), message=msg))


async def send_photo_message(app, bot, *, user=USER, caption="") -> None:
    """ارسال یک پیام عکس (برای تست پیام همگانی رسانه‌دار)."""
    photo = PhotoSize(
        file_id="AgACAgFAKEphoto", file_unique_id="AgACAgFAKEphoto:uniq", width=800, height=600
    )
    msg = make_message(None, user=user, photo=[photo], caption=caption or None)
    msg.set_bot(bot)
    await app.process_update(Update(update_id=_next_id(), message=msg))


# ── خواندن آخرین خروجی‌های بات ماک ──


def last_send(bot) -> dict:
    return bot.send_message.await_args.kwargs


def last_edit(bot) -> dict:
    return bot.edit_message_text.await_args.kwargs


def last_answer(bot) -> dict:
    return bot.answer_callback_query.await_args.kwargs


def last_document(bot) -> dict:
    return bot.send_document.await_args.kwargs


def texts(bot) -> list[str]:
    return [c.kwargs["text"] for c in bot.send_message.await_args_list]


def edits(bot) -> list[str]:
    return [c.kwargs["text"] for c in bot.edit_message_text.await_args_list]


def callbacks(kb: InlineKeyboardMarkup) -> list[str]:
    return [b.callback_data for row in kb.inline_keyboard for b in row]


def labels(kb: InlineKeyboardMarkup) -> list[str]:
    return [b.text for row in kb.inline_keyboard for b in row]
