"""ادمین‌های گسترده: دعوت یک‌بارمصرف، مالکیت رفرال‌ها و آمار فقط-تجمیعی."""

from __future__ import annotations

import html
import re

from telegram import Update
from telegram.error import TelegramError
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
    PATTERN_ADMIN_ADS_ASSIGN,
    PATTERN_ADMIN_ADS_OWNER_SET,
    PATTERN_ADMIN_WIDE,
    PATTERN_ADMIN_WIDE_ADD,
    PATTERN_ADMIN_WIDE_REVOKE,
    PATTERN_WIDE_CREATE,
    PATTERN_WIDE_HOME,
    PATTERN_WIDE_KICK,
    PATTERN_WIDE_RESET_PHRASE,
    PATTERN_WIDE_TOGGLE,
    PATTERN_WIDE_VIEW,
    WIDE_INVITE_PROMPT_CHAT_ID_KEY,
    WIDE_INVITE_PROMPT_MESSAGE_ID_KEY,
    WIDE_INVITE_STATE_KEY,
    WIDE_LINK_LABEL_STATE_KEY,
    WIDE_LINK_PROMPT_CHAT_ID_KEY,
    WIDE_LINK_PROMPT_MESSAGE_ID_KEY,
)
from bot.keyboards import admin as admin_keyboards
from bot.keyboards import wide_admin as keyboards
from bot.services import referrals, seminars, wide_admins
from bot.utils.persian import to_en, to_fa


def _esc(value: str) -> str:
    return html.escape(value or "")


def _is_owner(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


async def _require_owner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user and _is_owner(user.id):
        return True
    if update.callback_query:
        await update.callback_query.answer(content.ADMIN_ONLY_TEXT, show_alert=True)
    elif update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.ADMIN_ONLY_TEXT
        )
    return False


async def _require_wide_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user and wide_admins.is_wide_admin(user.id) and not _is_owner(user.id):
        return True
    if update.callback_query:
        await update.callback_query.answer(content.WIDE_LINK_ACCESS_DENIED, show_alert=True)
    elif update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.WIDE_ADMIN_NO_ACCESS
        )
    return False


def _owner_panel_text() -> str:
    admins = wide_admins.list_wide_admins()
    lines = [content.WIDE_ADMINS_TITLE, ""]
    if not admins:
        lines.append(content.WIDE_ADMINS_EMPTY)
    else:
        for item in admins:
            name = _esc(item["first_name"] or "—")
            lines.append(f"• {name} — <code>{item['user_id']}</code>")
        lines.extend(["", "برای لغو دسترسی، دکمهٔ همان ادمین را بزنید."])
    return "\n".join(lines)


async def _render_pending_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_key: str,
    message_key: str,
    text: str,
    reply_markup,
) -> None:
    chat_id = context.user_data.pop(chat_key, None)
    message_id = context.user_data.pop(message_key, None)
    await navigation.render_saved_screen(
        update,
        context,
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=reply_markup,
    )


async def _notify_owners_wide_admin_activated(
    context: ContextTypes.DEFAULT_TYPE, user_id: int
) -> None:
    text = (
        content.WIDE_ADMIN_ACTIVATION_NOTICE.format(user_id=user_id) + "\n\n" + _owner_panel_text()
    )
    reply_markup = keyboards.owner_panel(wide_admins.list_wide_admins())
    for admin_id in get_settings().admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=text, parse_mode="HTML", reply_markup=reply_markup
            )
        except TelegramError:
            continue  # ادمین هنوز چت خصوصی ربات را آغاز نکرده است


