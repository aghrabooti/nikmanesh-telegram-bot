"""ثابت‌ها: کالبک‌ها و الگوهای هندلر — کوتاه و استاندارد."""

from __future__ import annotations

import re

# ── کاربر ──
CB_MAIN = "main"
CB_SEMINAR_VIEW = "sem:v:{seminar_id}"
CB_SEMINAR_REGISTER = "sem:reg:{seminar_id}"
CB_WIZ_LEVEL = "wz:lv:{seminar_id}:{index}"
CB_WIZ_CONFIRM = "wz:ok:{seminar_id}"
CB_WIZ_CANCEL = "wz:x"

# ── ادمین ──
CB_ADMIN_SEMS = "adm:sems"
CB_ADMIN_SEM_NEW = "adm:sem:new"
CB_ADMIN_SEM_PAGE = "adm:sem:{seminar_id}"
CB_ADMIN_SEM_EDIT = "adm:sem:e:{seminar_id}"
CB_ADMIN_SEM_EDIT_FIELD = "adm:sem:ef:{seminar_id}:{field}"
CB_ADMIN_SEM_OPEN = "adm:sem:open:{seminar_id}"
CB_ADMIN_SEM_DELETE = "adm:sem:del:{seminar_id}"
CB_ADMIN_SEM_DELETE2 = "adm:sem:del2:{seminar_id}"
CB_ADMIN_REGS = "adm:regs:{seminar_id}"

# تبلیغات و رفرال (پورت ربات تیزگام)
CB_ADMIN_ADS = "adm:ads"
CB_ADMIN_ADS_NEW = "adm:ads:new"
CB_ADMIN_ADS_VIEW = "adm:ads:v:{link_id}"
CB_ADMIN_ADS_TOGGLE = "adm:ads:t:{link_id}"
CB_ADMIN_ADS_MSG = "adm:ads:msg"
CB_ADMIN_ADS_REGS = "adm:ads:rg:{link_id}"
CB_ADMIN_ADS_REGS_CSV = "adm:ads:rgc:{link_id}"
CB_ADMIN_ADS_REGS_XLSX = "adm:ads:rgx:{link_id}"
CB_ADMIN_ADS_RESET_PHRASE = "adm:ads:pw:{link_id}"
CB_ADMIN_ADS_KICK = "adm:ads:k:{link_id}:{user_id}"
CB_ADMIN_ADS_ASSIGN = "adm:ads:owner:{link_id}"
CB_ADMIN_ADS_OWNER_SET = "adm:ads:owner-set:{link_id}:{owner_id}"
CB_ADMIN_ADS_DELETE = "adm:ads:del:{link_id}"
CB_ADMIN_ADS_DELETE2 = "adm:ads:del2:{link_id}"
CB_ADMIN_ADS_CSV = "adm:ads:csv"
CB_ADMIN_ADS_XLSX = "adm:ads:xlsx"

# پیشوند payload لینک‌های رفرال در /start (مثل /start ref_ab12c)
REF_START_PREFIX = "ref_"

# state دریافت برچسب لینک جدید
REF_STATE_KEY = "admin_ref_label"

# state انتظار رمز ورود بخش کانال‌ها
CHANNELS_STATE_KEY = "channels_phrase"

# مدیریت ادمین‌های گسترده (فقط ادمین اصلی)
CB_ADMIN_WIDE = "adm:wide"
CB_ADMIN_WIDE_ADD = "adm:wide:add"
CB_ADMIN_WIDE_REVOKE = "adm:wide:revoke:{user_id}"

# پنل رفرال‌های شخصی ادمین گسترده
CB_WIDE_HOME = "wa:home"
CB_WIDE_CREATE = "wa:create"
CB_WIDE_VIEW = "wa:view:{link_id}"
CB_WIDE_TOGGLE = "wa:toggle:{link_id}"
CB_WIDE_RESET_PHRASE = "wa:phrase:{link_id}"
CB_WIDE_KICK = "wa:kick:{link_id}:{user_id}"

