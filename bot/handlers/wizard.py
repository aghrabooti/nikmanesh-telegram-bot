"""فرم ثبت‌نام ۷ مرحله‌ای:

نام ← پایه (کنکوری ۴۰۶/۴۰۷/۴۰۸) ← رشته (تجربی/ریاضی/انسانی) ← شهر ←
شماره تلگرام (اشتراک مخاطب) ← شماره پیامک (تایپ دستی 09xxxxxxxxx) ← پیام آخر.

همه‌ی مراحل با ریپلای کیبورد + دکمه‌های «⬅️ مرحله قبل» و «🔙 بازگشت» هستند.
"""

from __future__ import annotations

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import content
from bot.constants import (
    ABOUT_STATE_KEY,
    BCAST_STATE_KEY,
    EDIT_STATE_KEY,
    NEW_STATE_KEY,
    PATTERN_SEMINAR_REGISTER,
    RANGE_STATE_KEY,
)
from bot.handlers.seminars import render_seminar_screen
from bot.keyboards import user as user_keyboards
from bot.services import seminars
from bot.utils.persian import is_persian_text, normalize_phone, to_en

# کلید سمینارِ فعال در user_data
ACTIVE_SEMINAR_KEY = "active_seminar_id"

# شماره‌ی پیامک: دقیقاً ۱۱ رقم که با ۰۹ شروع می‌شود (ارقام فارسی/انگلیسی)
_SMS_RE = re.compile(r"^09\d{9}$")

# مرحله‌ی قبلی هر مرحله (برای دکمه‌ی «مرحله قبل»)
_PREV_STEP = {
    seminars.STEP_GRADE: seminars.STEP_NAME,
    seminars.STEP_FIELD: seminars.STEP_GRADE,
    seminars.STEP_CITY: seminars.STEP_FIELD,
    seminars.STEP_PHONE: seminars.STEP_CITY,
    seminars.STEP_SMS: seminars.STEP_PHONE,
}


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """شروع/ادامه‌ی ثبت‌نام — از همان مرحله‌ای که کاربر بوده."""
    seminar_id = int(update.callback_query.data.split(":")[2])
    seminar = seminars.get_seminar(seminar_id)
    if seminar is None:
        await update.callback_query.answer()
        await _reply(update, context, content.SEM_NOT_FOUND_TEXT)
        return

    reg = seminars.get_registration(update.effective_user.id, seminar_id)
    if reg is None and not seminar["is_open"]:
        await update.callback_query.answer(content.SEM_CLOSED_TEXT)
        return

    reg = seminars.ensure_registration(update.effective_user.id, seminar_id)
    reg = _normalize_step(update.effective_user.id, reg)
    context.user_data[ACTIVE_SEMINAR_KEY] = seminar_id
    await update.callback_query.answer()
    await _send_step(context, update.effective_chat.id, seminar, reg)


def _normalize_step(user_id: int, reg: dict) -> dict:
    """تبدیل مرحله‌ی نسخه‌های قدیمی (level/confirm) به معادل جدید."""
    step = reg["current_step"]
    mapped = seminars.LEGACY_STEP_MAP.get(step)
    if mapped:
        reg = {**reg, "current_step": mapped}
        seminars.save_registration(user_id, reg["seminar_id"], next_step=mapped)
    return reg


