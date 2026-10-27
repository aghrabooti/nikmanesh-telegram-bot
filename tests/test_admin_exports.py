"""Global Excel exports for contact leads and registration starts."""

from __future__ import annotations

import io

from openpyxl import load_workbook

from bot.services import seminars, users
from bot.services.database import get_db
from tests.helpers import callbacks, last_document, last_edit, send_text, tap


def _seed_registration(
    *,
    user_id: int,
    seminar_id: int,
    created_at: str,
    name: str,
    phone: str = "",
    current_step: str = seminars.STEP_NAME,
    complete: bool = False,
) -> None:
    users.ensure_user(user_id, first_name=f"کاربر {user_id}", username=f"user{user_id}")
    seminars.ensure_registration(user_id, seminar_id)
    db = get_db()
    db.execute(
        """UPDATE registrations
           SET name = ?, phone = ?, current_step = ?, is_complete = ?,
               created_at = ?, updated_at = ?
           WHERE user_id = ? AND seminar_id = ?""",
        (
            name,
            phone,
            current_step,
            int(complete),
            created_at,
            created_at,
            user_id,
            seminar_id,
        ),
    )
    db.commit()


def _seed_sample_data() -> None:
    first = seminars.create_seminar(title="سمینار اول")
    second = seminars.create_seminar(title="سمینار دوم")
    # یک فرد در دو سمینار شماره داده؛ خروجی لید باید برای او یک ردیف داشته باشد.
    _seed_registration(
        user_id=1001,
        seminar_id=first["id"],
        created_at="2026-10-20 10:00:30",
        name="آوا",
        phone="+989121111111",
        current_step=seminars.STEP_ALTERNATE_PHONE,
    )
    _seed_registration(
        user_id=1001,
        seminar_id=second["id"],
        created_at="2026-10-20 10:00:45",
        name="آوا محمدی",
        phone="+989121111111",
        current_step=seminars.STEP_ALTERNATE_PHONE,
    )
    # شروع فرم، بدون شماره؛ در خروجی شروع‌ها باشد ولی لید تماس نباشد.
    _seed_registration(
        user_id=1002,
        seminar_id=first["id"],
        created_at="2026-10-20 10:00:15",
        name="",
        current_step=seminars.STEP_PHONE,
    )
    # شماره‌دار ولی خارج از دقیقهٔ انتخاب‌شده.
    _seed_registration(
        user_id=1003,
        seminar_id=first["id"],
        created_at="2026-10-20 10:01:00",
        name="بهرام",
        phone="+989123333333",
        current_step=seminars.STEP_ALTERNATE_PHONE,
    )


async def test_admin_overview_has_two_new_excel_exports(bot_app):
    app, bot = bot_app
    await tap(app, bot, "adm:export:leads")
    assert "تاریخ و ساعت" in last_edit(bot)["text"]
    assert callbacks(last_edit(bot)["reply_markup"]) == [
        "adm:export:all:leads",
        "adm:export:cancel",
    ]

    await tap(app, bot, "adm:export:cancel")
    main_callbacks = callbacks(last_edit(bot)["reply_markup"])
    assert "adm:export:leads" in main_callbacks
    assert "adm:export:starts" in main_callbacks


async def test_contact_leads_export_filters_by_datetime_and_has_one_row_per_user(bot_app):
    app, bot = bot_app
    _seed_sample_data()

    await tap(app, bot, "adm:export:leads")
    await send_text(app, bot, "2026-10-20 10:00 تا 2026-10-20 10:00")

    document = last_document(bot)
    assert document["filename"] == "contact-leads.xlsx"
    workbook = load_workbook(io.BytesIO(document["document"].getvalue()), read_only=True)
    rows = list(workbook.active.values)
    assert rows[0][2:5] == ("نام", "شماره تماس", "شماره جایگزین")
    # دو ثبت‌نام همان شخص یکی شده‌اند؛ رکورد جدیدتر و فرد بدون شماره بیرون است.
    assert len(rows) == 2
    assert rows[1][1] == 1001
    assert rows[1][2] == "آوا محمدی"
    assert rows[1][3] == "+989121111111"
    assert rows[1][5] == "سمینار دوم"


async def test_registration_starts_export_includes_partials_and_filters_time(bot_app):
    app, bot = bot_app
    _seed_sample_data()

    await tap(app, bot, "adm:export:starts")
    await send_text(app, bot, "2026-10-20 10:00 تا 2026-10-20 10:00")

    document = last_document(bot)
    assert document["filename"] == "registration-starts.xlsx"
    workbook = load_workbook(io.BytesIO(document["document"].getvalue()), read_only=True)
    rows = list(workbook.active.values)
    # هر ردیف ثبت‌نام جداگانه است؛ شروع‌های نیمه‌کاره و بدون شماره هم می‌آیند.
    assert len(rows) == 4
    assert {row[1] for row in rows[1:]} == {1001, 1002}
    assert any(row[1] == 1002 and row[8] == "—" for row in rows[1:])


async def test_all_registration_starts_callback_sends_full_history(bot_app):
    app, bot = bot_app
    _seed_sample_data()

    await tap(app, bot, "adm:export:starts")
    await tap(app, bot, "adm:export:all:starts")

    document = last_document(bot)
    workbook = load_workbook(io.BytesIO(document["document"].getvalue()), read_only=True)
    rows = list(workbook.active.values)
    assert len(rows) == 5


async def test_wide_admin_cannot_access_new_private_exports(bot_app):
    app, bot = bot_app
    from telegram import User

    wide_admin = User(id=888, first_name="Wide", is_bot=False)
    for callback in (
        "adm:export:leads",
        "adm:export:starts",
        "adm:export:all:leads",
        "adm:export:all:starts",
    ):
        await tap(app, bot, callback, user=wide_admin)
        assert "فقط برای مدیران" in bot.answer_callback_query.await_args.kwargs["text"]
