"""صف ارسال انبوه — همه‌ی پیام‌های گروهی با نرخ ۵ گیرنده در ثانیه.

تلگرام برای ارسال انبوه خطای 429 (TooManyRequests) می‌دهد؛ همه‌ی
ارسال‌های انبوه (پیام همگانی و یادآورها) از این صف واحد می‌گذرند تا:

- حداکثر **۵ پیام در ثانیه** ارسال شود (فاصله‌ی ۰٫۲ ثانیه)؛
- خطای ``RetryAfter`` با صبرِ مدتِ اعلام‌شده + تلاش دوباره هندل شود؛
- خطای دیگر تلگرام فقط همان گیرنده را شکست بخوراند و صف ادامه دهد.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from telegram.error import RetryAfter, TelegramError

logger = logging.getLogger(__name__)

SEND_INTERVAL = 0.2  # ۵ پیام در ثانیه
_MAX_ATTEMPTS = 3  # تلاش کل به‌ازای هر گیرنده (شامل صبرهای 429)

_queue: asyncio.Queue | None = None
_worker: asyncio.Task | None = None


def ensure_worker() -> bool:
    """شروع کارگر صف (در صورت نبود). بدون حلقه‌ی در حال اجرا → False."""
    global _queue, _worker
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    if _queue is None:
        _queue = asyncio.Queue()
    if _worker is None or _worker.done():
        _worker = loop.create_task(_run_worker())
        logger.info("صف ارسال انبوه روشن شد (نرخ ۵ در ثانیه)")
    return True


async def cancel_worker() -> None:
    """توقف کارگر صف در خاموشی ربات؛ آیتم‌های مانده شکست خورده می‌شوند."""
    global _worker, _queue
    if _worker is not None:
        _worker.cancel()
        try:
            await _worker
        except asyncio.CancelledError:
            pass
        _worker = None
    if _queue is not None:
        while not _queue.empty():  # کسی منتظر نماند
            _send, future = _queue.get_nowait()
            if not future.done():
                future.set_result(False)
        _queue = None


def submit(send: Callable[[], Awaitable]) -> asyncio.Future | None:
    """گذاشتن یک ارسال در صف؛ Future نتیجه (True/False) برمی‌گرداند.

    ``send`` یک callable async است که ارسال واقعی را انجام می‌دهد؛
    کارگر صف آن را با نرخ کنترل‌شده و هندل 429 اجرا می‌کند.
    """
    if not ensure_worker():
        return None
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    _queue.put_nowait((send, future))
    return future


async def _run_worker() -> None:
    """کارگر: یک ارسال در هر فاصله‌ی SEND_INTERVAL."""
    while True:
        send, future = await _queue.get()
        try:
            ok = await _send_with_retry(send)
            if not future.done():
                future.set_result(ok)
        except Exception:  # noqa: BLE001 — کارگر هرگز نمی‌میرد
            logger.exception("خطای غیرمنتظره در صف ارسال")
            if not future.done():
                future.set_result(False)
        await asyncio.sleep(SEND_INTERVAL)


async def _send_with_retry(send: Callable[[], Awaitable]) -> bool:
    """اجرای یک ارسال با تلاش دوباره پس از 429."""
    for _attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            await send()
            return True
        except RetryAfter as exc:
            wait = float(exc.retry_after) + 1.0
            logger.warning("429 از تلگرام — %s ثانیه صبر و تلاش دوباره", wait)
            await asyncio.sleep(wait)
        except TelegramError as exc:
            logger.warning("ارسال انبوه ناموفق بود: %s", exc)
            return False
    return False
