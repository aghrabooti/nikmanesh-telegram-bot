"""تنظیمات محیطی ربات — از فایل .env یا متغیرهای محیطی."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent

try:  # python-dotenv اختیاری است
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    """تمام تنظیمات اجرای ربات در یک شیء."""

    bot_token: str
    admin_ids: frozenset[int]
    database_path: Path
    mode: str  # polling | webhook
    webhook_url: str
    webhook_port: int


def get_settings() -> Settings:
    """خواندن تنظیمات از محیط (هر بار تازه — برای تست‌پذیری)."""
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BOT_TOKEN تنظیم نشده است — فایل .env را کامل کنید (نمونه: .env.example)"
        )

    raw_admins = os.getenv("ADMIN_IDS", "").replace("،", ",")
    admin_ids = frozenset(int(x) for x in raw_admins.split(",") if x.strip())

    db_raw = os.getenv("DATABASE_PATH", "").strip() or str(_ROOT / "data" / "seminar.db")
    db_path = Path(db_raw)
    if not db_path.is_absolute():
        db_path = _ROOT / db_path

    return Settings(
        bot_token=token,
        admin_ids=admin_ids,
        database_path=db_path,
        mode=os.getenv("BOT_MODE", "polling").strip().lower(),
        webhook_url=os.getenv("WEBHOOK_URL", "").strip(),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "8443")),
    )
