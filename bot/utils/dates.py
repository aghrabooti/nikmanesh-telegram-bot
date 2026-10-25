"""پارس متنی «تاریخ + ساعت» برای زمان شروع سمینار (شمسی یا میلادی)."""

from __future__ import annotations

import re
from datetime import datetime

from bot.utils.jalali import jalali_to_gregorian
from bot.utils.persian import to_en

_DATE_RE = re.compile(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_datetime_text(text: str) -> datetime | None:
    """«۱۴۰۵/۰۸/۱۵ ۱۸:۳۰» → datetime محلی؛ نامعتبر → None.

    - جداکننده‌ی تاریخ: ``/`` یا ``-`` یا ``.`` (ارقام فارسی/عربی پذیرفته)
    - جداکننده‌ی تاریخ و ساعت: فاصله یا ``T``؛ ساعت اختیاری (پیش‌فرض ۱۲:۰۰)
    - سال ≥ ۱۵۰۰ میلادی در نظر گرفته می‌شود؛ کمتر از آن، شمسی
    """
    parts = re.split(r"[ T]+", to_en(text).strip(), maxsplit=1)
    if not parts or not parts[0]:
        return None

    hour, minute = 12, 0
    if len(parts) == 2:
        match = _TIME_RE.match(parts[1].strip())
        if not match:
            return None
        hour, minute = int(match[1]), int(match[2])
        if hour > 23 or minute > 59:
            return None

    date_match = _DATE_RE.match(parts[0])
    if not date_match:
        return None
    year, month, day = (int(x) for x in date_match.groups())
    if year >= 1500:  # میلادی (ISO)
        gy, gm, gd = year, month, day
    else:  # شمسی
        if not 1300 <= year <= 1499 or not 1 <= month <= 12 or not 1 <= day <= 31:
            return None
        gy, gm, gd = jalali_to_gregorian(year, month, day)
    try:
        return datetime(gy, gm, gd, hour, minute)
    except ValueError:
        return None