async def _send_step(context, chat_id: int, seminar: dict, reg: dict) -> None:
    """ارسال پرامپت مرحله‌ی فعلی همراه با ریپلای کیبورد همان مرحله."""
    step = reg["current_step"]
    if step == seminars.STEP_NAME:
        kb = user_keyboards.wiz_name_keyboard()
    elif step == seminars.STEP_GRADE:
        kb = user_keyboards.wiz_grade_keyboard()
    elif step == seminars.STEP_FIELD:
        kb = user_keyboards.wiz_field_keyboard()
    elif step == seminars.STEP_CITY:
        kb = user_keyboards.wiz_text_keyboard()
    elif step == seminars.STEP_PHONE:
        kb = user_keyboards.wiz_phone_keyboard()
    else:  # تایید شماره (پیامک)
        kb = user_keyboards.wiz_sms_keyboard()

    text = {
        seminars.STEP_NAME: content.WIZ_NAME_TEXT,
        seminars.STEP_GRADE: content.WIZ_GRADE_TEXT,
        seminars.STEP_FIELD: content.WIZ_FIELD_TEXT,
        seminars.STEP_CITY: content.WIZ_CITY_TEXT,
        seminars.STEP_PHONE: content.WIZ_PHONE_TEXT,
        seminars.STEP_SMS: content.WIZ_SMS_TEXT,
    }[step]
    await context.bot.send_message(chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _reply(update, context, text: str) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def _active_reg(update, context):
    """ثبت‌نام فعال کاربر (بر اساس کلید user_data) یا None."""
    seminar_id = context.user_data.get(ACTIVE_SEMINAR_KEY)
    if not seminar_id:
        return None, None
    seminar = seminars.get_seminar(seminar_id)
    reg = seminars.get_registration(update.effective_user.id, seminar_id)
    if seminar is None or reg is None or reg["is_complete"]:
        context.user_data.pop(ACTIVE_SEMINAR_KEY, None)
        return None, None
    return seminar, reg


def _admin_busy(context) -> bool:
    """اگر مدیر در میانه‌ی کارکرد پنل است، ورودی را به ادمین واگذار می‌کنیم."""
    keys = (
        NEW_STATE_KEY,
        EDIT_STATE_KEY,
        RANGE_STATE_KEY,
        BCAST_STATE_KEY,
        ABOUT_STATE_KEY,
    )
    return any(context.user_data.get(k) for k in keys)


async def _go_back_one(update, context, seminar: dict, reg: dict) -> None:
    """دکمه‌ی «⬅️ مرحله قبل» — بازگشت به مرحله‌ی قبلی بدون از دست رفتن داده."""
    prev = _PREV_STEP.get(reg["current_step"], seminars.STEP_NAME)
    seminars.save_registration(update.effective_user.id, seminar["id"], next_step=prev)
    await _send_step(context, update.effective_chat.id, seminar, {**reg, "current_step": prev})


async def _exit_wizard(update, context, seminar: dict) -> None:
    """دکمه‌ی «🔙 بازگشت» — خروج با حفظ پیشرفت + منوی ثابت."""
    context.user_data.pop(ACTIVE_SEMINAR_KEY, None)
    await _reply(update, context, content.WIZ_BACK_TEXT)
    await render_seminar_screen(update, context, seminar["id"])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=content.MENU_HINT_TEXT,
        reply_markup=user_keyboards.reply_menu(),
    )


def _valid_sms_phone(text: str) -> str | None:
    """اعتبارسنجی شماره پیامک: شروع با ۰۹ و دقیقاً ۱۱ رقم (فارسی/انگلیسی)."""
    digits = to_en(text).replace(" ", "").replace("-", "")
    return digits if _SMS_RE.match(digits) else None


