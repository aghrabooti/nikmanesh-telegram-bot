"""فیکسچر مشترک تست‌ها: اپلیکیشن واقعی + بات ماک‌شده + دیتابیس موقت."""

from __future__ import annotations

from unittest.mock import create_autospec

import pytest
from telegram.ext import ExtBot, Updater


@pytest.fixture
async def bot_app(tmp_path, monkeypatch):
    """اپلیکیشن آماده‌ی اجرا با بات ماک — (app, bot) برمی‌گرداند."""
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST-TOKEN")
    monkeypatch.setenv("ADMIN_IDS", "777")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))

    from bot.main import create_application
    from bot.services.database import close_db

    app = create_application()
    # بات و updater ماک می‌شوند تا هیچ تماس شبکه‌ای برقرار نشود
    app.bot = create_autospec(ExtBot, instance=True)  # از روی کلاس — نمونه‌ی واقعی initialize نشده
    app.updater = create_autospec(Updater, instance=True)
    await app.initialize()  # post_init فقط در run_polling/run_webhook صدا زده می‌شود
    await app.start()
    yield app, app.bot
    from bot.services import sender  # noqa: PLC0415

    await sender.cancel_worker()
    await app.stop()
    await app.shutdown()
    close_db()
