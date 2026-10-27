"""تست فلوهای کاربر: شروع (پیام + دکمه‌ی شیشه‌ای + منوی ثابت)، سمینار و ثبت‌نام."""

from __future__ import annotations

from bot.config import content
from bot.services import seminars
from tests.helpers import (
    NON_ADMIN,
    callbacks,
    last_edit,
    last_send,
    send_command,
    send_text,
    share_contact,
    tap,
    texts,
)


async def _create_seminar(app, bot, *, title="سمینار آمادگی تیزهوشان", message="-"):
    """ساخت سمینار از پنل ادمین (فرم ۲ مرحله‌ای: اسم + پیام آخر)."""
    await tap(app, bot, "adm:sem:new")
    await send_text(app, bot, title)
    await send_text(app, bot, message)


def _last_two_sends(bot):
    return [c.kwargs for c in bot.send_message.await_args_list[-2:]]


def _reply_rows(keyboard) -> list[list[str]]:
    return [[b.text for b in row] for row in keyboard.keyboard]


async def test_start_welcome_glass_button_and_reply_menu(bot_app):
    """/start: پیام خوش‌آمد + دکمه‌ی شیشه‌ای وبینار؛ سپس منوی ثابت (ریپلای)."""
    app, bot = bot_app
    await _create_seminar(app, bot)

    await send_command(app, bot, "/start", user=NON_ADMIN)
    welcome, menu = _last_two_sends(bot)

    assert welcome["text"] == content.WELCOME_TEXT
    webinar_btn = welcome["reply_markup"].inline_keyboard[0][0]
    assert webinar_btn.text == "وبینار سمینار آمادگی تیزهوشان"
    assert webinar_btn.callback_data == "sem:v:1"
    assert webinar_btn.style == "success"  # شیشه‌ای رنگی

    assert menu["text"] == content.MENU_HINT_TEXT
    assert _reply_rows(menu["reply_markup"]) == [
        ["وبینار سمینار آمادگی تیزهوشان"],
        ["درباره آکادمی نیک منش", "ارتباط با ما"],
    ]


async def test_start_no_seminars_only_fixed_buttons(bot_app):
    """بدون سمینار باز: بدون دکمه‌ی شیشه‌ای؛ منوی ثابت فقط درباره/ارتباط."""
    app, bot = bot_app
    await send_command(app, bot, "/start", user=NON_ADMIN)
    welcome, menu = _last_two_sends(bot)

    assert welcome["text"] == content.WELCOME_TEXT
    assert welcome["reply_markup"] is None
    assert _reply_rows(menu["reply_markup"]) == [["درباره آکادمی نیک منش", "ارتباط با ما"]]


