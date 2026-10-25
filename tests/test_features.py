"""تست سه قابلیت جدید: قالب اختصاصی/آمار جدا، پیام همگانی، یادآورها."""

from __future__ import annotations

from datetime import datetime, timedelta

from bot.config import content
from bot.services import reminders, seminars
from tests.helpers import (
    NON_ADMIN,
    USER,
    callbacks,
    last_answer,
    last_edit,
    last_send,
    send_command,
    send_photo_message,
    send_text,
    share_contact,
    tap,
)


async def _create(**kwargs):
    defaults = dict(
        title="سمینار آمادگی تیزهوشان",
        description="مرور روش مطالعه",
        date_text="پنجشنبه ۱۵ آبان، ساعت ۱۸",
        link="https://t.me/seminar_room",
        levels=["ششم", "نهم"],
    )
    defaults.update(kwargs)
    return seminars.create_seminar(**defaults)


async def _register(app, bot, seminar_id, *, user=NON_ADMIN, complete=True, name="علی محمدی"):
    """ثبت‌نام (کامل یا ناتمام تا مرحله‌ی پایه)."""
    await tap(app, bot, f"sem:reg:{seminar_id}", user=user)
    await send_text(app, bot, name, user=user)
    if not complete:
        return
    await send_text(app, bot, "کنکوری ۴۰۶", user=user)
    await send_text(app, bot, "تجربی", user=user)
    await send_text(app, bot, "تهران", user=user)
    await share_contact(app, bot, user=user, phone="09121234567")
    await send_text(app, bot, "۰۹۱۲۳۴۵۶۷۸۹", user=user)


def _texts(bot) -> list[str]:
    return [c.kwargs["text"] for c in bot.send_message.await_args_list]


def _reminder_texts(bot) -> list[str]:
    return [c.kwargs["text"] for c in bot.send_message.await_args_list]


# ---------------------------------------------------------------------------
# ۱) قالب پیام نهایی اختصاصی + آمار جداگانه‌ی هر سمینار
# ---------------------------------------------------------------------------


async def test_custom_final_message_per_seminar(bot_app):
    """قالب اختصاصی سمینار جای قالب سراسری را می‌گیرد؛ دیگری پیش‌فرض می‌ماند."""
    app, bot = bot_app
    custom = await _create(
        title="سمینار ویژه",
        link="https://t.me/room_x",
        levels=[],
        message_template="سلام {name} جان!\nسمینار «{seminar}» — {date}\n{link}",
    )
    default = await _create(title="سمینار عادی", link="https://t.me/room_y", levels=[])

    await _register(app, bot, custom["id"])
    final_custom = _texts(bot)[-2]  # ماقبل آخر — بعدش منوی ثابت می‌آید
    assert final_custom.startswith("سلام علی محمدی جان!")
    assert "سمینار «سمینار ویژه»" in final_custom
    assert "https://t.me/room_x" in final_custom

    await _register(app, bot, default["id"])
    final_default = _texts(bot)[-2]
    assert "علی محمدی عزیز" in final_default  # قالب سراسری FINAL_MSG


async def test_edit_message_template_from_panel(bot_app):
    app, bot = bot_app
    await _create()
    await tap(app, bot, "adm:sem:1")
    await tap(app, bot, "adm:sem:e:1")
    await tap(app, bot, "adm:sem:ef:1:message_template")
    assert last_edit(bot)["text"] == content.ADMIN_EDIT_PROMPTS["message_template"]
    await send_text(app, bot, "پیام اختصاصی {name} برای {seminar}")
    assert "ذخیره شد" in _texts(bot)[-2]
    assert seminars.get_seminar(1)["message_template"] == "پیام اختصاصی {name} برای {seminar}"
    # بازگشت به پیش‌فرض
    await tap(app, bot, "adm:sem:ef:1:message_template")
    await send_text(app, bot, "پیش‌فرض")
    assert seminars.get_seminar(1)["message_template"] == ""


