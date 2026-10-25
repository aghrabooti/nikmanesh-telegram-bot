"""تنظیمات متنی قابل‌ویرایش ادمین (متن صفحه‌ی «درباره آکادمی»)."""

from __future__ import annotations

from bot.config import content
from bot.services.database import get_setting, set_setting

_ABOUT_KEY = "about_text"
_ABOUT_MAX = 2500


def get_about_text() -> str:
    """متن فعلی «درباره آکادمی» — ذخیره‌ی خالی = متن پیش‌فرض."""
    return get_setting(_ABOUT_KEY) or content.ABOUT_DEFAULT_TEXT


def set_about_text(text: str) -> None:
    """ذخیره‌ی متن «درباره آکادمی» (رشته‌ی خالی = بازگشت به پیش‌فرض)."""
    set_setting(_ABOUT_KEY, text.strip()[:_ABOUT_MAX])
