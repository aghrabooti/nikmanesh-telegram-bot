"""تست ویزارد ثبت‌نام ۷ مرحله‌ای: نام ← پایه ← رشته ← شهر ← تلفن ← پیامک."""

from __future__ import annotations

from bot.config import content
from bot.services import seminars
from tests.helpers import NON_ADMIN, last_send, send_text, share_contact, tap, texts


def _reply_rows(keyboard) -> list[list[str]]:
    return [[b.text for b in row] for row in keyboard.keyboard]


async def _create(app, bot, *, title="سمینار آمادگی تیزهوشان", message="-"):
    await tap(app, bot, "adm:sem:new")
    await send_text(app, bot, title)
    await send_text(app, bot, message)


async def _start(app, bot, *, user=NON_ADMIN):
    await tap(app, bot, "sem:reg:1", user=user)
    await send_text(app, bot, "علی محمدی", user=user)  # نام → پایه


async def test_step_texts_and_keyboards(bot_app):
    """پرامپت و کیبورد هر مرحله دقیقاً طبق مشخصات."""
    app, bot = bot_app
    await _create(app, bot)
    await tap(app, bot, "sem:reg:1", user=NON_ADMIN)

    # ۱) نام
    sent = last_send(bot)
    assert sent["text"] == content.WIZ_NAME_TEXT
    assert _reply_rows(sent["reply_markup"]) == [["🔙 بازگشت"]]

    # ۲) پایه
    await send_text(app, bot, "علی محمدی", user=NON_ADMIN)
    sent = last_send(bot)
    assert sent["text"] == content.WIZ_GRADE_TEXT
    assert _reply_rows(sent["reply_markup"]) == [
        ["کنکوری ۴۰۶"],
        ["کنکوری ۴۰۷"],
        ["کنکوری ۴۰۸"],
        ["⬅️ مرحله قبل", "🔙 بازگشت"],
    ]

    # ۳) رشته
    await send_text(app, bot, "کنکوری ۴۰۷", user=NON_ADMIN)
    sent = last_send(bot)
    assert sent["text"] == content.WIZ_FIELD_TEXT
    assert _reply_rows(sent["reply_markup"])[:1] == [["تجربی", "ریاضی", "انسانی"]]
    assert _reply_rows(sent["reply_markup"])[1] == ["⬅️ مرحله قبل", "🔙 بازگشت"]

    # ۴) شهر
    await send_text(app, bot, "ریاضی", user=NON_ADMIN)
    sent = last_send(bot)
    assert sent["text"] == content.WIZ_CITY_TEXT

    # ۵) شماره تلگرام
    await send_text(app, bot, "تهران", user=NON_ADMIN)
    sent = last_send(bot)
    assert sent["text"] == content.WIZ_PHONE_TEXT
    rows = _reply_rows(sent["reply_markup"])
    assert rows[0] == ["📱 ارسال شماره تلفن"]
    assert rows[1] == ["⬅️ مرحله قبل", "🔙 بازگشت"]
    assert sent["reply_markup"].keyboard[0][0].request_contact is True
    assert not sent["reply_markup"].one_time_keyboard  # کیبورد پایدار بماند

    # ۶) شماره پیامک
    await share_contact(app, bot, user=NON_ADMIN, phone="09121234567")
    sent = last_send(bot)
    assert sent["text"] == content.WIZ_SMS_TEXT


