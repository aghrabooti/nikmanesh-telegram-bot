"""کیبوردهای مدیریت ادمین گسترده و فضای رفرال محدودشده."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import content
from bot.constants import (
    CB_ADMIN_ADS_OWNER_SET,
    CB_ADMIN_ADS_VIEW,
    CB_ADMIN_WIDE,
    CB_ADMIN_WIDE_ADD,
    CB_ADMIN_WIDE_REVOKE,
    CB_MAIN,
    CB_WIDE_CREATE,
    CB_WIDE_HOME,
    CB_WIDE_KICK,
    CB_WIDE_RESET_PHRASE,
    CB_WIDE_TOGGLE,
    CB_WIDE_VIEW,
)
from bot.services import referrals


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=callback_data)


def _short(text: str, length: int = 24) -> str:
    return text if len(text) <= length else text[: length - 1] + "…"


def owner_panel(admins: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for item in admins:
        display = _short(item["first_name"] or "ادمین")
        rows.append(
            [
                _btn(
                    f"🚫 {display} · {item['user_id']}",
                    CB_ADMIN_WIDE_REVOKE.format(user_id=item["user_id"]),
                )
            ]
        )
    rows.extend(
        [
            [_btn(content.LBL_WIDE_ADMIN_ADD, CB_ADMIN_WIDE_ADD)],
            [_btn(content.LBL_BACK, CB_MAIN)],
        ]
    )
    return InlineKeyboardMarkup(rows)


def invite_prompt() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_btn(content.LBL_BACK, CB_ADMIN_WIDE)]])


def owner_assignment(link: dict, admins: list[dict]) -> InlineKeyboardMarkup:
    link_id = int(link["link_id"])
    rows = []
    for item in admins:
        name = _short(item["first_name"] or "ادمین")
        rows.append(
            [
                _btn(
                    f"{name} · {item['user_id']}",
                    CB_ADMIN_ADS_OWNER_SET.format(link_id=link_id, owner_id=item["user_id"]),
                )
            ]
        )
    rows.extend(
        [
            [
                _btn(
                    content.LBL_ADS_ASSIGN_NONE,
                    CB_ADMIN_ADS_OWNER_SET.format(link_id=link_id, owner_id=0),
                )
            ],
            [_btn(content.LBL_BACK, CB_ADMIN_ADS_VIEW.format(link_id=link_id))],
        ]
    )
    return InlineKeyboardMarkup(rows)


def workspace(links: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for link in links:
        marker = "✅" if link["is_active"] else "⏸"
        rows.append(
            [
                _btn(
                    f"{marker} {_short(link['label'], 38)} · {link['code']}",
                    CB_WIDE_VIEW.format(link_id=link["link_id"]),
                )
            ]
        )
    rows.extend(
        [
            [_btn(content.LBL_WIDE_LINK_CREATE, CB_WIDE_CREATE)],
            [_btn(content.LBL_HOME, CB_MAIN)],
        ]
    )
    return InlineKeyboardMarkup(rows)


def link_label_prompt() -> InlineKeyboardMarkup:
    """پرامپت برچسب: دکمهٔ ساخت حذف می‌شود تا فقط یک درخواست فعال بماند."""
    return InlineKeyboardMarkup([[_btn(content.LBL_BACK, CB_WIDE_HOME)]])


def _link_admin_rows(link_id: int) -> list[list[InlineKeyboardButton]]:
    rows = []
    for item in referrals.link_admins(link_id):
        user_id = int(item["user_id"])
        rows.append(
            [
                _btn(
                    f"🚪 لغو دسترسی شناسه {user_id}",
                    CB_WIDE_KICK.format(link_id=link_id, user_id=user_id),
                )
            ]
        )
    return rows


def link_detail(link: dict) -> InlineKeyboardMarkup:
    link_id = int(link["link_id"])
    toggle_label = content.LBL_ADS_TOGGLE_OFF if link["is_active"] else content.LBL_ADS_TOGGLE_ON
    rows = [
        [_btn(toggle_label, CB_WIDE_TOGGLE.format(link_id=link_id))],
        [_btn(content.LBL_ADS_RESET_PHRASE, CB_WIDE_RESET_PHRASE.format(link_id=link_id))],
    ]
    rows.extend(_link_admin_rows(link_id))
    rows.extend(
        [
            [_btn(content.LBL_WIDE_LINK_CREATE, CB_WIDE_CREATE)],
            [_btn(content.LBL_BACK, CB_WIDE_HOME)],
            [_btn(content.LBL_HOME, CB_MAIN)],
        ]
    )
    return InlineKeyboardMarkup(rows)