async def test_edit_starts_at_from_panel(bot_app):
    app, bot = bot_app
    await _create()
    await tap(app, bot, "adm:sem:1")
    await tap(app, bot, "adm:sem:e:1")
    await tap(app, bot, "adm:sem:ef:1:starts_at")
    await send_text(app, bot, "۱۴۰۵/۰۸/۱۵ ۱۸:۳۰")
    stored = seminars.get_seminar(1)["starts_at"]
    assert stored.startswith("2026-11-") and "18:30" in stored
    # حذف زمان با «هیچ»
    await tap(app, bot, "adm:sem:ef:1:starts_at")
    await send_text(app, bot, "هیچ")
    assert seminars.get_seminar(1)["starts_at"] == ""
    # مقدار نامعتبر → خطا
    await tap(app, bot, "adm:sem:ef:1:starts_at")
    await send_text(app, bot, "فردا صبح")
    assert "زمان شروع" in last_send(bot)["text"]


async def test_sems_list_shows_per_seminar_stats(bot_app):
    """صفحه‌ی مدیریت سمینارها: آمار هر سمینار جداگانه."""
    app, bot = bot_app
    first = await _create()
    second = await _create(title="سمینار دوم", link="https://t.me/r2", levels=[])
    await _register(app, bot, first["id"])  # کامل
    await _register(app, bot, second["id"], complete=False)  # ناتمام

    await tap(app, bot, "adm:sems")
    text = last_edit(bot)["text"]
    assert "🟢 <b>سمینار آمادگی تیزهوشان</b> — ثبت‌نام <b>۱</b> (کامل <b>۱</b>)" in text
    assert "🟢 <b>سمینار دوم</b> — ثبت‌نام <b>۱</b> (کامل <b>۰</b>)" in text


# ---------------------------------------------------------------------------
# ۲) پیام همگانی (broadcast)
# ---------------------------------------------------------------------------


async def test_broadcast_full_flow(bot_app):
    app, bot = bot_app
    # دو کاربر ربات را استارت کرده‌اند
    await send_command(app, bot, "/start", user=NON_ADMIN)
    await send_command(app, bot, "/menu", user=USER)

    await tap(app, bot, "adm:bcast")
    assert content.BCAST_PROMPT in last_edit(bot)["text"]
    await send_text(app, bot, "سلام به همه 🎉", user=USER)

    sent = last_send(bot)
    assert content.BCAST_CONFIRM_TEXT.format(count="۲", preview="سلام به همه 🎉") == sent["text"]
    assert callbacks(sent["reply_markup"]) == ["adm:bcast:go", "adm:bcast:no"]

    await tap(app, bot, "adm:bcast:go")
    # کپی همان پیام مدیر برای هر دو کاربر
    assert bot.copy_message.await_count == 2
    target_chats = {c.kwargs["chat_id"] for c in bot.copy_message.await_args_list}
    assert target_chats == {NON_ADMIN.id, USER.id}
    source_ids = {
        (c.kwargs["from_chat_id"], c.kwargs["message_id"]) for c in bot.copy_message.await_args_list
    }
    assert len(source_ids) == 1  # همه از همان یک پیام مدیر کپی شده‌اند
    assert "موفق: ۲" in last_send(bot)["text"]
    # state پاک شده: پیام بعدی مدیر fallback است
    await send_text(app, bot, "پیام آزاد", user=USER)
    assert content.FALLBACK_TEXT in _texts(bot)[-1]


async def test_broadcast_accepts_photo(bot_app):
    """پیام همگانی می‌تواند عکس/ویدیو/فوروارد باشد (copy_message)."""
    app, bot = bot_app
    await send_command(app, bot, "/start", user=NON_ADMIN)
    await tap(app, bot, "adm:bcast")
    await send_photo_message(app, bot, user=USER, caption="عکس خبری")
    sent = last_send(bot)
    assert "۱ کاربر" in sent["text"]
    assert "📷 عکس" in sent["text"]
    await tap(app, bot, "adm:bcast:go")
    assert bot.copy_message.await_count == 1


async def test_broadcast_cancel_and_empty(bot_app):
    app, bot = bot_app
    await send_command(app, bot, "/start", user=NON_ADMIN)
    await tap(app, bot, "adm:bcast")
    await send_text(app, bot, "متنی که ارسال نمی‌شود", user=USER)
    await tap(app, bot, "adm:bcast:no")
    assert bot.copy_message.await_count == 0
    assert content.ADMIN_MENU_HEADER in last_edit(bot)["text"]