async def wizard_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پیشروی مراحل ویزارد — ورودی معتبر = بلافاصله مرحله‌ی بعد."""
    # رمز ورود بخش کانال‌ها (state کاربر عادی — قبل از هر چیز مصرف می‌شود)
    from bot.handlers import channels  # noqa: PLC0415 — وابستگی چرخه‌ای در سطح ماژول

    if channels.maybe_consume_phrase(context):
        await channels.consume_phrase(update, context)
        raise ApplicationHandlerStop
    if _admin_busy(context):
        return
    seminar, reg = _active_reg(update, context)
    if seminar is None:
        return

    text = (update.message.text or "").strip()
    step = reg["current_step"]
    chat_id = update.effective_chat.id

    # دکمه‌های ناوبری ریپلای کیبورد
    if text == content.LBL_WIZ_BACK:
        await _exit_wizard(update, context, seminar)
        raise ApplicationHandlerStop
    if text == content.LBL_WIZ_PREV:
        await _go_back_one(update, context, seminar, reg)
        raise ApplicationHandlerStop

    if step == seminars.STEP_NAME:
        if not is_persian_text(text):
            await _reply(update, context, content.WIZ_NAME_INVALID)
            raise ApplicationHandlerStop
        await _advance(update, context, seminar, reg, name=text)
    elif step == seminars.STEP_GRADE:
        if text not in content.WIZ_GRADE_OPTIONS:
            await _send_step(context, chat_id, seminar, reg)  # پرامپت تکرار
            raise ApplicationHandlerStop
        await _advance(update, context, seminar, reg, grade=text)
    elif step == seminars.STEP_FIELD:
        if text not in content.WIZ_FIELD_OPTIONS:
            await _send_step(context, chat_id, seminar, reg)
            raise ApplicationHandlerStop
        await _advance(update, context, seminar, reg, field=text)
    elif step == seminars.STEP_CITY:
        if not is_persian_text(text):
            await _reply(update, context, content.WIZ_CITY_INVALID)
            raise ApplicationHandlerStop
        await _advance(update, context, seminar, reg, city=text)
    elif step == seminars.STEP_PHONE:
        # مسیر اصلی: دکمه‌ی «📱 ارسال شماره تلفن» (اشتراک مخاطب)؛
        # مسیر جایگزین: تایپ دستی شماره — برای کلاینت‌هایی که دکمه‌ی
        # request_contact را نشان نمی‌دهند یا کیبورد جمع شده است.
        phone = normalize_phone(text)
        if phone is None:
            await _reply(update, context, content.WIZ_PHONE_INVALID)
            raise ApplicationHandlerStop
        await _advance(update, context, seminar, reg, phone=phone)
    else:  # تایید شماره (پیامک)
        if text == content.LBL_PHONE_OK:
            # تأیید: همان شماره تلگرام برای پیامک استفاده می‌شود
            telegram_phone = reg.get("phone") or ""
            sms = "0" + telegram_phone[3:] if telegram_phone.startswith("+98") else None
            if sms is None or _valid_sms_phone(sms) is None:
                await _reply(update, context, content.WIZ_SMS_INVALID)
                raise ApplicationHandlerStop
            await _finish(update, context, seminar, reg, sms_phone=sms)
            raise ApplicationHandlerStop
        sms = _valid_sms_phone(text)
        if sms is None:
            await _reply(update, context, content.WIZ_SMS_INVALID)
            raise ApplicationHandlerStop
        await _finish(update, context, seminar, reg, sms_phone=sms)
    raise ApplicationHandlerStop  # پیام در ویزارد مصرف شد


async def _advance(update, context, seminar: dict, reg: dict, **fields) -> None:
    """ذخیره‌ی فیلد و رفتن به مرحله‌ی بعد."""
    step = reg["current_step"]
    order = seminars.STEP_ORDER
    next_step = order[min(order.index(step) + 1, len(order) - 1)]
    seminars.save_registration(
        update.effective_user.id, seminar["id"], next_step=next_step, **fields
    )
    await _send_step(
        context, update.effective_chat.id, seminar, {**reg, **fields, "current_step": next_step}
    )


async def _finish(update, context, seminar: dict, reg: dict, *, sms_phone: str) -> None:
    """پایان ثبت‌نام: ذخیره‌ی شماره پیامک + تکمیل + پیام آخر + منوی ثابت."""
    user_id = update.effective_user.id
    seminars.save_registration(
        user_id, seminar["id"], sms_phone=sms_phone, next_step=seminars.STEP_SMS
    )
    seminars.complete_registration(user_id, seminar["id"])
    context.user_data.pop(ACTIVE_SEMINAR_KEY, None)

    rows = []
    if seminar["link"]:
        rows.append([InlineKeyboardButton(content.LBL_ENTER_SEMINAR, url=seminar["link"])])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=seminars.final_message(seminar, {**reg, "sms_phone": sms_phone}),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows) if rows else None,
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=content.MENU_HINT_TEXT,
        reply_markup=user_keyboards.reply_menu(),
    )


async def wizard_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """مرحله‌ی شماره تلگرام: دریافت شماره با دکمه‌ی بومی «اشتراک مخاطب»."""
    if _admin_busy(context):
        return
    seminar, reg = _active_reg(update, context)
    if seminar is None:
        return
    if reg["current_step"] != seminars.STEP_PHONE:
        raise ApplicationHandlerStop
    phone = normalize_phone(update.message.contact.phone_number)
    if phone is None:
        await _reply(update, context, content.WIZ_PHONE_INVALID)
        raise ApplicationHandlerStop
    await _advance(update, context, seminar, reg, phone=phone)
    raise ApplicationHandlerStop


def register(app: Application) -> None:
    """گروه ۱ — بعد از دیسپچر ادمین (گروه ۰)، قبل از fallback (گروه ۲)."""
    app.add_handler(
        CallbackQueryHandler(start_registration, pattern=PATTERN_SEMINAR_REGISTER), group=1
    )
    app.add_handler(MessageHandler(filters.CONTACT, wizard_contact), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, wizard_text), group=1)