# بخش کانال‌ها (دسترسی فقط-آماری ادمین کانال)
CB_CH_LINK = "ch:l:{link_id}"
CB_CH_ADD = "ch:add"
CB_ADMIN_REGS_MSG = "adm:regs:msg:{seminar_id}"
CB_ADMIN_REGS_CSV = "adm:regs:csv:{seminar_id}"
CB_ADMIN_REGS_CSV_COMPLETE = "adm:regs:csv-complete:{seminar_id}"
CB_ADMIN_REGS_XLSX = "adm:regs:xlsx:{seminar_id}"
CB_ADMIN_REGS_XLSX_COMPLETE = "adm:regs:xlsx-complete:{seminar_id}"
CB_ADMIN_USERS_CSV = "adm:users:csv"
CB_ADMIN_USERS_XLSX = "adm:users:xlsx"
CB_ADMIN_EXPORT_LEADS = "adm:export:leads"
CB_ADMIN_EXPORT_STARTS = "adm:export:starts"
CB_ADMIN_EXPORT_ALL = "adm:export:all:{kind}"
CB_ADMIN_EXPORT_CANCEL = "adm:export:cancel"
CB_ADMIN_RANGE = "adm:range:{code}"
CB_ADMIN_BCAST = "adm:bcast"
CB_ADMIN_BCAST_GO = "adm:bcast:go"
CB_ADMIN_BCAST_NO = "adm:bcast:no"
CB_ADMIN_REMINDERS = "adm:rem"
CB_ADMIN_ABOUT = "adm:about"

# ── کلیدهای state ادمین در user_data ──
NEW_STATE_KEY = "admin_new_seminar"
EDIT_STATE_KEY = "admin_edit_field"
RANGE_STATE_KEY = "admin_custom_range"
EXPORT_RANGE_STATE_KEY = "admin_export_range"
REGS_STATE_KEY = "admin_regs_range"
BCAST_STATE_KEY = "admin_broadcast"
ABOUT_STATE_KEY = "admin_about_edit"
WIDE_INVITE_STATE_KEY = "admin_wide_invite"
WIDE_LINK_LABEL_STATE_KEY = "wide_link_label"
ADMIN_REF_PROMPT_CHAT_ID_KEY = "admin_ref_prompt_chat_id"
ADMIN_REF_PROMPT_MESSAGE_ID_KEY = "admin_ref_prompt_message_id"
WIDE_INVITE_PROMPT_CHAT_ID_KEY = "wide_invite_prompt_chat_id"
WIDE_INVITE_PROMPT_MESSAGE_ID_KEY = "wide_invite_prompt_message_id"
WIDE_LINK_PROMPT_CHAT_ID_KEY = "wide_link_prompt_chat_id"
WIDE_LINK_PROMPT_MESSAGE_ID_KEY = "wide_link_prompt_message_id"

# فیلدهای قابل ویرایش سمینار: اسم، پیام آخر، زمان شروع (اختیاری)
SEMINAR_FIELDS = (
    "title",
    "message_template",
    "starts_at",
)

# ── الگوهای callback ──
PATTERN_MAIN = re.compile(r"^main$")
PATTERN_SEMINAR_VIEW = re.compile(r"^sem:v:(\d+)$")
PATTERN_SEMINAR_REGISTER = re.compile(r"^sem:reg:(\d+)$")
PATTERN_WIZ_LEVEL = re.compile(r"^wz:lv:(\d+):(\d+)$")
PATTERN_WIZ_CONFIRM = re.compile(r"^wz:ok:(\d+)$")
PATTERN_WIZ_CANCEL = re.compile(r"^wz:x$")

