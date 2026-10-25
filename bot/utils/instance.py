"""قفل تک‌نمونه‌ای ربات — در هر لحظه فقط یک پروسه اجازه‌ی اجرا دارد.

روی لینوکس (هاست) با flock پیاده شده است؛ روی ویندوز (PC شخصی) fcntl
وجود ندارد و قفل به‌صورت no-op فعال می‌شود — چون اجرای هم‌زمان دو نمونه
روی PC عملاً پیش نمی‌آید.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:  # ویندوز
    fcntl = None

_lock_handle = None


def acquire_instance_lock(lock_name: str = "bot.lock") -> bool:
    """True = این پروسه صاحب اجرای ربات است؛ False = نمونه‌ی دیگری فعال است.

    قفل تا پایان عمر پروسه باز می‌ماند (نیازی به release دستی نیست).
    """
    global _lock_handle
    if fcntl is None:
        return True  # ویندوز — بدون قفل
    lock_path = project_root() / "tmp" / lock_name
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "w")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_handle = handle
        return True
    except OSError:
        logger.warning("نمونه‌ی دیگری از ربات فعال است — این پروسه اجرا نمی‌شود")
        return False


def bot_is_running(lock_name: str = "bot.lock") -> bool:
    """آیا پروسه‌ای قفل را در دست دارد؟ (برای صفحه‌ی سلامت passenger)"""
    if fcntl is None:
        return False
    lock_path = project_root() / "tmp" / lock_name
    if not lock_path.exists():
        return False
    try:
        handle = open(lock_path, "w")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle, fcntl.LOCK_UN)
            return False  # قفل آزاد بود → ربات در اجرا نیست
        finally:
            handle.close()
    except OSError:
        return True  # کسی قفل را گرفته → ربات فعال است


def project_root() -> Path:
    """ریشه‌ی پروژه (پوشه‌ی حاوی bot/)."""
    return Path(__file__).resolve().parent.parent.parent
