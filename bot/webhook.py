"""اجرای ربات در حالت وب‌هوک (هاست اشتراکی/cPanel — پروسه‌ی بلندمدت).

PTB در run_webhook مقدار post_init را صدا می‌زند؛ این حالت دستی است، پس
هوک‌ها را خودمان مدیریت می‌کنیم.
"""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application

logger = logging.getLogger(__name__)

_INIT_TIMEOUT = 30


async def _serve(app: Application, settings) -> None:
    """راه‌اندازی دستی وب‌هوک + انتظار تا سیگنال توقف."""
    await asyncio.wait_for(app.initialize(), timeout=_INIT_TIMEOUT)
    await app.start()
    # حلقه‌ی یادآورها — post_init فقط در run_polling/run_webhook اجرا می‌شود؛
    # اینجا حالت دستی است و باید خودمان روشنش کنیم.
    from bot.services import reminders, sender  # noqa: PLC0415

    reminders.ensure_task(app)
    sender.ensure_worker()
    secret_path = settings.bot_token.split(":")[0]
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=settings.webhook_port,
        url_path=secret_path,
        webhook_url=f"{settings.webhook_url}/{secret_path}",
    )
    logger.info("وب‌هوک فعال شد: %s/%s", settings.webhook_url, secret_path)
    try:
        await asyncio.Event().wait()  # تا ابد (توقف با سیگنال)
    finally:
        from bot.services import reminders, sender  # noqa: PLC0415

        await reminders.cancel_task()
        await sender.cancel_worker()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


def run(app: Application, settings) -> None:
    """اجرای بلندمدت با مدیریت SIGINT/SIGTERM."""

    async def _runner() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        import signal  # noqa: PLC0415

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:  # ویندوز
                pass
        task = asyncio.create_task(_serve(app, settings))
        await stop.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(_runner())


if __name__ == "__main__":
    from bot.config.settings import get_settings
    from bot.main import create_application

    run(create_application(), get_settings())
