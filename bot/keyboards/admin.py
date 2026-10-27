"""کیبوردهای پنل مدیریت."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import content
from bot.constants import (
    CB_ADMIN_ABOUT,
    CB_ADMIN_ADS,
    CB_ADMIN_ADS_CSV,
    CB_ADMIN_ADS_KICK,
    CB_ADMIN_ADS_MSG,
    CB_ADMIN_ADS_NEW,
    CB_ADMIN_ADS_REGS,
    CB_ADMIN_ADS_REGS_CSV,
    CB_ADMIN_ADS_REGS_XLSX,
    CB_ADMIN_ADS_RESET_PHRASE,
    CB_ADMIN_ADS_XLSX,
    CB_ADMIN_BCAST,
    CB_ADMIN_BCAST_GO,
    CB_ADMIN_BCAST_NO,
    CB_ADMIN_RANGE,
    CB_ADMIN_REGS,
    CB_ADMIN_REGS_CSV,
    CB_ADMIN_REGS_CSV_COMPLETE,
    CB_ADMIN_REGS_MSG,
    CB_ADMIN_REGS_XLSX,
    CB_ADMIN_REGS_XLSX_COMPLETE,
    CB_ADMIN_REMINDERS,
    CB_ADMIN_SEM_DELETE,
    CB_ADMIN_SEM_DELETE2,
    CB_ADMIN_SEM_EDIT,
    CB_ADMIN_SEM_EDIT_FIELD,
    CB_ADMIN_SEM_NEW,
    CB_ADMIN_SEM_OPEN,
    CB_ADMIN_SEM_PAGE,
    CB_ADMIN_SEMS,
    CB_ADMIN_USERS_CSV,
    CB_ADMIN_USERS_XLSX,
    CB_MAIN,
    SEMINAR_FIELDS,
)
from bot.services import seminars


def _btn(label: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=callback)


def overview(*, reminders_on: bool = True) -> InlineKeyboardMarkup:
    """صفحه‌ی اصلی پنل — سمینارها، پیام همگانی و کلید یادآورها."""
    return InlineKeyboardMarkup(
        [
            [_btn(content.LBL_ADMIN_SEMS, CB_ADMIN_SEMS)],
            [_btn(content.LBL_ADMIN_BCAST, CB_ADMIN_BCAST)],
            [
                _btn(content.LBL_ADMIN_USERS_CSV, CB_ADMIN_USERS_CSV),
                _btn(content.LBL_ADMIN_USERS_XLSX, CB_ADMIN_USERS_XLSX),
            ],
            [_btn(content.LBL_ADMIN_ADS, CB_ADMIN_ADS)],
            [
                _btn(
                    content.LBL_ADMIN_REMINDERS_ON
                    if reminders_on
                    else content.LBL_ADMIN_REMINDERS_OFF,
                    CB_ADMIN_REMINDERS,
                )
            ],
            [_btn(content.LBL_ADMIN_ABOUT, CB_ADMIN_ABOUT)],
            [_btn(content.LBL_HOME, CB_MAIN)],
        ]
    )


def sems_list() -> InlineKeyboardMarkup:
    """لیست سمینارها (با آمار هر کدام) + ساخت سمینار جدید."""
    rows = [
        [
            _btn(
                f"{'🟢' if s['is_open'] else '🔴'} {s['title']}",
                CB_ADMIN_SEM_PAGE.format(seminar_id=s["id"]),
            )
        ]
        for s in seminars.list_seminars()
    ]
    rows.append([_btn(content.ADMIN_SEMINAR_NEW, CB_ADMIN_SEM_NEW)])
    rows.append([_btn(content.LBL_HOME, CB_MAIN)])
    return InlineKeyboardMarkup(rows)


def seminar_page(seminar: dict) -> InlineKeyboardMarkup:
    """صفحه‌ی یک سمینار در پنل."""
    sid = seminar["id"]
    return InlineKeyboardMarkup(
        [
            [_btn("✏️ ویرایش", CB_ADMIN_SEM_EDIT.format(seminar_id=sid))],
            [
                _btn(
                    content.LBL_ADMIN_CLOSE if seminar["is_open"] else content.LBL_ADMIN_OPEN,
                    CB_ADMIN_SEM_OPEN.format(seminar_id=sid),
                )
            ],
            [_btn("📋 ثبت‌نام‌ها", CB_ADMIN_REGS.format(seminar_id=sid))],
            [_btn("🗑 حذف", CB_ADMIN_SEM_DELETE.format(seminar_id=sid))],
            [_btn(content.LBL_BACK, CB_ADMIN_SEMS)],
            [_btn(content.LBL_HOME, CB_MAIN)],
        ]
    )


def edit_menu(seminar: dict) -> InlineKeyboardMarkup:
    """منوی ویرایش فیلدها (۷ فیلد، از جمله زمان شروع و پیام نهایی)."""
    sid = seminar["id"]
    rows = [
        [
            _btn(
                content.ADMIN_FIELD_LABELS[field],
                CB_ADMIN_SEM_EDIT_FIELD.format(seminar_id=sid, field=field),
            )
        ]
        for field in SEMINAR_FIELDS
    ]
    rows.append([_btn(content.LBL_BACK, CB_ADMIN_SEM_PAGE.format(seminar_id=sid))])
    rows.append([_btn(content.LBL_HOME, CB_MAIN)])
    return InlineKeyboardMarkup(rows)


def delete_confirm(seminar: dict) -> InlineKeyboardMarkup:
    sid = seminar["id"]
    return InlineKeyboardMarkup(
        [
            [_btn(content.LBL_ADMIN_DELETE_CONFIRM, CB_ADMIN_SEM_DELETE2.format(seminar_id=sid))],
            [_btn(content.LBL_BACK, CB_ADMIN_SEM_PAGE.format(seminar_id=sid))],
            [_btn(content.LBL_HOME, CB_MAIN)],
        ]
    )


def regs_page(seminar_id: int) -> InlineKeyboardMarkup:
    """صفحه‌ی ثبت‌نام‌ها: خروجی‌ها + بازه‌ی تاریخ."""
    return InlineKeyboardMarkup(
        [
            [_btn(content.LBL_ADMIN_REGS_MSG, CB_ADMIN_REGS_MSG.format(seminar_id=seminar_id))],
            [
                _btn(content.LBL_ADMIN_REGS_CSV, CB_ADMIN_REGS_CSV.format(seminar_id=seminar_id)),
                _btn(
                    content.LBL_ADMIN_REGS_CSV_COMPLETE,
                    CB_ADMIN_REGS_CSV_COMPLETE.format(seminar_id=seminar_id),
                ),
            ],
            [
                _btn(
                    content.LBL_ADMIN_REGS_XLSX,
                    CB_ADMIN_REGS_XLSX.format(seminar_id=seminar_id),
                ),
                _btn(
                    content.LBL_ADMIN_REGS_XLSX_COMPLETE,
                    CB_ADMIN_REGS_XLSX_COMPLETE.format(seminar_id=seminar_id),
                ),
            ],
            [
                _btn(content.LBL_RANGE_TODAY, CB_ADMIN_RANGE.format(code="today")),
                _btn(content.LBL_RANGE_7, CB_ADMIN_RANGE.format(code="7")),
                _btn(content.LBL_RANGE_30, CB_ADMIN_RANGE.format(code="30")),
            ],
            [
                _btn(content.LBL_RANGE_90, CB_ADMIN_RANGE.format(code="90")),
                _btn(content.LBL_RANGE_ALL, CB_ADMIN_RANGE.format(code="all")),
                _btn(content.LBL_RANGE_CUSTOM, CB_ADMIN_RANGE.format(code="custom")),
            ],
            [_btn(content.LBL_BACK, CB_ADMIN_SEM_PAGE.format(seminar_id=seminar_id))],
            [_btn(content.LBL_HOME, CB_MAIN)],
        ]
    )


def ads(link_rows: list[list[InlineKeyboardButton]] = ()) -> InlineKeyboardMarkup:
    """هاب مدیریت تبلیغات: لینک جدید + دکمه‌ی هر لینک + خروجی‌ها."""
    rows = [[_btn(content.LBL_ADS_NEW, CB_ADMIN_ADS_NEW)]]
    rows += [list(r) for r in link_rows]
    rows += [
        [_btn(content.LBL_ADS_MSG, CB_ADMIN_ADS_MSG)],
        [_btn(content.LBL_ADS_CSV, CB_ADMIN_ADS_CSV)],
        [_btn(content.LBL_ADS_XLSX, CB_ADMIN_ADS_XLSX)],
        [_btn(content.LBL_HOME, CB_MAIN)],
    ]
    return InlineKeyboardMarkup(rows)


def ads_link_detail(link: dict) -> InlineKeyboardMarkup:
    """صفحه‌ی مدیریت یک لینک رفرال: روشن/خاموش + ثبت‌نامی‌ها + رمز + دسترسی‌ها."""
    link_id = int(link["link_id"])
    label = content.LBL_ADS_TOGGLE_OFF if link["is_active"] else content.LBL_ADS_TOGGLE_ON
    rows = [
        [_btn(label, f"adm:ads:t:{link_id}")],
        [_btn(content.LBL_ADS_RESET_PHRASE, CB_ADMIN_ADS_RESET_PHRASE.format(link_id=link_id))],
        [_btn(content.LBL_ADS_REGS, CB_ADMIN_ADS_REGS.format(link_id=link_id))],
        [
            _btn(content.LBL_ADS_REGS_CSV, CB_ADMIN_ADS_REGS_CSV.format(link_id=link_id)),
            _btn(content.LBL_ADS_REGS_XLSX, CB_ADMIN_ADS_REGS_XLSX.format(link_id=link_id)),
        ],
    ]
    for admin_row in _link_admin_rows(link_id):
        rows.append(admin_row)
    rows += [
        [_btn(content.LBL_BACK, CB_ADMIN_ADS)],
        [_btn(content.LBL_HOME, CB_MAIN)],
    ]
    return InlineKeyboardMarkup(rows)


def _link_admin_rows(link_id: int) -> list[list[InlineKeyboardButton]]:
    """ردیف «بیرون کردن» برای هر ادمین کانالِ واردشده."""
    from bot.services import referrals  # noqa: PLC0415 — جلوگیری از import چرخه‌ای

    rows = []
    for entry in referrals.link_admins(link_id):
        name = _channel_admin_name(entry["user_id"])
        rows.append(
            [
                _btn(
                    content.LBL_ADS_KICK.format(name=name),
                    CB_ADMIN_ADS_KICK.format(link_id=link_id, user_id=entry["user_id"]),
                )
            ]
        )
    return rows


def _channel_admin_name(user_id: int) -> str:
    """نام نمایشی ادمین کانال از جدول کاربران (یا شناسه)."""
    from bot.services import users  # noqa: PLC0415

    row = users.get_user(user_id)
    if row and row["first_name"]:
        return row["first_name"]
    return str(user_id)


def ads_prompt() -> InlineKeyboardMarkup:
    """صفحه‌ی دریافت برچسب لینک جدید — فقط انصراف."""
    return InlineKeyboardMarkup([[_btn(content.LBL_BACK, CB_ADMIN_ADS)]])


def bcast_prompt() -> InlineKeyboardMarkup:
    """پرامپت پیام همگانی — فقط انصراف."""
    return InlineKeyboardMarkup([[_btn(content.LBL_BCAST_NO, CB_ADMIN_BCAST_NO)]])


def bcast_confirm(count) -> InlineKeyboardMarkup:
    """تأییدیه‌ی ارسال همگانی (count می‌تواند رشته‌ی ارقام فارسی باشد)."""
    return InlineKeyboardMarkup(
        [
            [_btn(content.LBL_BCAST_GO.format(count=count), CB_ADMIN_BCAST_GO)],
            [_btn(content.LBL_BCAST_NO, CB_ADMIN_BCAST_NO)],
        ]
    )