async def test_name_english_rejected(bot_app):
    app, bot = bot_app
    await _create(app, bot)
    await tap(app, bot, "sem:reg:1", user=NON_ADMIN)
    await send_text(app, bot, "Ali Mohammad", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_NAME_INVALID
    await send_text(app, bot, "علی محمدی", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_GRADE_TEXT


async def test_grade_invalid_re_prompts(bot_app):
    """متن خارج از گزینه‌های پایه → تکرار همان پرامپت."""
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, "دهم", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_GRADE_TEXT


async def test_field_invalid_re_prompts(bot_app):
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)
    await send_text(app, bot, "هنری", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_FIELD_TEXT


async def test_city_invalid(bot_app):
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)
    await send_text(app, bot, "تجربی", user=NON_ADMIN)
    await send_text(app, bot, "tehran", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_CITY_INVALID
    await send_text(app, bot, "تهران", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_PHONE_TEXT


async def test_phone_step_typed_number_accepted(bot_app):
    """مرحله‌ی شماره تلگرام: تایپ دستی شماره‌ی معتبر هم قبول است (جایگزین دکمه)."""
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)
    await send_text(app, bot, "انسانی", user=NON_ADMIN)
    await send_text(app, bot, "تهران", user=NON_ADMIN)
    await send_text(app, bot, "۰۹۱۲۳۴۵۶۷۸۹", user=NON_ADMIN)  # تایپ فارسی
    assert last_send(bot)["text"] == content.WIZ_SMS_TEXT  # رفته به مرحله‌ی بعد
    reg = seminars.get_registration(NON_ADMIN.id, 1)
    assert reg["phone"] == "+989123456789"


async def test_phone_step_typed_garbage_rejected(bot_app):
    """تایپ غیرشماره در مرحله‌ی شماره تلگرام → پیام راهنما (هر دو مسیر)."""
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)
    await send_text(app, bot, "انسانی", user=NON_ADMIN)
    await send_text(app, bot, "تهران", user=NON_ADMIN)
    await send_text(app, bot, "شماره ندارم", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_PHONE_INVALID
    assert "۰۹۱۲۳۴۵۶۷۸۹" in last_send(bot)["text"]  # راهنمای تایپ دستی


async def test_sms_confirm_button_uses_telegram_phone(bot_app):
    """دکمه‌ی «✅ شماره‌م درسته»: همان شماره تلگرام برای پیامک — بدون ورودی اجباری."""
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)
    await send_text(app, bot, "تجربی", user=NON_ADMIN)
    await send_text(app, bot, "تهران", user=NON_ADMIN)
    await share_contact(app, bot, user=NON_ADMIN, phone="09121234567")
    sent = last_send(bot)
    assert sent["text"] == content.WIZ_SMS_TEXT
    # کیبورد مرحله: دکمه‌ی تأیید + ناوبری
    rows = _reply_rows(sent["reply_markup"])
    assert rows[0] == [content.LBL_PHONE_OK]
    assert rows[1] == ["⬅️ مرحله قبل", "🔙 بازگشت"]

    await send_text(app, bot, content.LBL_PHONE_OK, user=NON_ADMIN)
    reg = seminars.get_registration(NON_ADMIN.id, 1)
    assert reg["is_complete"] == 1
    assert reg["phone"] == "+989121234567"
    assert reg["sms_phone"] == "09121234567"  # از شماره تلگرام گرفته شد


async def test_sms_confirm_without_phone_prompts_typing(bot_app):
    """قدیمی/بدون شماره‌ی تلگرام: دکمه‌ی تأیید → راهنمای ورود دستی."""
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)
    await send_text(app, bot, "تجربی", user=NON_ADMIN)
    await send_text(app, bot, "تهران", user=NON_ADMIN)
    await share_contact(app, bot, user=NON_ADMIN, phone="09121234567")
    # شبیه‌سازی رکورد قدیمی بدون شماره‌ی تلگرام
    seminars.save_registration(NON_ADMIN.id, 1, next_step=seminars.STEP_SMS, phone="")
    await send_text(app, bot, content.LBL_PHONE_OK, user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_SMS_INVALID
    # ورود دستی همچنان کار می‌کند
    await send_text(app, bot, "۰۹۳۵۱۱۱۲۲۳۳", user=NON_ADMIN)
    reg = seminars.get_registration(NON_ADMIN.id, 1)
    assert reg["is_complete"] == 1 and reg["sms_phone"] == "09351112233"


async def test_sms_validation_variants(bot_app):
    """شماره پیامک: باید با ۰۹ شروع شود و ۱۱ رقم باشد — فارسی و انگلیسی."""
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)
    await send_text(app, bot, "تجربی", user=NON_ADMIN)
    await send_text(app, bot, "تهران", user=NON_ADMIN)
    await share_contact(app, bot, user=NON_ADMIN, phone="09121234567")

    for raw, ok in (
        ("09123456789", True),
        ("۰۹۱۲۳۴۵۶۷۸۹", True),  # ارقام فارسی
        ("0912 345 6789", True),  # فاصله‌ها نادیده گرفته می‌شوند
        ("9123456789", False),  # بدون ۰
        ("0912345678", False),  # ۱۰ رقم
        ("091234567890", False),  # ۱۲ رقم
        ("+989123456789", False),  # فرمت غیرمجاز در این مرحله
        ("سلام", False),
    ):
        await send_text(app, bot, raw, user=NON_ADMIN)
        if ok:
            # پیام آخر + سپس منوی ثابت (آخرین پیام، منو است)
            assert "تکمیل شد" in texts(bot)[-2], f"{raw} باید قبول شود"
            assert last_send(bot)["text"] == content.MENU_HINT_TEXT
            return  # ثبت‌نام کامل شد
        assert last_send(bot)["text"] == content.WIZ_SMS_INVALID, f"{raw} باید رد شود"


