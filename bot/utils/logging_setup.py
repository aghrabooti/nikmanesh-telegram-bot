"""راه‌اندازی لاگ یکنواخت."""

from __future__ import annotations

import logging


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        level=level,
    )
    # کتابخانه‌های زیرین پرحرف‌اند
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    return logging.getLogger("tizgam-seminar-bot")
