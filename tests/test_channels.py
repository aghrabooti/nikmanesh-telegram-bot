"""تست بخش کانال‌ها (/channels) — رمز ورود، دسترسی فقط-آماری، اطلاع به ادمین."""

from __future__ import annotations

import sqlite3

from bot.config import content
from bot.constants import REF_START_PREFIX
from bot.services import referrals, seminars, users
from bot.services.database import close_db, init_db
from tests.helpers import (
    NON_ADMIN,
    USER,
    callbacks,
    last_answer,
    last_edit,
    last_send,
    send_command,
    send_text,
    share_contact,
    tap,
)


def _create(**kwargs):
    defaults = dict(title="وبینار تست", link="https://t.me/room", levels=[])
    defaults.update(kwargs)
    return seminars.create_seminar(**defaults)


async def _register(app, bot, seminar_id, *, user=NON_ADMIN, name="سارا احمدی"):
    await tap(app, bot, f"sem:reg:{seminar_id}", user=user)
    await send_text(app, bot, name, user=user)
    await send_text(app, bot, "کنکوری ۴۰۷", user=user)
    await send_text(app, bot, "ریاضی", user=user)
    await send_text(app, bot, "شیراز", user=user)
    await share_contact(app, bot, user=user, phone="09121234567")
    await send_text(app, bot, "۰۹۱۲۳۴۵۶۷۸۹", user=user)


# ── ساخت لینک = رمز خودکار ───────────────────────────────────────────────


def test_link_gets_auto_phrase(bot_app):
    app, bot = bot_app
    a = referrals.create_link("کانال الف")
    b = referrals.create_link("کانال ب")
    assert a["phrase"] and len(a["phrase"]) == 8
    assert a["phrase"] != b["phrase"]
    assert referrals.find_link_by_phrase(a["phrase"])["link_id"] == a["link_id"]
    assert (
        referrals.find_link_by_phrase("  " + a["phrase"].upper() + " ")["link_id"] == a["link_id"]
    )
    assert referrals.find_link_by_phrase("wrong123") is None


# ── /channels و ورود با رمز ───────────────────────────────────────────────


async def test_channels_flow_login_and_aggregate_stats(bot_app):
    """/channels → پرامپت رمز → ورود → آمار تجمیعی (بدون هیچ داده‌ی شخصی)."""
    app, bot = bot_app
    s = _create()
    link = referrals.create_link("کانال همکار")
    # یک ثبت‌نام کامل از این لینک
    await send_command(app, bot, f"/start {REF_START_PREFIX}{link['code']}", user=NON_ADMIN)
    await _register(app, bot, s["id"], user=NON_ADMIN)

    # کاربر سوم (ادمین کانال) — user id 888
    from telegram import User as TgUser

    owner = TgUser(id=888, first_name="مدیر کانال", is_bot=False)
    await send_command(app, bot, "/channels", user=owner)
    assert last_send(bot)["text"] == content.CH_LOGIN_PROMPT

    # رمز غلط → خطا و ماندن در حالت
    await send_text(app, bot, "wrong-pass", user=owner)
    assert last_send(bot)["text"] == content.CH_LOGIN_WRONG

    # رمز درست → دسترسی + آمار
    await send_text(app, bot, link["phrase"], user=owner)
    assert referrals.is_channel_admin(888, link["link_id"])
    texts_sent = [c.kwargs["text"] for c in bot.send_message.await_args_list[-2:]]
    assert content.CH_GRANTED.format(label="کانال همکار") in texts_sent[0]
    stats = texts_sent[1]
    assert "کانال همکار" in stats and "ورودی (استارت): <b>۱</b>" in stats
    assert "ثبت‌نام کامل: <b>۱</b>" in stats and "شماره جایگزین" in stats
    # هیچ داده‌ی شخصی در صفحه نیست
    assert "سارا احمدی" not in stats and "09123456789" not in stats and "+989" not in stats

    # ادمین ربات مطلع شد
    notified = [
        c.kwargs for c in bot.send_message.await_args_list if c.kwargs.get("chat_id") == USER.id
    ]
    assert any("مدیر کانال" in k["text"] and "کانال همکار" in k["text"] for k in notified)


