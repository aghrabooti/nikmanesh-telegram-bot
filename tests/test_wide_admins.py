"""ادمین گسترده: دعوت یک‌بارمصرف، مالکیت رفرال و جداسازی آمار."""

from __future__ import annotations

import re
import sqlite3

from telegram import User as TgUser

from bot.config import content
from bot.services import referrals, seminars, wide_admins
from bot.services.database import close_db, get_db, init_db
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
    texts,
)


async def _create_wide_admin(app, bot, target_id=888):
    """دعوت را از پنل ادمین اصلی بسازد و کد خام را برگرداند."""
    await send_command(app, bot, "/admin", user=USER)
    await tap(app, bot, "adm:wide", user=USER)
    await tap(app, bot, "adm:wide:add", user=USER)
    await send_text(app, bot, str(target_id), user=USER)
    invite = next(text for text in texts(bot) if "رمز یک‌بارمصرف" in text)
    token = re.search(r"<code>([a-z2-9]{16})</code>", invite).group(1)
    assert "adm:wide:add" in callbacks(last_edit(bot)["reply_markup"])
    return token


async def _register_from_link(app, bot, link, *, user=NON_ADMIN):
    seminar = seminars.create_seminar(
        title="سمینار تست", link="https://t.me/room", levels=["کنکوری ۴۰۶"]
    )
    await send_command(app, bot, f"/start ref_{link['code']}", user=user)
    await tap(app, bot, f"sem:reg:{seminar['id']}", user=user)
    await send_text(app, bot, "سارا احمدی", user=user)
    await send_text(app, bot, "کنکوری ۴۰۶", user=user)
    await send_text(app, bot, "تجربی", user=user)
    await send_text(app, bot, "تهران", user=user)
    await share_contact(app, bot, user=user, phone="09121234567")
    await send_text(app, bot, "09123456789", user=user)
    return seminar


async def test_wide_admin_invite_is_one_time_and_bound_to_telegram_id(bot_app):
    app, bot = bot_app
    token = await _create_wide_admin(app, bot, target_id=888)

    stored = (
        get_db()
        .execute("SELECT token_hash, target_user_id, used_at FROM wide_admin_invites")
        .fetchone()
    )
    assert stored["target_user_id"] == 888
    assert token not in stored["token_hash"]
    assert stored["used_at"] == ""

    wrong_user = TgUser(id=889, first_name="Wrong", is_bot=False)
    await send_command(app, bot, f"/wideadmin {token}", user=wrong_user)
    assert last_send(bot)["text"] == content.WIDE_ADMIN_INVITE_INVALID
    assert not wide_admins.is_wide_admin(889)

    invited = TgUser(id=888, first_name="Wide", is_bot=False)
    await send_command(app, bot, f"/wideadmin {token}", user=invited)
    assert wide_admins.is_wide_admin(888)
    assert content.WIDE_ADMIN_LINKS_TITLE in last_send(bot)["text"]
    owner_update = next(
        call.kwargs
        for call in bot.send_message.await_args_list
        if "ادمین گسترده با شناسهٔ <code>888</code> فعال شد" in call.kwargs["text"]
    )
    assert "adm:wide:revoke:888" in callbacks(owner_update["reply_markup"])
    assert wide_admins.redeem_invite(888, token) is False

    assert wide_admins.revoke_wide_admin(888) is True
    assert wide_admins.is_wide_admin(888) is False


async def test_primary_admin_rejects_nonpositive_and_out_of_range_invite_ids(bot_app):
    app, bot = bot_app
    await send_command(app, bot, "/admin", user=USER)
    await tap(app, bot, "adm:wide", user=USER)
    await tap(app, bot, "adm:wide:add", user=USER)

    for invalid_id in ("0", "9223372036854775808"):
        await send_text(app, bot, invalid_id, user=USER)
        assert last_send(bot)["text"] == content.WIDE_ADMIN_ID_INVALID
    assert get_db().execute("SELECT COUNT(*) FROM wide_admin_invites").fetchone()[0] == 0


