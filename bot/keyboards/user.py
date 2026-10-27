"""کیبوردهای سمت کاربر — دکمه‌ی شیشه‌ای استارت + منوی ثابت (ریپلای کیبورد)."""

from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.config import content
from bot.constants import CB_SEMINAR_REGISTER, CB_SEMINAR_VIEW
from bot.services import seminars


def start_inline() -> InlineKeyboardMarkup | None:
    """دکمه‌ی شیشه‌ای رنگی زیر پیام استارت — «وبینار {فعال}»."""
    active = seminars.active_seminar()
    if active is None:
        return None
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    content.LBL_WEBINAR.format(title=active["title"]),
                    callback_data=CB_SEMINAR_VIEW.format(seminar_id=active["id"]),
                    style="success",  # شیشه‌ای رنگی (سبز)
                )
            ]
        ]
    )


def _fixed_rows() -> list[list[KeyboardButton]]:
    """ردیف‌های ثابت منوی کاربر — وبینار فعال + درباره + ارتباط با ما."""
    rows: list[list[KeyboardButton]] = []
    active = seminars.active_seminar()
    if active is not None:
        rows.append([KeyboardButton(content.LBL_WEBINAR.format(title=active["title"]))])
    rows.append([KeyboardButton(content.LBL_ABOUT), KeyboardButton(content.LBL_CONTACT)])
    return rows


def reply_menu() -> ReplyKeyboardMarkup:
    """منوی ثابت کاربر (ریپلای کیبورد)."""
    return ReplyKeyboardMarkup(_fixed_rows(), resize_keyboard=True)


# ── کیبوردهای ویزارد ثبت‌نام ──


def _nav_row(with_prev: bool) -> list[KeyboardButton]:
    """ردیف ناوبری ویزارد: مرحله قبل + بازگشت."""
    if with_prev:
        return [KeyboardButton(content.LBL_WIZ_PREV), KeyboardButton(content.LBL_WIZ_BACK)]
    return [KeyboardButton(content.LBL_WIZ_BACK)]


def wiz_name_keyboard() -> ReplyKeyboardMarkup:
    """مرحله‌ی نام — فقط بازگشت (مرحله‌ای قبلش وجود ندارد)."""
    return ReplyKeyboardMarkup([_nav_row(with_prev=False)], resize_keyboard=True)


def wiz_grade_keyboard() -> ReplyKeyboardMarkup:
    """مرحله‌ی پایه: کنکوری ۴۰۶/۴۰۷/۴۰۸ + ناوبری."""
    rows = [[KeyboardButton(g)] for g in content.WIZ_GRADE_OPTIONS]
    rows.append(_nav_row(with_prev=True))
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def wiz_field_keyboard() -> ReplyKeyboardMarkup:
    """مرحله‌ی رشته: تجربی/ریاضی/انسانی + ناوبری."""
    rows = [list(KeyboardButton(f) for f in content.WIZ_FIELD_OPTIONS)]
    rows.append(_nav_row(with_prev=True))
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def wiz_alternate_phone_keyboard() -> ReplyKeyboardMarkup:
    """مرحله‌ی شماره جایگزین: ثبت همان شماره یا ورود شماره‌ی دیگری + ناوبری."""
    rows = [[KeyboardButton(content.LBL_ALTERNATE_PHONE_OK)]]
    rows.append(_nav_row(with_prev=True))
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def wiz_text_keyboard() -> ReplyKeyboardMarkup:
    """مراحل تایپی (شهر/شماره جایگزین) — فقط ناوبری."""
    return ReplyKeyboardMarkup([_nav_row(with_prev=True)], resize_keyboard=True)


def wiz_phone_keyboard() -> ReplyKeyboardMarkup:
    """مرحله‌ی شماره تلگرام: دکمه‌ی بومی ارسال شماره + ناوبری."""
    rows = [[KeyboardButton(content.LBL_SHARE_PHONE, request_contact=True)]]
    rows.append(_nav_row(with_prev=True))
    # بدون one_time_keyboard — کیبورد یک‌بار‌مصرف در برخی کلاینت‌ها بعد از
    # اولین لمس/پیام جمع می‌شود و دکمه‌ی اشتراک شماره دیگر نمایش داده نمی‌شود.
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def channels_cancel_keyboard() -> ReplyKeyboardMarkup:
    """پرامپت رمز ورود کانال‌ها — فقط انصراف."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(content.CH_LOGIN_CANCEL_LBL)]], resize_keyboard=True
    )


def seminar_screen(seminar: dict, *, has_registration: bool, is_complete: bool):
    """کیبورد اینلاین صفحه‌ی سمینار — فقط اقدام اصلی (منوی ثابت جدا است)."""
    sid = seminar["id"]
    rows: list[list[InlineKeyboardButton]] = []
    if is_complete:
        if seminar["link"]:
            rows.append([InlineKeyboardButton(content.LBL_ENTER_SEMINAR, url=seminar["link"])])
    elif has_registration:
        rows.append(
            [
                InlineKeyboardButton(
                    content.LBL_RESUME_REGISTRATION,
                    callback_data=CB_SEMINAR_REGISTER.format(seminar_id=sid),
                )
            ]
        )
    elif seminar["is_open"]:
        rows.append(
            [
                InlineKeyboardButton(
                    content.LBL_REGISTER,
                    callback_data=CB_SEMINAR_REGISTER.format(seminar_id=sid),
                )
            ]
        )
    return InlineKeyboardMarkup(rows) if rows else None
