"""ابزارهای متنی فارسی: ارقام، نام و شماره تماس."""

from __future__ import annotations

import re

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
EN_DIGITS = "0123456789"

_TO_EN = str.maketrans(FA_DIGITS + AR_DIGITS, EN_DIGITS + EN_DIGITS)
_TO_FA = str.maketrans(EN_DIGITS, FA_DIGITS)

# حروف فارسی + فاصله/ZWNJ؛ ۲ تا ۶۰ نویسه
_TEXT_RE = re.compile(r"^[\u0621-\u064A\u067E\u0686\u0698\u06A9\u06AF\u06C0\u06CC\s\u200c]{2,60}$")


def to_en(text: str) -> str:
    """تبدیل ارقام فارسی/عربی به انگلیسی."""
    return text.translate(_TO_EN)


def to_fa(value: object) -> str:
    """تبدیل ارقام انگلیسی به فارسی (برای نمایش به کاربر)."""
    return str(value).translate(_TO_FA)


def is_persian_text(text: str) -> bool:
    """متن فارسی معتبر (نام/شهر): فقط حروف فارسی و فاصله."""
    return bool(_TEXT_RE.match(text.strip()))


def normalize_phone(text: str) -> str | None:
    """نرمال‌سازی شماره موبایل ایران به شکل +989XXXXXXXXX؛ نامعتبر → None."""
    digits = to_en(text).replace(" ", "").replace("-", "").lstrip("+")
    if digits.startswith("0098"):
        digits = "98" + digits[4:]
    if digits.startswith("098"):
        digits = "98" + digits[3:]
    if digits.startswith("0"):
        digits = "98" + digits[1:]
    elif len(digits) == 10 and digits.startswith("9"):
        digits = "98" + digits
    if len(digits) == 12 and digits.startswith("989") and digits.isdigit():
        return "+" + digits
    return None
