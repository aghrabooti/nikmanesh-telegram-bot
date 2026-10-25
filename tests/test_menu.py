"""تست دکمه‌های ثابت (ریپلای کیبورد): وبینار فعال، درباره، ارتباط با ما."""

from __future__ import annotations

from bot.config import content
from bot.services import seminars, settings
from tests.helpers import NON_ADMIN, last_send, send_command, send_text, tap


def _reply_rows(keyboard) -> list[list[str]]:
    return [[b.text for b in row] for row in keyboard.keyboard]


async def test_webinar_button_tracks_active_seminar(bot_app):
    """دکمه‌ی «وبینار …» همیشه جدیدترین سمینار باز را نشان می‌دهد."""
    app, bot = bot_app
    seminars.create_seminar(title="قدیمی")
    seminars.create_seminar(title="جدید")
    await send_command(app, bot, "/start", user=NON_ADMIN)

    menu = last_send(bot)
    assert _reply_rows(menu["reply_markup"])[0] == ["وبینار جدید"]

    # بستن وبینار فعال → کلید تازه، وبینار باز قبلی را نشان می‌دهد
    seminars.set_seminar_open(2, False)
    await tap(app, bot, "main")
    assert last_send(bot)["reply_markup"] is not None  # اینلاین شیشه‌ای هنوز قدیمی است
    await send_text(app, bot, "وبینار جدید", user=NON_ADMIN)  # کلید قدیمی کیبورد کاربر
    refreshed = last_send(bot)
    assert refreshed["text"] == content.WELCOME_TEXT
    assert _reply_rows(refreshed["reply_markup"])[0] == ["وبینار قدیمی"]


async def test_webinar_button_opens_seminar(bot_app):
    """فشردن «وبینار …» → صفحه‌ی همان سمینار با دکمه‌ی ثبت‌نام."""
    app, bot = bot_app
    seminars.create_seminar(title="آزمون ریاضی")
    await send_command(app, bot, "/start", user=NON_ADMIN)
    await send_text(app, bot, "وبینار آزمون ریاضی", user=NON_ADMIN)

    screen = last_send(bot)
    assert "آزمون ریاضی" in screen["text"]
    buttons = [b for row in screen["reply_markup"].inline_keyboard for b in row]
    assert [b.text for b in buttons] == ["📝 ثبت‌نام"]
    assert buttons[0].callback_data == "sem:reg:1"


async def test_contact_button(bot_app):
    """دکمه‌ی «ارتباط با ما» → متن دقیق + منوی ثابت."""
    app, bot = bot_app
    await send_command(app, bot, "/start", user=NON_ADMIN)
    await send_text(app, bot, content.LBL_CONTACT, user=NON_ADMIN)

    screen = last_send(bot)
    assert screen["text"] == content.CONTACT_TEXT
    assert "09021444799" in screen["text"]
    assert "@nikmanesh_academyy" in screen["text"]
    assert "nikmaneshedu.ir" in screen["text"]
    assert _reply_rows(screen["reply_markup"]) == [["درباره آکادمی نیک منش", "ارتباط با ما"]]


async def test_about_button_default_text(bot_app):
    app, bot = bot_app
    await send_command(app, bot, "/start", user=NON_ADMIN)
    await send_text(app, bot, content.LBL_ABOUT, user=NON_ADMIN)
    assert last_send(bot)["text"] == content.ABOUT_DEFAULT_TEXT


async def test_fixed_buttons_work_mid_wizard(bot_app):
    """وسط ثبت‌نام هم دکمه‌های ثابت کار می‌کنند و پیشرفت حفظ می‌شود."""
    app, bot = bot_app
    seminars.create_seminar(title="آزمون")
    await tap(app, bot, "sem:reg:1", user=NON_ADMIN)
    await send_text(app, bot, "علی محمدی", user=NON_ADMIN)  # → پایه

    await send_text(app, bot, content.LBL_CONTACT, user=NON_ADMIN)  # دکمه‌ی ثابت
    assert last_send(bot)["text"] == content.CONTACT_TEXT

    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)  # ادامه‌ی ویزارد
    assert last_send(bot)["text"] == content.WIZ_FIELD_TEXT


async def test_about_screen_and_admin_edit(bot_app):
    """صفحه‌ی درباره: متن پیش‌فرض → ادمین ویرایش می‌کند → «پیش‌فرض» = ریست."""
    app, bot = bot_app
    await send_command(app, bot, "/start", user=NON_ADMIN)
    await send_text(app, bot, content.LBL_ABOUT, user=NON_ADMIN)
    assert last_send(bot)["text"] == content.ABOUT_DEFAULT_TEXT

    # ادمین متن را عوض می‌کند
    await tap(app, bot, "adm:about")
    await send_text(app, bot, "متن جدید درباره‌ی آکادمی ✍️")
    assert settings.get_about_text() == "متن جدید درباره‌ی آکادمی ✍️"

    # کاربر متن جدید را می‌بیند
    await send_text(app, bot, content.LBL_ABOUT, user=NON_ADMIN)
    assert last_send(bot)["text"] == "متن جدید درباره‌ی آکادمی ✍️"

    # «پیش‌فرض» = بازگشت به متن اولیه
    await tap(app, bot, "adm:about")
    await send_text(app, bot, "پیش‌فرض")
    assert settings.get_about_text() == content.ABOUT_DEFAULT_TEXT
