"""صفحه‌ی سمینار از دید کاربر."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from bot import navigation
from bot.config import content
from bot.constants import PATTERN_SEMINAR_VIEW
from bot.keyboards import user as user_keyboards
from bot.services import seminars
from bot.utils.persian import to_fa


def seminar_text(seminar: dict, *, status_line: str = "") -> str:
    """متن صفحه‌ی سمینار — فقط خطوط پر نمایش داده می‌شوند."""
    levels = seminars.split_levels(seminar)
    lines = [f"🎓 <b>{_esc(seminar['title'])}</b>", ""]
    if seminar["description"]:
        lines += [_esc(seminar["description"]), ""]
    if seminar["date_text"]:
        lines += [f"🗓 {_esc(seminar['date_text'])}", ""]
    if seminar["starts_at"]:
        lines += [f"⏰ شروع: {to_fa(seminars.format_starts_at(seminar))}", ""]
    if levels:
        lines += ["👥 گروه‌ها: " + "، ".join(_esc(x) for x in levels), ""]
    if status_line:
        lines += [status_line, ""]
    return "\n".join(lines).rstrip() + "\n"


def _esc(text: str) -> str:
    import html  # noqa: PLC0415

    return html.escape(text)


async def render_seminar_screen(
    update: Update, context: ContextTypes.DEFAULT_TYPE, seminar_id: int
) -> None:
    """نمایش صفحه‌ی سمینار — هم برای callback (ویرایش) و هم پیام (ارسال تازه)."""
    seminar = seminars.get_seminar(seminar_id)
    if seminar is None:
        if update.callback_query:
            await update.callback_query.answer()
        await navigation.render_screen(update, context, text=content.SEM_NOT_FOUND_TEXT)
        return

    user_id = update.effective_user.id
    reg = seminars.get_registration(user_id, seminar_id)
    if reg and reg["is_complete"]:
        status = content.ALREADY_DONE_TEXT
    elif reg:
        status = "⏳ ثبت‌نام شما نیمه‌کاره است."
    elif not seminar["is_open"]:
        status = content.SEM_CLOSED_TEXT
    else:
        status = "برای ثبت‌نام، دکمه‌ی زیر را بزنید:"

    if update.callback_query:
        await update.callback_query.answer()
    await navigation.render_screen(
        update,
        context,
        text=seminar_text(seminar, status_line=status),
        reply_markup=user_keyboards.seminar_screen(
            seminar,
            has_registration=reg is not None,
            is_complete=bool(reg and reg["is_complete"]),
        ),
    )


async def view_seminar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ورود به صفحه‌ی سمینار از دکمه‌ی اینلاین — data: sem:v:{id}"""
    seminar_id = int(update.callback_query.data.split(":")[2])
    await render_seminar_screen(update, context, seminar_id)


def register(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(view_seminar, pattern=PATTERN_SEMINAR_VIEW))