async def test_channels_list_after_login_and_no_personal_data(bot_app):
    """بعد از ورود، /channels لیست کانال‌ها را می‌دهد و صفحه فقط آمار است."""
    app, bot = bot_app
    s = _create()
    link = referrals.create_link("کانال آماری")
    referrals.add_channel_admin(NON_ADMIN.id, link["link_id"])
    await _register(
        app, bot, s["id"], user=USER
    )  # ثبت‌نام از user=777 (ادمین ربات؟ نه — USER=777 ادمین است!)

    await send_command(app, bot, "/channels", user=NON_ADMIN)
    sent = last_send(bot)
    assert content.CH_TITLE in sent["text"]
    assert callbacks(sent["reply_markup"]) == [
        f"ch:l:{link['link_id']}",
        "ch:add",
        "main",
    ]

    await tap(app, bot, f"ch:l:{link['link_id']}", user=NON_ADMIN)
    page = last_edit(bot)["text"]
    assert "کانال آماری" in page
    assert "سارا احمدی" not in page  # ثبت‌نام به لینک نسبت نداشت و نامش نمی‌آید


async def test_channels_link_page_access_denied_for_strangers(bot_app):
    app, bot = bot_app
    link = referrals.create_link("کانال خصوصی")
    referrals.add_channel_admin(USER.id, link["link_id"])  # فقط USER دسترسی دارد
    await tap(app, bot, f"ch:l:{link['link_id']}", user=NON_ADMIN)
    assert last_answer(bot)["text"] == content.CH_ACCESS_DENIED


async def test_channels_inactive_phrase_rejected(bot_app):
    app, bot = bot_app
    link = referrals.create_link("کانال تعطیل")
    referrals.set_active(link["link_id"], False)
    await send_command(app, bot, "/channels", user=NON_ADMIN)
    await send_text(app, bot, link["phrase"], user=NON_ADMIN)
    assert last_send(bot)["text"] == content.CH_LOGIN_INACTIVE
    assert not referrals.is_channel_admin(NON_ADMIN.id, link["link_id"])


async def test_channels_cancel_button(bot_app):
    app, bot = bot_app
    await send_command(app, bot, "/channels", user=NON_ADMIN)
    await send_text(app, bot, content.CH_LOGIN_CANCEL_LBL, user=NON_ADMIN)
    assert content.CH_NO_ACCESS_YET in last_send(bot)["text"]
    # state پاک شد — پیام بعدی معمولی به ویزارد/منو می‌رود نه رمز


async def test_channels_bot_admin_gets_redirect(bot_app):
    app, bot = bot_app
    await send_command(app, bot, "/channels", user=USER)  # USER=777 = ادمین
    assert "/admin" in last_send(bot)["text"]


# ── افزودن کانالهای بعدی توسط ادمین کانال ───────────────────────────────


async def test_channel_admin_can_add_second_channel_with_button(bot_app):
    """دمین کانال با دکمهی «➕ افزودن کانال» کانال دوم را هم اضافه میکند."""
    app, bot = bot_app
    first = referrals.create_link("کانال اول")
    second = referrals.create_link("کانال دوم")
    referrals.add_channel_admin(NON_ADMIN.id, first["link_id"])

    await send_command(app, bot, "/channels", user=NON_ADMIN)
    assert "ch:add" in callbacks(last_send(bot)["reply_markup"])

    await tap(app, bot, "ch:add", user=NON_ADMIN)
    prompt = last_edit(bot)
    assert prompt["text"] == content.CH_ADD_PROMPT
    assert callbacks(prompt["reply_markup"]) == ["ch:home"]

    await send_text(app, bot, second["phrase"], user=NON_ADMIN)
    assert referrals.is_channel_admin(NON_ADMIN.id, second["link_id"])
    assert len(referrals.user_links(NON_ADMIN.id)) == 2

    sent_texts = [c.kwargs.get("text", "") for c in bot.send_message.await_args_list]
    assert content.CH_ADD_GRANTED.format(label="کانال دوم") in sent_texts
    assert any("کانال دوم" in t and "تعداد ورودی" in t for t in sent_texts)
    # ادمین ربات هم از اضافه شدن کانال جدید مطلع شد
    notified = [
        c.kwargs for c in bot.send_message.await_args_list if c.kwargs.get("chat_id") == USER.id
    ]
    assert any("کانال دوم" in k["text"] for k in notified)


async def test_channel_admin_can_add_second_channel_with_command_arg(bot_app):
    """/channels <رمز> حتی وقتی کانال قبلی وجود دارد، کانال جدید اضافه میکند."""
    app, bot = bot_app
    first = referrals.create_link("کانال الف")
    second = referrals.create_link("کانال ب")
    referrals.add_channel_admin(NON_ADMIN.id, first["link_id"])

    await send_command(app, bot, f"/channels {second['phrase']}", user=NON_ADMIN)
    assert referrals.is_channel_admin(NON_ADMIN.id, second["link_id"])
    assert len(referrals.user_links(NON_ADMIN.id)) == 2
    sent_texts = [c.kwargs.get("text", "") for c in bot.send_message.await_args_list]
    assert content.CH_ADD_GRANTED.format(label="کانال ب") in sent_texts


