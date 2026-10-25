"""نقطه‌ی ورود اصلی — ساخت اپلیکیشن و اجرای polling.

اجرا مستقیم روی ویندوز هم کار می‌کند:
    python bot/main.py
یا به‌صورت ماژول:
    python -m bot
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # اجرای مستقیم: python bot/main.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import BotCommand, BotCommandScopeChat
from telegram.error import TelegramError
from telegram.ext import Application, ApplicationBuilder

from bot.handlers import register_handlers
from bot.services import reminders, sender
from bot.services.database import init_db
from bot.utils.logging_setup import setup_logging

logger = setup_logging()

# فرمان‌های منوی تلگرام — برای «همه» فقط دستورهای کاربر عادی.
# فرمان‌های مدیریتی (/admin و /channels) عمداً در منو نیستند؛ با تایپ
# مستقیم کار می‌کنند (دسترسی‌شان با فیلتر ادمین/رمز کنترل می‌شود).
_USER_COMMANDS = [
    BotCommand("start", "منوی اصلی و سمینارهای باز"),
    BotCommand("menu", "منوی اصلی"),
    BotCommand("id", "شناسه‌ی تلگرام من"),
]


async def _setup_commands(app: Application) -> None:
    """ثبات فرمان‌ها در منوی تلگرام — یکسان برای همه، بدون دستورهای مدیریتی."""
    from bot.config.settings import get_settings  # noqa: PLC0415
    from bot.services import referrals  # noqa: PLC0415

    await app.bot.set_my_commands(_USER_COMMANDS)  # scope = همه‌ی کاربران
    # پاک‌سازی scope های اختصاصیِ احتمالی نسخه‌های قبل (ادمین/ادمین کانال)
    stale_ids = set(get_settings().admin_ids) | set(referrals.all_channel_admin_ids())
    for user_id in stale_ids:
        try:
            await app.bot.delete_my_commands(scope=BotCommandScopeChat(user_id))
        except TelegramError:  # کاربر هنوز ربات را استارت نکرده است
            continue


async def _on_startup(app: Application) -> None:
    """پس از راه‌اندازی: ثبت فرمان‌ها + حلقه‌ی یادآورها + صف ارسال انبوه."""
    await _setup_commands(app)
    reminders.ensure_task(app)
    sender.ensure_worker()


async def _on_shutdown(app: Application) -> None:
    """پیش از توقف کامل: توقف حلقه‌ی یادآورها و صف ارسال."""
    await reminders.cancel_task()
    await sender.cancel_worker()


def create_application() -> Application:
    """ساخت اپلیکیشن ربات (برای production و تست‌ها)."""
    from bot.config.settings import get_settings

    settings = get_settings()

    # دیتابیس (سمینارها + ثبت‌نام‌ها + کاربران + یادآورها)
    init_db(settings.database_path)

    builder = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .post_init(_on_startup)
        .post_shutdown(_on_shutdown)
    )
    app = builder.build()
    register_handlers(app)
    return app


def main() -> None:
    from bot.config.settings import get_settings
    from bot.utils.instance import acquire_instance_lock

    # فقط یک نمونه از ربات (قفل بین-پروسه‌ای — مهم برای nohup/keepalive روی هاست)
    if not acquire_instance_lock():
        return
    app = create_application()
    settings = get_settings()
    if settings.mode == "webhook":
        from bot import webhook

        webhook.run(app, settings)
        return
    logger.info("ربات با polling شروع می‌شود…")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