PATTERN_ADMIN_SEMS = re.compile(r"^adm:sems$")
PATTERN_ADMIN_SEM_NEW = re.compile(r"^adm:sem:new$")
PATTERN_ADMIN_SEM_PAGE = re.compile(r"^adm:sem:(\d+)$")
PATTERN_ADMIN_SEM_EDIT = re.compile(r"^adm:sem:e:(\d+)$")
PATTERN_ADMIN_SEM_EDIT_FIELD = re.compile(r"^adm:sem:ef:(\d+):([a-z_]+)$")
PATTERN_ADMIN_SEM_OPEN = re.compile(r"^adm:sem:open:(\d+)$")
PATTERN_ADMIN_SEM_DELETE = re.compile(r"^adm:sem:del:(\d+)$")
PATTERN_ADMIN_SEM_DELETE2 = re.compile(r"^adm:sem:del2:(\d+)$")
PATTERN_ADMIN_REGS = re.compile(r"^adm:regs:(\d+)$")
PATTERN_ADMIN_ADS = re.compile(r"^adm:ads$")
PATTERN_ADMIN_ADS_NEW = re.compile(r"^adm:ads:new$")
PATTERN_ADMIN_ADS_VIEW = re.compile(r"^adm:ads:v:(\d+)$")
PATTERN_ADMIN_ADS_TOGGLE = re.compile(r"^adm:ads:t:(\d+)$")
PATTERN_ADMIN_ADS_MSG = re.compile(r"^adm:ads:msg$")
PATTERN_ADMIN_ADS_REGS = re.compile(r"^adm:ads:rg:(\d+)$")
PATTERN_ADMIN_ADS_REGS_CSV = re.compile(r"^adm:ads:rgc:(\d+)$")
PATTERN_ADMIN_ADS_REGS_XLSX = re.compile(r"^adm:ads:rgx:(\d+)$")
PATTERN_ADMIN_ADS_RESET_PHRASE = re.compile(r"^adm:ads:pw:(\d+)$")
PATTERN_ADMIN_ADS_KICK = re.compile(r"^adm:ads:k:(\d+):(\d+)$")
PATTERN_ADMIN_ADS_ASSIGN = re.compile(r"^adm:ads:owner:(\d+)$")
PATTERN_ADMIN_ADS_OWNER_SET = re.compile(r"^adm:ads:owner-set:(\d+):(\d+)$")
PATTERN_ADMIN_ADS_DELETE = re.compile(r"^adm:ads:del:(\d+)$")
PATTERN_ADMIN_ADS_DELETE2 = re.compile(r"^adm:ads:del2:(\d+)$")
PATTERN_CH_LINK = re.compile(r"^ch:l:(\d+)$")
PATTERN_CH_ADD = re.compile(r"^ch:add$")
PATTERN_ADMIN_WIDE = re.compile(r"^adm:wide$")
PATTERN_ADMIN_WIDE_ADD = re.compile(r"^adm:wide:add$")
PATTERN_ADMIN_WIDE_REVOKE = re.compile(r"^adm:wide:revoke:(\d+)$")
PATTERN_WIDE_HOME = re.compile(r"^wa:home$")
PATTERN_WIDE_CREATE = re.compile(r"^wa:create$")
PATTERN_WIDE_VIEW = re.compile(r"^wa:view:(\d+)$")
PATTERN_WIDE_TOGGLE = re.compile(r"^wa:toggle:(\d+)$")
PATTERN_WIDE_RESET_PHRASE = re.compile(r"^wa:phrase:(\d+)$")
PATTERN_WIDE_KICK = re.compile(r"^wa:kick:(\d+):(\d+)$")
PATTERN_ADMIN_ADS_CSV = re.compile(r"^adm:ads:csv$")
PATTERN_ADMIN_ADS_XLSX = re.compile(r"^adm:ads:xlsx$")
PATTERN_ADMIN_REGS_MSG = re.compile(r"^adm:regs:msg:(\d+)$")
PATTERN_ADMIN_REGS_CSV = re.compile(r"^adm:regs:csv:(\d+)$")
PATTERN_ADMIN_REGS_CSV_COMPLETE = re.compile(r"^adm:regs:csv-complete:(\d+)$")
PATTERN_ADMIN_REGS_XLSX = re.compile(r"^adm:regs:xlsx:(\d+)$")
PATTERN_ADMIN_REGS_XLSX_COMPLETE = re.compile(r"^adm:regs:xlsx-complete:(\d+)$")
PATTERN_ADMIN_USERS_CSV = re.compile(r"^adm:users:csv$")
PATTERN_ADMIN_USERS_XLSX = re.compile(r"^adm:users:xlsx$")
PATTERN_ADMIN_EXPORT_LEADS = re.compile(r"^adm:export:leads$")
PATTERN_ADMIN_EXPORT_STARTS = re.compile(r"^adm:export:starts$")
PATTERN_ADMIN_EXPORT_ALL = re.compile(r"^adm:export:all:(leads|starts)$")
PATTERN_ADMIN_EXPORT_CANCEL = re.compile(r"^adm:export:cancel$")
PATTERN_ADMIN_RANGE = re.compile(r"^adm:range:(\w+)$")
PATTERN_ADMIN_BCAST = re.compile(r"^adm:bcast$")
PATTERN_ADMIN_BCAST_GO = re.compile(r"^adm:bcast:go$")
PATTERN_ADMIN_BCAST_NO = re.compile(r"^adm:bcast:no$")
PATTERN_ADMIN_REMINDERS = re.compile(r"^adm:rem$")
PATTERN_ADMIN_ABOUT = re.compile(r"^adm:about$")