async def test_sms_invalid_then_valid(bot_app):
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, "کنکوری ۴۰۸", user=NON_ADMIN)
    await send_text(app, bot, "ریاضی", user=NON_ADMIN)
    await send_text(app, bot, "شیراز", user=NON_ADMIN)
    await share_contact(app, bot, user=NON_ADMIN, phone="09121234567")

    await send_text(app, bot, "12345", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_SMS_INVALID
    await send_text(app, bot, "۰۹۱۲۳۴۵۶۷۸۹", user=NON_ADMIN)

    reg = seminars.get_registration(NON_ADMIN.id, 1)
    assert reg["is_complete"] == 1
    assert reg["sms_phone"] == "09123456789"
    assert reg["phone"] == "+989121234567"  # شماره تلگرام از اشتراک مخاطب
    assert reg["grade"] == "کنکوری ۴۰۸"
    assert reg["field"] == "ریاضی"
    assert reg["city"] == "شیراز"


async def test_prev_button_steps_back(bot_app):
    """«⬅️ مرحله قبل» یک مرحله عقب می‌رود و داده‌ها می‌مانند."""
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)  # تا پایه
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)  # تا رشته
    await send_text(app, bot, content.LBL_WIZ_PREV, user=NON_ADMIN)  # → پایه
    assert last_send(bot)["text"] == content.WIZ_GRADE_TEXT
    assert seminars.get_registration(NON_ADMIN.id, 1)["grade"] == "کنکوری ۴۰۶"

    await send_text(app, bot, content.LBL_WIZ_PREV, user=NON_ADMIN)  # → نام
    assert last_send(bot)["text"] == content.WIZ_NAME_TEXT
    assert seminars.get_registration(NON_ADMIN.id, 1)["name"] == "علی محمدی"


async def test_back_button_exits_and_saves(bot_app):
    """«🔙 بازگشت» از ویزارد خارج می‌شود؛ صفحه‌ی سمینار و منوی ثابت برمی‌گردد."""
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, content.LBL_WIZ_BACK, user=NON_ADMIN)

    assert last_send(bot)["text"] == content.MENU_HINT_TEXT  # منوی ثابت
    assert _reply_rows(last_send(bot)["reply_markup"])[0] == ["وبینار سمینار آمادگی تیزهوشان"]
    reg = seminars.get_registration(NON_ADMIN.id, 1)
    assert reg["current_step"] == seminars.STEP_GRADE  # پیشرفت حفظ شد
    assert reg["name"] == "علی محمدی"

    # ادامه از همان‌جا
    await tap(app, bot, "sem:reg:1", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_GRADE_TEXT


async def test_wizard_resume_same_step(bot_app):
    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await tap(app, bot, "sem:reg:1", user=NON_ADMIN)  # ورود دوباره
    assert last_send(bot)["text"] == content.WIZ_GRADE_TEXT


async def test_fixed_menu_buttons_still_work_mid_wizard(bot_app):
    """دکمه‌های ثابت (از کیبورد قدیمی) وسط ویزارد هم کار می‌کنند."""

    app, bot = bot_app
    await _create(app, bot)
    await _start(app, bot)
    await send_text(app, bot, content.LBL_CONTACT, user=NON_ADMIN)
    assert last_send(bot)["text"] == content.CONTACT_TEXT
    # ویزارد همچنان فعال است
    await send_text(app, bot, "کنکوری ۴۰۶", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_FIELD_TEXT