async def test_wide_admin_gets_only_own_referrals_and_no_registrant_data(bot_app):
    app, bot = bot_app
    token = await _create_wide_admin(app, bot, target_id=888)
    wide_user = TgUser(id=888, first_name="Wide", is_bot=False)
    await send_command(app, bot, f"/wideadmin {token}", user=wide_user)

    await tap(app, bot, "wa:create", user=wide_user)
    assert "wa:create" not in callbacks(last_edit(bot)["reply_markup"])
    assert callbacks(last_edit(bot)["reply_markup"]) == ["wa:home"]
    # دکمهٔ قدیمیِ «ساخت» هم در زمان انتظار برچسب، درخواست دوم نمی‌سازد.
    await tap(app, bot, "wa:create", user=wide_user)
    assert last_answer(bot)["text"] == content.WIDE_LINK_LABEL_PENDING
    assert referrals.owned_links(888) == []

    await send_text(app, bot, "کمپین مخصوص", user=wide_user)
    owned = referrals.owned_links(888)[0]
    assert f"wa:view:{owned['link_id']}" in callbacks(last_edit(bot)["reply_markup"])
    assert "wa:create" in callbacks(last_edit(bot)["reply_markup"])
    other = referrals.create_link("رفرال ادمین اصلی")
    another_owner_link = referrals.create_link("رفرال گسترده دیگر", owner_user_id=999)

    assert owned["owner_user_id"] == 888
    assert not referrals.owns_link(888, other["link_id"])
    assert not referrals.owns_link(888, another_owner_link["link_id"])

    await _register_from_link(app, bot, owned)

    # اگر این حساب از قبل مدیر کانال لینک دیگری بوده باشد، نقش گسترده هم‌زمان
    # از مسیر /channels به آن آمار دسترسی نمی‌دهد.
    referrals.add_channel_admin(wide_user.id, other["link_id"])
    await tap(app, bot, f"ch:l:{other['link_id']}", user=wide_user)
    assert last_answer(bot)["text"] == content.CH_ACCESS_DENIED

    await send_command(app, bot, "/channels", user=wide_user)
    assert callbacks(last_send(bot)["reply_markup"]) == [
        f"wa:view:{owned['link_id']}",
        "wa:create",
        "main",
    ]

    await tap(app, bot, f"wa:view:{owned['link_id']}", user=wide_user)
    detail = last_edit(bot)["text"]
    assert "ورودی (استارت): <b>۱</b>" in detail
    assert "ثبت‌نام کامل: <b>۱</b>" in detail
    assert "سارا احمدی" not in detail
    assert "09123456789" not in detail and "09121234567" not in detail
    assert not any(
        callback.startswith(("adm:ads:rg", "adm:ads:rgc", "adm:ads:rgx"))
        for callback in callbacks(last_edit(bot)["reply_markup"])
    )

    # فرستادن مستقیم callback لینک مالک دیگر هم از سمت سرور رد می‌شود.
    await tap(app, bot, f"wa:view:{another_owner_link['link_id']}", user=wide_user)
    assert last_answer(bot)["text"] == content.WIDE_LINK_ACCESS_DENIED

    # این نقش از /admin کامل و گزارش‌های شخصی ثبت‌نام‌ها محروم است.
    await send_command(app, bot, "/admin", user=wide_user)
    assert last_send(bot)["text"] == content.ADMIN_ONLY_TEXT

    # callbackهای حساس را هم مستقیم فرستاده‌ایم؛ محدودیت باید در handler باشد.
    protected_callbacks = [
        "adm:sems",
        "adm:sem:1",
        "adm:regs:1",
        "adm:regs:csv:1",
        "adm:regs:xlsx:1",
        "adm:users:csv",
        "adm:users:xlsx",
        "adm:bcast",
        "adm:ads:msg",
        "adm:ads:csv",
        "adm:ads:xlsx",
        f"adm:ads:v:{owned['link_id']}",
        f"adm:ads:t:{owned['link_id']}",
        f"adm:ads:owner:{owned['link_id']}",
        f"adm:ads:rg:{owned['link_id']}",
        f"adm:ads:rgc:{owned['link_id']}",
        f"adm:ads:rgx:{owned['link_id']}",
        f"adm:ads:del:{owned['link_id']}",
        f"adm:ads:del2:{owned['link_id']}",
    ]
    for callback in protected_callbacks:
        await tap(app, bot, callback, user=wide_user)
        assert last_answer(bot)["text"] == content.ADMIN_ONLY_TEXT
    assert referrals.get_link(owned["link_id"]) is not None


