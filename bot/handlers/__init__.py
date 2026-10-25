"""ثبت هندلرها — ترتیب ثبت حیاتی است: start → seminars → wizard → admin → errors."""

from telegram.ext import Application

from bot.handlers import admin, channels, errors, menu_buttons, seminars, start, wizard


def register_handlers(app: Application) -> None:
    start.register(app)
    seminars.register(app)
    channels.register(app)  # /channels + صفحات آماری ادمین کانال
    menu_buttons.register(app)  # گروه ۱: دکمه‌های ثابت (قبل از ویزارد)
    admin.register(app)  # گروه ۰: دیسپچر ورودی مدیر (بدون state عبور می‌دهد)
    wizard.register(app)  # گروه ۱
    errors.register(app)  # گروه ۲
