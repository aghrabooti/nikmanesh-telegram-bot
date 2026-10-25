"""تبدیل تقویم جلالی ↔ میلادی — بدون وابستگی خارجی (الگوریتم کلاسیک jdf)."""

from __future__ import annotations

import re
from datetime import date

from bot.utils.persian import to_en

_DATE_RE = re.compile(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$")


def _is_gregorian_leap(gy: int) -> bool:
    return (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """میلادی → جلالی."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + 365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 3) // 100
        + (gy2 + 3) // 400
        + gd
        + g_d_m[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    """جلالی → میلادی."""
    jy += 1595
    days = (
        -355668
        + 365 * jy
        + (jy // 33) * 8
        + ((jy % 33) + 3) // 4
        + jd
        + ((jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186)
    )
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    months = [31, 29 if _is_gregorian_leap(gy) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    while gm < 12 and gd > months[gm - 1]:
        gd -= months[gm - 1]
        gm += 1
    return gy, gm, gd


def format_jalali(d: date) -> str:
    """تاریخ میلادی → رشته‌ی «1405/07/29»."""
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return f"{jy}/{jm:02d}/{jd:02d}"


def parse_jalali_text(text: str) -> date | None:
    """پارس «۱۴۰۵/۰۷/۱۵» (ارقام فارسی/انگلیسی، جداکننده‌ی / - .) → date."""
    match = _DATE_RE.match(to_en(text).strip())
    if not match:
        return None
    jy, jm, jd = (int(x) for x in match.groups())
    if not 1300 <= jy <= 1500 or not 1 <= jm <= 12 or not 1 <= jd <= 31:
        return None
    try:
        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        return date(gy, gm, gd)
    except ValueError:
        return None