async def owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پنل ساخت و لغو ادمین‌های گسترده؛ فقط ADMIN_IDS."""
    if not await _require_owner(update, context):
        return
    context.user_data.pop(WIDE_INVITE_STATE_KEY, None)
    context.user_data.pop(WIDE_INVITE_PROMPT_CHAT_ID_KEY, None)
    context.user_data.pop(WIDE_INVITE_PROMPT_MESSAGE_ID_KEY, None)
    if update.callback_query:
        await update.callback_query.answer()
    admins = wide_admins.list_wide_admins()
    await navigation.render_screen(
        update,
        context,
        text=_owner_panel_text(),
        reply_markup=keyboards.owner_panel(admins),
    )


async def owner_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_owner(update, context):
        return
    if context.user_data.get(WIDE_INVITE_STATE_KEY):
        await update.callback_query.answer(content.WIDE_ADMIN_INVITE_PENDING, show_alert=True)
        return
    context.user_data[WIDE_INVITE_STATE_KEY] = True
    prompt_message = update.callback_query.message
    if prompt_message is not None:
        context.user_data[WIDE_INVITE_PROMPT_CHAT_ID_KEY] = prompt_message.chat_id
        context.user_data[WIDE_INVITE_PROMPT_MESSAGE_ID_KEY] = prompt_message.message_id
    await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=content.WIDE_ADMIN_ADD_PROMPT,
        reply_markup=keyboards.invite_prompt(),
    )


async def handle_owner_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ورودی شناسهٔ هدف برای ساخت دعوت یک‌بارمصرف."""
    message = update.message
    if message is None or message.text is None:
        return
    raw_id = to_en(message.text).strip()
    if not re.fullmatch(r"\d+", raw_id):
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.WIDE_ADMIN_ID_INVALID
        )
        return
    try:
        target_id = int(raw_id)
    except ValueError:
        target_id = 0
    if not 0 < target_id < 2**63:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.WIDE_ADMIN_ID_INVALID
        )
        return
    if target_id in get_settings().admin_ids:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.WIDE_ADMIN_IS_OWNER
        )
        return
    if wide_admins.is_wide_admin(target_id):
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.WIDE_ADMIN_ALREADY_EXISTS
        )
        return

    token = wide_admins.create_invite(target_id, update.effective_user.id)
    context.user_data.pop(WIDE_INVITE_STATE_KEY, None)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=content.WIDE_ADMIN_INVITE_CREATED.format(user_id=target_id, token=token),
        parse_mode="HTML",
    )
    await _render_pending_prompt(
        update,
        context,
        chat_key=WIDE_INVITE_PROMPT_CHAT_ID_KEY,
        message_key=WIDE_INVITE_PROMPT_MESSAGE_ID_KEY,
        text=_owner_panel_text(),
        reply_markup=keyboards.owner_panel(wide_admins.list_wide_admins()),
    )


async def owner_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_owner(update, context):
        return
    user_id = int(context.match.group(1))
    wide_admins.revoke_wide_admin(user_id)
    await update.callback_query.answer(content.WIDE_ADMIN_REVOKED, show_alert=True)
    await navigation.render_screen(
        update,
        context,
        text=_owner_panel_text(),
        reply_markup=keyboards.owner_panel(wide_admins.list_wide_admins()),
    )


def _workspace_text(user_id: int) -> str:
    links = referrals.owned_links(user_id)
    lines = [content.WIDE_ADMIN_LINKS_TITLE, "", content.WIDE_ADMIN_LINKS_HINT, ""]
    if links:
        lines.append(f"لینک‌های شما: <b>{to_fa(len(links))}</b>")
    else:
        lines.append(content.WIDE_ADMIN_LINKS_EMPTY)
    return "\n".join(lines)


async def open_workspace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """فهرست رفرال‌های خود ادمین گسترده؛ برای /channels و /wideadmin."""
    if not await _require_wide_admin(update, context):
        return
    context.user_data.pop(WIDE_LINK_LABEL_STATE_KEY, None)
    context.user_data.pop(WIDE_LINK_PROMPT_CHAT_ID_KEY, None)
    context.user_data.pop(WIDE_LINK_PROMPT_MESSAGE_ID_KEY, None)
    if update.callback_query:
        await update.callback_query.answer()
    user_id = update.effective_user.id
    links = referrals.owned_links(user_id)
    await navigation.render_screen(
        update,
        context,
        text=_workspace_text(user_id),
        reply_markup=keyboards.workspace(links),
    )