async def test_primary_admin_can_assign_existing_link_and_wide_admin_can_manage_it(bot_app):
    app, bot = bot_app
    token = await _create_wide_admin(app, bot, target_id=888)
    wide_user = TgUser(id=888, first_name="Wide", is_bot=False)
    await send_command(app, bot, f"/wideadmin {token}", user=wide_user)
    old_link = referrals.create_link("لینک قدیمی")

    # رفرال قدیمی تا زمان واگذاری فقط برای ادمین اصلی است.
    assert old_link["owner_user_id"] is None
    assert referrals.owned_links(888) == []

    await send_command(app, bot, "/admin", user=USER)
    await tap(app, bot, "adm:ads", user=USER)
    await tap(app, bot, f"adm:ads:v:{old_link['link_id']}", user=USER)
    await tap(app, bot, f"adm:ads:owner:{old_link['link_id']}", user=USER)
    assign_button = f"adm:ads:owner-set:{old_link['link_id']}:888"
    assert assign_button in callbacks(last_edit(bot)["reply_markup"])
    await tap(app, bot, assign_button, user=USER)

    assert referrals.owns_link(888, old_link["link_id"])
    assert referrals.get_link(old_link["link_id"])["owner_user_id"] == 888
    assert old_link["link_id"] in [item["link_id"] for item in referrals.owned_links(888)]

    # ادمین گسترده می‌تواند لینکِ واگذارشده را غیرفعال کند.
    await tap(app, bot, f"wa:view:{old_link['link_id']}", user=wide_user)
    await tap(app, bot, f"wa:toggle:{old_link['link_id']}", user=wide_user)
    assert referrals.get_link(old_link["link_id"])["is_active"] == 0


async def test_permanent_link_deletion_is_primary_admin_only_and_preserves_first_touch(
    bot_app,
):
    app, bot = bot_app
    token = await _create_wide_admin(app, bot, target_id=888)
    wide_user = TgUser(id=888, first_name="Wide", is_bot=False)
    await send_command(app, bot, f"/wideadmin {token}", user=wide_user)

    link = referrals.create_link("برای حذف")
    referrals.add_channel_admin(666, link["link_id"])
    referrals.attribute_start(123456, link["code"])
    seminar = seminars.create_seminar(title="سمینار حفظ سوابق")
    registration = seminars.ensure_registration(123456, seminar["id"])
    assert registration["link_id"] == link["link_id"]

    # حتی callback حذف مستقیم برای ادمین گسترده مجاز نیست.
    await tap(app, bot, f"adm:ads:del2:{link['link_id']}", user=wide_user)
    assert last_answer(bot)["text"] == content.ADMIN_ONLY_TEXT
    assert referrals.get_link(link["link_id"]) is not None

    await tap(app, bot, f"adm:ads:del:{link['link_id']}", user=USER)
    assert f"adm:ads:del2:{link['link_id']}" in callbacks(last_edit(bot)["reply_markup"])
    await tap(app, bot, f"adm:ads:del2:{link['link_id']}", user=USER)

    assert referrals.get_link(link["link_id"]) is None
    assert not referrals.is_channel_admin(666, link["link_id"])
    assert referrals.attributed_link_id(123456) == link["link_id"]
    preserved = seminars.get_registration(123456, seminar["id"])
    assert preserved["link_id"] == link["link_id"]


def test_old_referral_database_migrates_existing_links_to_primary_owner(tmp_path):
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """CREATE TABLE referral_links (
               link_id INTEGER PRIMARY KEY,
               code TEXT NOT NULL,
               label TEXT NOT NULL,
               is_active INTEGER NOT NULL DEFAULT 1,
               phrase TEXT NOT NULL DEFAULT '',
               created_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        "INSERT INTO referral_links (link_id, code, label, phrase, created_at) "
        "VALUES (41, 'oldref', 'لینک قدیمی', 'safe1234', '2026-10-01')"
    )
    connection.commit()
    connection.close()

    init_db(database_path)
    try:
        row = (
            get_db()
            .execute("SELECT owner_user_id FROM referral_links WHERE link_id = 41")
            .fetchone()
        )
        assert row["owner_user_id"] is None
        assert get_db().execute("SELECT COUNT(*) FROM wide_admins").fetchone()[0] == 0
        assert get_db().execute("SELECT COUNT(*) FROM wide_admin_invites").fetchone()[0] == 0
    finally:
        close_db()