async def test_id_command(bot_app):
    app, bot = bot_app
    await send_command(app, bot, "/id", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.ID_TEXT.format(user_id=NON_ADMIN.id)


async def test_view_seminar_screen(bot_app):
    app, bot = bot_app
    await _create_seminar(app, bot, message="پیام اختصاصی {name}")
    await send_command(app, bot, "/start", user=NON_ADMIN)
    await tap(app, bot, "sem:v:1", user=NON_ADMIN)

    edited = last_edit(bot)
    assert "سمینار آمادگی تیزهوشان" in edited["text"]
    assert "برای ثبت‌نام" in edited["text"]
    # فقط دکمه‌ی اقدام اصلی — منوی ثابت جای «منوی اصلی» را گرفته
    assert callbacks(edited["reply_markup"]) == ["sem:reg:1"]


async def test_view_closed_seminar(bot_app):
    app, bot = bot_app
    await _create_seminar(app, bot)
    await tap(app, bot, "adm:sem:open:1")  # ادمین می‌بندد
    await tap(app, bot, "sem:v:1", user=NON_ADMIN)

    edited = last_edit(bot)
    assert content.SEM_CLOSED_TEXT in edited["text"]
    assert edited["reply_markup"] is None  # هیچ دکمه‌ای نیست


async def test_seminar_not_found(bot_app):
    app, bot = bot_app
    await tap(app, bot, "sem:v:999", user=NON_ADMIN)
    assert last_edit(bot)["text"] == content.SEM_NOT_FOUND_TEXT


async def test_full_registration_flow(bot_app):
    """فلو کامل ۷ مرحله‌ای: نام ← پایه ← رشته ← شهر ← تلفن ← شماره جایگزین ← پیام آخر."""
    app, bot = bot_app
    await _create_seminar(app, bot)
    await tap(app, bot, "sem:reg:1", user=NON_ADMIN)

    await send_text(app, bot, "علی محمدی", user=NON_ADMIN)  # نام
    await send_text(app, bot, "کنکوری ۴۰۷", user=NON_ADMIN)  # پایه
    await send_text(app, bot, "تجربی", user=NON_ADMIN)  # رشته
    await send_text(app, bot, "تهران", user=NON_ADMIN)  # شهر
    await share_contact(app, bot, user=NON_ADMIN, phone="09121234567")  # تلفن تلگرام
    await send_text(app, bot, "۰۹۳۵۱۲۳۴۵۶۷", user=NON_ADMIN)  # شماره جایگزین

    final, menu = _last_two_sends(bot)
    assert final["text"] == content.FINAL_MSG.format(
        name="علی محمدی",
        seminar="سمینار آمادگی تیزهوشان",
        date="—",
        link="",
    )
    assert menu["text"] == content.MENU_HINT_TEXT  # منوی ثابت برمی‌گردد
    reg = seminars.get_registration(NON_ADMIN.id, 1)
    assert reg["is_complete"] == 1
    assert reg["phone"] == "+989121234567"
    assert reg["alternate_phone"] == "09351234567"
    assert reg["grade"] == "کنکوری ۴۰۷"
    assert reg["field"] == "تجربی"
    assert reg["current_step"] == seminars.STEP_DONE


async def test_custom_final_message(bot_app):
    """پیام آخر اختصاصی سمینار برای کاربر ارسال می‌شود."""
    app, bot = bot_app
    await _create_seminar(app, bot, message="سلام {name} جان، به «{seminar}» خوش آمدی 🌟")
    await tap(app, bot, "sem:reg:1", user=NON_ADMIN)
    await send_text(app, bot, "علی محمدی", user=NON_ADMIN)
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)
    await send_text(app, bot, "ریاضی", user=NON_ADMIN)
    await send_text(app, bot, "تهران", user=NON_ADMIN)
    await share_contact(app, bot, user=NON_ADMIN, phone="09121234567")
    await send_text(app, bot, "09123456789", user=NON_ADMIN)

    assert texts(bot)[-2] == "سلام علی محمدی جان، به «سمینار آمادگی تیزهوشان» خوش آمدی 🌟"


async def test_back_keeps_progress(bot_app):
    """«🔙 بازگشت» پیشرفت را نگه می‌دارد و ادامه از همان مرحله است."""
    app, bot = bot_app
    await _create_seminar(app, bot)
    await tap(app, bot, "sem:reg:1", user=NON_ADMIN)
    await send_text(app, bot, "علی محمدی", user=NON_ADMIN)
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)
    await send_text(app, bot, content.LBL_WIZ_BACK, user=NON_ADMIN)  # بازگشت

    assert last_send(bot)["text"] == content.MENU_HINT_TEXT
    await tap(app, bot, "sem:reg:1", user=NON_ADMIN)  # ادامه از همان‌جا
    assert last_send(bot)["text"] == content.WIZ_FIELD_TEXT
    reg = seminars.get_registration(NON_ADMIN.id, 1)
    assert reg["current_step"] == seminars.STEP_FIELD
    assert reg["grade"] == "کنکوری ۴۰۶"


async def test_complete_registration_status(bot_app):
    app, bot = bot_app
    await _create_seminar(app, bot, message="خوش آمدی {name}!")
    await tap(app, bot, "sem:reg:1", user=NON_ADMIN)
    for step in ("علی محمدی", "کنکوری ۴۰۶", "ریاضی", "تهران"):
        await send_text(app, bot, step, user=NON_ADMIN)
    await share_contact(app, bot, user=NON_ADMIN, phone="09121234567")
    await send_text(app, bot, "09123456789", user=NON_ADMIN)

    await tap(app, bot, "sem:v:1", user=NON_ADMIN)
    edited = last_edit(bot)
    assert content.ALREADY_DONE_TEXT in edited["text"]
    assert edited["reply_markup"] is None  # بدون لینک، بدون دکمه


async def test_fallback_text(bot_app):
    app, bot = bot_app
    await send_text(app, bot, "سلام چی میشه؟", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.FALLBACK_TEXT


async def test_non_admin_admin_command_denied(bot_app):
    app, bot = bot_app
    await send_command(app, bot, "/admin", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.ADMIN_ONLY_TEXT


async def test_main_menu_callback_from_admin_panel(bot_app):
    """دکمه‌ی 🏠 پنل ادمین → پیام خوش‌آمد کاربر با دکمه‌ی شیشه‌ای وبینار."""
    app, bot = bot_app
    await _create_seminar(app, bot)
    await tap(app, bot, "adm:sems")
    await tap(app, bot, "main")

    edited = last_edit(bot)
    assert edited["text"] == content.WELCOME_TEXT
    assert callbacks(edited["reply_markup"]) == ["sem:v:1"]