def _link_detail_text(link: dict, bot_username: str) -> str:
    """جزئیات و آمار تجمیعی یک لینک متعلق به همین ادمین؛ بدون فهرست ثبت‌نام."""
    link_id = int(link["link_id"])
    funnel = referrals.funnel(link_id)
    starts = funnel["starts"]
    completed = funnel["completed"]
    percent = completed * 100 / starts if starts else 0.0
    url = referrals.link_url(bot_username, link["code"])
    status = "✅ فعال" if link["is_active"] else "⏸ غیرفعال"
    steps = [
        f"{referrals.STEP_LABELS[step]} {to_fa(funnel['steps'][step])}"
        for step in seminars.STEP_ORDER
    ]
    steps.append(f"✅ {to_fa(completed)}")
    grades = " | ".join(
        f"{_esc(grade.split()[-1])}: {to_fa(count)}" for grade, count in funnel["grades"].items()
    )
    lines = [
        f"📣 <b>{_esc(link['label'])}</b>",
        "",
        f"🔗 لینک کامل: <code>{_esc(url)}</code>",
        f"🔘 وضعیت: {status}",
        f"👥 ورودی (استارت): <b>{to_fa(starts)}</b>",
        f"✅ ثبت‌نام کامل: <b>{to_fa(completed)}</b> ({to_fa(f'{percent:.1f}')}٪)",
        f"⏳ نیمه‌کاره: <b>{to_fa(max(0, funnel['steps'][seminars.STEP_NAME] - completed))}</b>",
        "",
        "📊 قیف ثبت‌نام:",
        " → ".join(steps),
        f"🎓 {grades}",
        content.ADS_PHRASE_LINE.format(phrase=_esc(link["phrase"])),
    ]
    admins = referrals.link_admins(link_id)
    lines.append(content.ADS_ADMINS_HEADER if admins else content.ADS_ADMINS_EMPTY)
    for item in admins:
        lines.append(f"• شناسهٔ تلگرام <code>{item['user_id']}</code>")
    # عمداً از link_registrations/CSV/Excel استفاده نمی‌شود؛ اطلاعات فردی نمایش ندارد.
    return "\n".join(lines)


async def wide_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/wideadmin CODE برای مصرف دعوت، یا /wideadmin برای پنل شخصی."""
    user = update.effective_user
    if user is None:
        return
    if _is_owner(user.id):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="شما ادمین اصلی هستید؛ مدیریت کامل از /admin در دسترس است.",
        )
        return
    token = (context.args or [""])[0].strip()
    if token:
        if wide_admins.is_wide_admin(user.id):
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=content.WIDE_ADMIN_ALREADY_EXISTS
            )
            return
        if not wide_admins.redeem_invite(user.id, token):
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=content.WIDE_ADMIN_INVITE_INVALID
            )
            return
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.WIDE_ADMIN_ACTIVATED
        )
        await _notify_owners_wide_admin_activated(context, user.id)
        await open_workspace(update, context)
        return
    if wide_admins.is_wide_admin(user.id):
        await open_workspace(update, context)
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=content.WIDE_ADMIN_USAGE + "\n\n" + content.WIDE_ADMIN_NO_ACCESS,
            parse_mode="HTML",
        )


async def wide_link_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_wide_admin(update, context):
        return
    if context.user_data.get(WIDE_LINK_LABEL_STATE_KEY):
        await update.callback_query.answer(content.WIDE_LINK_LABEL_PENDING, show_alert=True)
        return
    context.user_data[WIDE_LINK_LABEL_STATE_KEY] = True
    prompt_message = update.callback_query.message
    if prompt_message is not None:
        context.user_data[WIDE_LINK_PROMPT_CHAT_ID_KEY] = prompt_message.chat_id
        context.user_data[WIDE_LINK_PROMPT_MESSAGE_ID_KEY] = prompt_message.message_id
    await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=content.WIDE_LINK_LABEL_PROMPT,
        reply_markup=keyboards.link_label_prompt(),
    )


async def wide_admin_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دریافت برچسب لینک جدید؛ ورودی‌های دیگر را به هندلرهای عادی واگذار می‌کند."""
    user = update.effective_user
    if user is None or not wide_admins.is_wide_admin(user.id):
        return
    if not context.user_data.get(WIDE_LINK_LABEL_STATE_KEY):
        return
    message = update.message
    if message is None or message.text is None:
        return
    label = message.text.strip()
    if not label:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=content.ADS_LABEL_EMPTY
        )
        raise ApplicationHandlerStop
    context.user_data.pop(WIDE_LINK_LABEL_STATE_KEY, None)
    link = referrals.create_link(label, owner_user_id=user.id)
    bot_username = context.bot.username or "bot"
    url = referrals.link_url(bot_username, link["code"])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=content.ADS_CREATED_TEXT.format(
            label=_esc(label), url=_esc(url), phrase=_esc(link["phrase"])
        ),
        parse_mode="HTML",
    )
    await _render_pending_prompt(
        update,
        context,
        chat_key=WIDE_LINK_PROMPT_CHAT_ID_KEY,
        message_key=WIDE_LINK_PROMPT_MESSAGE_ID_KEY,
        text=_workspace_text(user.id),
        reply_markup=keyboards.workspace(referrals.owned_links(user.id)),
    )
    raise ApplicationHandlerStop