async def test_broadcast_denied_for_non_admin(bot_app):
    app, bot = bot_app
    await send_command(app, bot, "/start", user=NON_ADMIN)
    await tap(app, bot, "adm:bcast", user=NON_ADMIN)
    assert content.ADMIN_ONLY_TEXT in last_answer(bot)["text"]
    assert bot.copy_message.await_count == 0


# ---------------------------------------------------------------------------
# ۳) یادآورهای خودکار
# ---------------------------------------------------------------------------


async def test_reminder_nudge_incomplete_daily(bot_app):
    """ناتمام‌ها روزانه (هر ۲۴ ساعت) یادآوری می‌شوند؛ زودتر نه، و دکمه‌ی ادامه دارد."""
    app, bot = bot_app
    sem = await _create(levels=[])
    await _register(app, bot, sem["id"], complete=False)

    # تازه رها کرده (updated_at همین حالا) → هنوز یادآوری نه
    report = await reminders.run_due_reminders(app)
    assert report["nudge"] == 0

    # ۱۳ ساعت می‌گذرد → هنوز یک روز کامل نشده
    _age_registration(sem["id"], hours=13)
    report = await reminders.run_due_reminders(app)
    assert report["nudge"] == 0

    # یک روز کامل می‌گذرد → یادآوری روزانه
    _age_registration(sem["id"], hours=25)
    report = await reminders.run_due_reminders(app)
    assert report["nudge"] == 1
    msg = _reminder_texts(bot)[-1]
    assert content.REMINDER_NUDGE_TEXT.format(seminar="سمینار آمادگی تیزهوشان") == msg
    resume_cbs = callbacks(last_send(bot)["reply_markup"])
    assert resume_cbs == [f"sem:reg:{sem['id']}"]

    # اجرای دوباره بلافاصله → تکراری نیست (فاصله‌ی روزانه)
    report = await reminders.run_due_reminders(app)
    assert report["nudge"] == 0

    # دکمه‌ی ادامه: ثبت‌نام از همان مرحله باز می‌شود
    await tap(app, bot, f"sem:reg:{sem['id']}", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_GRADE_TEXT


async def test_reminder_nudge_stops_after_seminar_start(bot_app):
    """بعد از شروع سمینار، ناتمام‌ها دیگر یادآوری نمی‌شوند (ضد اسپم)."""
    app, bot = bot_app
    starts = datetime.now() + timedelta(hours=6)
    sem = await _create(levels=[], starts_at=starts.isoformat(timespec="seconds"))
    await _register(app, bot, sem["id"], complete=False)
    _age_registration(sem["id"], hours=25)

    # قبل از شروع → یادآوری می‌آید
    report = await reminders.run_due_reminders(app)
    assert report["nudge"] == 1

    # سمینار شروع شده → دیگر نه
    seminars.update_seminar(
        sem["id"], starts_at=(datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    )
    _age_registration(sem["id"], hours=30)
    report = await reminders.run_due_reminders(app)
    assert report["nudge"] == 0


async def test_reminder_nudge_cap_without_starts_at(bot_app):
    """سمینار بدون زمان شروع: حداکثر ۸ یادآوری ناتمامی (نه تا ابد)."""
    app, bot = bot_app
    sem = await _create(levels=[])
    await _register(app, bot, sem["id"], complete=False)
    # ۸ بار قبلاً ارسال شده
    for _ in range(8):
        reminders._log_sent(NON_ADMIN.id, sem["id"], reminders.KIND_NUDGE)
    _age_registration(sem["id"], hours=100)
    report = await reminders.run_due_reminders(app)
    assert report["nudge"] == 0


async def test_reminder_pre12_and_pre2(bot_app):
    """کامل‌شده‌ها: ۱۲ ساعت و ۲ ساعت قبل از سمینار — هر کدام فقط یک بار."""
    app, bot = bot_app
    starts = datetime.now() + timedelta(hours=11)
    sem = await _create(
        levels=[],
        starts_at=starts.isoformat(timespec="seconds"),
        link="https://t.me/room_x",
    )
    await _register(app, bot, sem["id"])

    # ۱۱ ساعت مانده → pre12
    report = await reminders.run_due_reminders(app)
    assert report["pre12"] == 1 and report["pre2"] == 0
    assert "۱۲ ساعت تا شروع سمینار" in _reminder_texts(bot)[-1]
    assert "https://t.me/room_x" in _reminder_texts(bot)[-1]

    # اجرای دوباره → تکراری نیست
    report = await reminders.run_due_reminders(app)
    assert report["pre12"] == 0

    # ۹۰ دقیقه مانده → pre2
    seminars.update_seminar(
        sem["id"],
        starts_at=(datetime.now() + timedelta(minutes=90)).isoformat(timespec="seconds"),
    )
    report = await reminders.run_due_reminders(app)
    assert report["pre2"] == 1
    assert "فقط ۲ ساعت" in _reminder_texts(bot)[-1]

    # بعد از شروع → هیچ‌چیز
    seminars.update_seminar(
        sem["id"],
        starts_at=(datetime.now() - timedelta(minutes=10)).isoformat(timespec="seconds"),
    )
    report = await reminders.run_due_reminders(app)
    assert report == {"nudge": 0, "pre12": 0, "pre2": 0, "failed": 0}


async def test_reminder_no_pre12_when_inside_2h_window(bot_app):
    """اگر فقط ۲ ساعت مانده، فقط pre2 می‌آید (pre12 نمی‌آید تا اسپم نشود)."""
    app, bot = bot_app
    starts = datetime.now() + timedelta(minutes=90)
    sem = await _create(levels=[], starts_at=starts.isoformat(timespec="seconds"))
    await _register(app, bot, sem["id"])
    report = await reminders.run_due_reminders(app)
    assert report == {"nudge": 0, "pre12": 0, "pre2": 1, "failed": 0}


async def test_reminders_respect_closed_seminar_and_toggle(bot_app):
    """سمینار بسته → بدون یادآور؛ کلید خاموش → بدون یادآور."""
    app, bot = bot_app
    starts = datetime.now() + timedelta(hours=5)
    sem = await _create(levels=[], starts_at=starts.isoformat(timespec="seconds"))
    await _register(app, bot, sem["id"], complete=False)
    _age_registration(sem["id"], hours=25)

    seminars.set_seminar_open(sem["id"], False)
    assert (await reminders.run_due_reminders(app))["nudge"] == 0
    seminars.set_seminar_open(sem["id"], True)

    # خاموش کردن از پنل
    await tap(app, bot, "adm:rem")
    assert "خاموش" in last_edit(bot)["text"]
    assert reminders.enabled() is False
    assert (await reminders.run_due_reminders(app))["nudge"] == 0

    # روشن کردن
    await tap(app, bot, "adm:rem")
    assert reminders.enabled() is True
    assert (await reminders.run_due_reminders(app))["nudge"] == 1


# ---------------------------------------------------------------------------
# ابزار کمکی تست
# ---------------------------------------------------------------------------


def _age_registration(seminar_id: int, hours: float) -> None:
    """جابه‌جایی updated_at ثبت‌نام به گذشته (شبیه‌سازی گذشت زمان)."""
    from bot.services.database import get_db

    past = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    get_db().execute(
        "UPDATE registrations SET updated_at = ? WHERE seminar_id = ?", (past, seminar_id)
    )


async def test_broadcast_paces_and_handles_429(bot_app, monkeypatch):
    """صف انبوه: نرخ ۵ در ثانیه + تلاش دوباره بعد از خطای 429 تلگرام."""
    from telegram.error import RetryAfter

    app, bot = bot_app
    await send_command(app, bot, "/start", user=NON_ADMIN)
    await send_command(app, bot, "/menu", user=USER)

    sleeps: list[float] = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("bot.services.sender.asyncio.sleep", fake_sleep)

    # گیرنده‌ی اول: اول 429، سپس موفق — گیرنده‌ی دوم: مستقیم موفق
    bot.copy_message.side_effect = [RetryAfter(2), None, None]

    await tap(app, bot, "adm:bcast")
    await send_text(app, bot, "سلام همگانی", user=USER)
    await tap(app, bot, "adm:bcast:go")

    assert bot.copy_message.await_count == 3  # یک تلاش دوباره برای 429
    assert 3.0 in sleeps  # صبرِ 429 (retry_after + 1)
    assert 0.2 in sleeps  # فاصله‌ی صف — ۵ پیام در ثانیه
    assert "موفق: ۲" in last_send(bot)["text"]


def test_legacy_users_table_migrated(tmp_path):
    """دیتابیس قدیمی (users بدون started_at) با ALTER TABLE خودکار مهاجرت می‌کند."""
    import sqlite3

    from bot.services import database, users

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO users (user_id, name) VALUES (555, 'کاربر قدیمی')")
    conn.commit()
    conn.close()

    database.init_db(db_path)  # مهاجرت باید ستون‌های جاافتاده را اضافه کند
    users.ensure_user(555, first_name="جدید")  # قبلاً همین‌جا خطا می‌داد
    assert users.count_users() == 1

    # دیتای قدیمی از بین نرفته
    row = database.get_db().execute("SELECT name FROM users WHERE user_id = 555").fetchone()
    assert row["name"] == "کاربر قدیمی"
    database.close_db()


def test_legacy_db_without_registration_id(tmp_path):
    """دیتابیس قدیمی: registrations بدون ستون id → مهاجرت + آمار لیست کار می‌کند."""
    import sqlite3

    from bot.services import database

    db_path = tmp_path / "legacy2.db"
    conn = sqlite3.connect(db_path)
    # جدول قدیمی بدون id و بدون ستون‌های جدید
    conn.execute(
        "CREATE TABLE registrations ("
        "user_id INTEGER NOT NULL, seminar_id INTEGER NOT NULL, "
        "name TEXT, is_complete INTEGER, created_at TEXT, updated_at TEXT, "
        "UNIQUE (user_id, seminar_id))"
    )
    conn.execute(
        "INSERT INTO registrations VALUES (555, 1, 'کاربر قدیمی', 1, "
        "'2026-10-01 10:00:00', '2026-10-01 10:00:00')"
    )
    conn.commit()
    conn.close()

    database.init_db(db_path)  # مهاجرت خودکار
    seminars.create_seminar(title="سمینار قدیمی")  # id = 1

    # آمار per-seminar (قبلاً همین‌جا: no such column: r.id)
    stats = seminars.list_with_counts()
    assert stats[0]["reg_total"] == 1
    assert stats[0]["reg_done"] == 1

    # خروجی لیست ثبت‌نام هم (ORDER BY rowid) بدون خطا
    regs = seminars.list_registrations(1)
    assert regs[0]["name"] == "کاربر قدیمی"
    database.close_db()


def test_legacy_seminars_without_updated_at(tmp_path):
    """دیتابیس خیلی قدیمی: seminars بدون updated_at → مهاجرت + ساخت سمینار کار می‌کند."""
    import sqlite3

    from bot.services import database

    db_path = tmp_path / "legacy3.db"
    conn = sqlite3.connect(db_path)
    # جدول قدیمی فقط ستون‌های اولیه را دارد (بدون created_at/updated_at/...)
    conn.execute(
        "CREATE TABLE seminars ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
        "description TEXT, date_text TEXT, link TEXT, levels TEXT)"
    )
    conn.execute(
        "INSERT INTO seminars (title, description, date_text, link, levels) "
        "VALUES ('سمینار قدیمی', 'توضیح', 'جمعه', 'https://t.me/x', '')"
    )
    conn.commit()
    conn.close()

    database.init_db(db_path)  # مهاجرت خودکار همه‌ی ستون‌های جاافتاده

    # ساخت سمینار جدید (قبلاً همین‌جا: no such column: updated_at)
    sem = seminars.create_seminar(title="سمینار جدید", message_template="پیام {name}")
    assert sem["id"] == 2
    assert sem["message_template"] == "پیام {name}"

    # دیتای قدیمی سالم است
    old = seminars.get_seminar(1)
    assert old["title"] == "سمینار قدیمی"
    assert old["is_open"] == 1
    database.close_db()


async def test_legacy_step_resumes_correctly(bot_app):
    """ثبت‌نام ناتمامِ نسخه‌ی قدیمی (level/confirm) به مراحل جدید نگاشت می‌شود."""
    app, bot = bot_app
    sem = seminars.create_seminar(title="سمینار")
    seminars.ensure_registration(NON_ADMIN.id, sem["id"])
    seminars.save_registration(
        NON_ADMIN.id,
        sem["id"],
        name="کاربر قدیمی",
        next_step="level",  # مرحله‌ی قدیمی
    )
    await tap(app, bot, f"sem:reg:{sem['id']}", user=NON_ADMIN)
    assert last_send(bot)["text"] == content.WIZ_GRADE_TEXT  # → معادل جدید: پایه