async def test_channels_cancel_with_existing_links_returns_list(bot_app):
    """انصراف موقع افزودن کانال، کاربر را به لیست کانالهای قبلی برمیگرداند."""
    app, bot = bot_app
    link = referrals.create_link("کانال قبلی")
    referrals.add_channel_admin(NON_ADMIN.id, link["link_id"])

    await tap(app, bot, "ch:add", user=NON_ADMIN)
    await send_text(app, bot, content.CH_LOGIN_CANCEL_LBL, user=NON_ADMIN)
    assert content.CH_TITLE in last_send(bot)["text"]


async def test_channels_home_clears_add_state(bot_app):
    """دکمهی انصراف اینلاین از پرامپت افزودن، لیست را نشان میدهد."""
    app, bot = bot_app
    link = referrals.create_link("کانال تست")
    referrals.add_channel_admin(NON_ADMIN.id, link["link_id"])

    await tap(app, bot, "ch:add", user=NON_ADMIN)
    await tap(app, bot, "ch:home", user=NON_ADMIN)
    page = last_edit(bot)
    assert content.CH_TITLE in page["text"]
    assert "ch:add" in callbacks(page["reply_markup"])


# ── پنل ادمین ربات: رمز، بیرون کردن، رمز جدید ────────────────────────────


async def test_admin_link_detail_shows_phrase_and_access(bot_app):
    app, bot = bot_app
    link = referrals.create_link("کانال الف")
    users.ensure_user(888, first_name="مدیر کانال", username="channel_mgr")
    referrals.add_channel_admin(888, link["link_id"])

    await tap(app, bot, f"adm:ads:v:{link['link_id']}", user=USER)
    detail = last_edit(bot)
    assert f"🔑 رمز ورود کانال‌ها: <code>{link['phrase']}</code>" in detail["text"]
    assert "مدیر کانال (@channel_mgr | <code>888</code>)" in detail["text"]
    cbs = callbacks(detail["reply_markup"])
    assert f"adm:ads:pw:{link['link_id']}" in cbs  # رمز جدید
    assert f"adm:ads:k:{link['link_id']}:888" in cbs  # بیرون کردن


async def test_admin_reset_phrase_and_kick(bot_app):
    app, bot = bot_app
    link = referrals.create_link("کانال ب")
    referrals.add_channel_admin(NON_ADMIN.id, link["link_id"])
    old_phrase = link["phrase"]

    # رمز جدید → رمز قبلی بی‌اعتبار
    await tap(app, bot, f"adm:ads:pw:{link['link_id']}", user=USER)
    assert last_answer(bot)["text"] == content.ADS_RESET_DONE
    fresh = referrals.get_link(link["link_id"])
    assert fresh["phrase"] != old_phrase
    assert referrals.find_link_by_phrase(old_phrase) is None
    assert referrals.find_link_by_phrase(fresh["phrase"])["link_id"] == link["link_id"]

    # بیرون کردن → دسترسی حذف
    await tap(app, bot, f"adm:ads:k:{link['link_id']}:{NON_ADMIN.id}", user=USER)
    assert last_answer(bot)["text"] == content.ADS_KICK_DONE
    assert not referrals.is_channel_admin(NON_ADMIN.id, link["link_id"])


async def test_create_link_message_includes_phrase(bot_app):
    app, bot = bot_app
    bot.username = "nikmanesh_bot"
    await tap(app, bot, "adm:ads", user=USER)
    await tap(app, bot, "adm:ads:new", user=USER)
    await send_text(app, bot, "کانال جدید", user=USER)
    created = bot.send_message.await_args_list[-2].kwargs["text"]
    assert "رمز ورود بخش کانال‌ها" in created
    link = referrals.links()[0]
    assert f"<code>{link['phrase']}</code>" in created


# ── مهاجرت دیتابیس قدیمی ────────────────────────────────────────────────


def test_legacy_links_get_phrases(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE referral_links ("
        "link_id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE,"
        " label TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1,"
        " created_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO referral_links (code, label, is_active, created_at)"
        " VALUES ('abc123', 'قدیمی', 1, '2026-01-01')"
    )
    conn.commit()
    conn.close()

    init_db(db_path)
    link = referrals.links()[0]
    assert link["phrase"]  # بک‌فیل شده
    close_db()


def test_bot_command_menu_has_no_admin_commands():
    """منوی دستورات تلگرام فقط فرمان‌های کاربر عادی دارد — /admin و /channels نیستند."""
    from bot.main import _USER_COMMANDS

    names = [c.command for c in _USER_COMMANDS]
    assert names == ["start", "menu", "id"]
    assert "admin" not in names and "channels" not in names