async def wide_link_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_wide_admin(update, context):
        return
    link_id = int(context.match.group(1))
    user_id = update.effective_user.id
    if not referrals.owns_link(user_id, link_id):
        await update.callback_query.answer(content.WIDE_LINK_ACCESS_DENIED, show_alert=True)
        return
    link = referrals.get_link(link_id)
    await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=_link_detail_text(link, context.bot.username or "bot"),
        reply_markup=keyboards.link_detail(link),
    )


async def wide_link_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_wide_admin(update, context):
        return
    link_id = int(context.match.group(1))
    user_id = update.effective_user.id
    if not referrals.owns_link(user_id, link_id):
        await update.callback_query.answer(content.WIDE_LINK_ACCESS_DENIED, show_alert=True)
        return
    link = referrals.get_link(link_id)
    referrals.set_active(link_id, not bool(link["is_active"]))
    await update.callback_query.answer("وضعیت لینک تغییر کرد.")
    fresh = referrals.get_link(link_id)
    await navigation.render_screen(
        update,
        context,
        text=_link_detail_text(fresh, context.bot.username or "bot"),
        reply_markup=keyboards.link_detail(fresh),
    )


async def wide_link_reset_phrase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_wide_admin(update, context):
        return
    link_id = int(context.match.group(1))
    if not referrals.owns_link(update.effective_user.id, link_id):
        await update.callback_query.answer(content.WIDE_LINK_ACCESS_DENIED, show_alert=True)
        return
    referrals.reset_phrase(link_id)
    await update.callback_query.answer(content.ADS_RESET_DONE)
    fresh = referrals.get_link(link_id)
    await navigation.render_screen(
        update,
        context,
        text=_link_detail_text(fresh, context.bot.username or "bot"),
        reply_markup=keyboards.link_detail(fresh),
    )


async def wide_link_kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_wide_admin(update, context):
        return
    link_id, channel_admin_id = map(int, context.match.groups())
    if not referrals.owns_link(update.effective_user.id, link_id):
        await update.callback_query.answer(content.WIDE_LINK_ACCESS_DENIED, show_alert=True)
        return
    referrals.remove_channel_admin(channel_admin_id, link_id)
    await update.callback_query.answer(content.ADS_KICK_DONE)
    link = referrals.get_link(link_id)
    await navigation.render_screen(
        update,
        context,
        text=_link_detail_text(link, context.bot.username or "bot"),
        reply_markup=keyboards.link_detail(link),
    )


async def owner_assign_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_owner(update, context):
        return
    link_id = int(context.match.group(1))
    link = referrals.get_link(link_id)
    if link is None:
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return
    admins = wide_admins.list_wide_admins()
    owner_id = link.get("owner_user_id")
    if owner_id:
        owner = next((item for item in admins if item["user_id"] == owner_id), None)
        owner_name = _esc((owner or {}).get("first_name") or str(owner_id))
        owner_label = f"ادمین گستردهٔ {owner_name} ({owner_id})"
    else:
        owner_label = "ادمین اصلی"
    await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=(
            f"👤 <b>واگذاری دسترسی به لینک «{_esc(link['label'])}»</b>\n\n"
            f"مسئول فعلی: {owner_label}\n"
            "با واگذاری، ادمین گسترده فقط آمار تجمیعی همین لینک را می‌بیند؛ "
            "ادمین اصلی همچنان دسترسی کامل دارد."
        ),
        reply_markup=keyboards.owner_assignment(link, admins),
    )


async def owner_set_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_owner(update, context):
        return
    link_id, owner_id = map(int, context.match.groups())
    link = referrals.get_link(link_id)
    if link is None:
        await update.callback_query.answer(content.ADS_NOT_FOUND, show_alert=True)
        return
    if owner_id and not wide_admins.is_wide_admin(owner_id):
        await update.callback_query.answer(content.WIDE_ADMIN_NO_ACCESS, show_alert=True)
        return
    referrals.set_owner(link_id, owner_id or None)
    fresh = referrals.get_link(link_id)
    await update.callback_query.answer(content.WIDE_OWNER_SET_DONE)
    # استفاده از همان متن کامل ادمین اصلی؛ این مسیر فقط برای ADMIN_IDS است.
    from bot.handlers.admin import _ads_link_detail_text  # noqa: PLC0415

    await navigation.render_screen(
        update,
        context,
        text=_ads_link_detail_text(fresh, context.bot.username or "bot"),
        reply_markup=admin_keyboards.ads_link_detail(fresh),
    )


class _WideAdminFilter(filters.MessageFilter):
    def filter(self, message) -> bool:
        return bool(message.from_user and wide_admins.is_wide_admin(message.from_user.id))


def register(app: Application) -> None:
    app.add_handler(CommandHandler("wideadmin", wide_admin_command))
    app.add_handler(CallbackQueryHandler(owner_panel, pattern=PATTERN_ADMIN_WIDE))
    app.add_handler(CallbackQueryHandler(owner_add_prompt, pattern=PATTERN_ADMIN_WIDE_ADD))
    app.add_handler(CallbackQueryHandler(owner_revoke, pattern=PATTERN_ADMIN_WIDE_REVOKE))
    app.add_handler(CallbackQueryHandler(owner_assign_link, pattern=PATTERN_ADMIN_ADS_ASSIGN))
    app.add_handler(CallbackQueryHandler(owner_set_link, pattern=PATTERN_ADMIN_ADS_OWNER_SET))
    app.add_handler(CallbackQueryHandler(open_workspace, pattern=PATTERN_WIDE_HOME))
    app.add_handler(CallbackQueryHandler(wide_link_create, pattern=PATTERN_WIDE_CREATE))
    app.add_handler(CallbackQueryHandler(wide_link_view, pattern=PATTERN_WIDE_VIEW))
    app.add_handler(CallbackQueryHandler(wide_link_toggle, pattern=PATTERN_WIDE_TOGGLE))
    app.add_handler(CallbackQueryHandler(wide_link_reset_phrase, pattern=PATTERN_WIDE_RESET_PHRASE))
    app.add_handler(CallbackQueryHandler(wide_link_kick, pattern=PATTERN_WIDE_KICK))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & _WideAdminFilter(),
            wide_admin_message_input,
        ),
        group=0,
    )
