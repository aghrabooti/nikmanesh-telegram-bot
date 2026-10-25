# 🎓 ربات وبینار آکادمی نیک منش (تلگرام)

ربات رسمی **آکادمی نیک منش** برای **معرفی، ثبت‌نام و مدیریت وبینار** در
تلگرام — کاربر با پیام خوش‌آمد و دکمه‌ی رنگی «وبینار {فعال}» وارد می‌شود و
با یک فرم چندمرحله‌ای (نام ← گروه ← شهر ← شماره تماس ← تأیید) ثبت‌نام
می‌کند؛ مدیر از داخل تلگرام وبینار می‌سازد (با **پیام نهایی اختصاصی**)،
**پیام همگانی** می‌فرستد و **یادآورهای خودکار** (ناتمام‌ها روزانه و
کامل‌شده‌ها ۱۲/۲ ساعت قبل از شروع) فعال است.

ساخته‌شده با **python-telegram-bot v22** (async)؛ بدون وابستگی سنگین،
با دیتابیس SQLite و معماری ماژولار.

---

## ✨ امکانات

| # | بخش | توضیح |
|---|------|-------|
| ۱ | منوی کاربر | **ریپلای کیبورد ثابت**: «وبینار {فعال}» + «درباره آکادمی نیک منش» + «ارتباط با ما» |
| ۱٫۵ | پیام /start | دکمه‌ی **شیشه‌ای رنگی** «وبینار {فعال}» زیر پیام خوش‌آمد |
| ۲ | صفحه‌ی سمینار | عنوان، توضیح، تاریخ/زمان برگزاری + دکمه‌ی ثبت‌نام |
| ۳ | فرم ثبت‌نام ۷ مرحله‌ای | نام ← پایه (۴۰۶/۴۰۷/۴۰۸) ← رشته (تجربی/ریاضی/انسانی) ← شهر ← شماره تلگرام (دکمه‌ی اشتراک یا تایپ) ← **تایید شماره** (دکمه‌ی «✅ شماره‌م درسته» یا شماره‌ی پیامک جایگزین ۰۹…۱۱ رقم) ← پیام آخر |
| ۴ | شماره تماس | دکمه‌ی بومی «اشتراک مخاطب» تلگرام یا تایپ دستی (نرمال‌سازی `+98…`) |
| ۵ | ادامه از همین‌جا | انصراف/خروج پیشرفت را حفظ می‌کند؛ دوباره ورود = ادامه از همان مرحله |
| ۶ | پیام نهایی | قالب قابل‌تنظیم با `{name}` `{seminar}` `{date}` `{link}` — **اختصاصی برای هر سمینار** |
| 🔗 | **لینک‌های رفرال اسم‌دار** (مثل تیزگام) | مدیر در پنل هر چند لینک `t.me/<bot>?start=ref_<کد>` با برچسب دلخواه می‌سازد؛ استارت‌ها first-touch شمرده می‌شوند؛ قیف ثبت‌نام/پایه/نرخ تبدیل هر لینک + ارگانیک + CSV — و **لیست/CSV ثبت‌نامی‌های هر لینک (اسم+شماره)** در صفحه‌ی همان لینک؛ دستورهای مدیریتی (/admin و /channels) در منوی دستورات نیستند — فقط با تایپ مستقیم کار می‌کنند |
| 📡 | **بخش کانال‌ها (/channels)** | هر لینک رفرال یک رمز ورود خودکار دارد؛ ادمین کانال با رمز وارد می‌شود و **فقط آمار تجمیعی** می‌بیند (ورودی/ثبت‌نام/قیف/پایه — بدون هیچ داده‌ی شخصی)؛ ورودش به ادمین ربات اطلاع داده می‌شود و ادمین می‌تواند رمز را جدید یا شخص را بیرون کند |
| 🛠 | **پنل مدیریت** | `/admin` → ساخت/ویرایش/حذف سمینار + باز/بسته کردن ثبت‌نام + آمار هر سمینار جدا |
| 📣 | **پیام همگانی** | ارسال هر پیام مدیر (متن/عکس/ویدیو/فوروارد) به همه — از **صف با نرخ ۵ در ثانیه** |
| ⏰ | **یادآور خودکار** | ناتمام‌ها روزانه + کامل‌شده‌ها ۱۲ و ۲ ساعت قبل از شروع |
| 📋 | **ثبت‌نام‌ها** | لیست با نام/گروه/شهر/**شماره** + قیف آماری هر سمینار |
| 📥 | **خروجی‌ها** | پیام تلگرامی + CSV سازگار با Excel فارسی + فیلتر بازه‌ی تاریخ شمسی |

---

## 📚 سمینارها و گروه‌بندی

- هر سمینار: عنوان، توضیح، متن تاریخ، لینک گروه/کانال، گروه‌ها و وضعیت باز/بسته.
- «گروه» یعنی پایه‌ی تحصیلی (مثل ششم/نهم)؛ سمینار می‌تواند بدون گروه هم باشد —
  در آن صورت مرحله‌ی گروه در فرم حذف می‌شود.
- فقط سمینارهای **باز** به کاربر نمایش داده می‌شوند؛ بستن ثبت‌نام سمینار را
  از منو حذف نمی‌کند ولی دکمه‌ی ثبت‌نام را برمی‌دارد.
- **وبینار فعال** = جدیدترین سمینار باز؛ نام دکمه‌ی ثابت «وبینار …» و دکمه‌ی
  رنگی زیر /start از همین جا می‌آید و خودکار عوض می‌شود.
- تمام مراحل ثبت‌نام با **ریپلای کیبورد** + دکمه‌های «⬅️ مرحله قبل» و
  «🔙 بازگشت» (بازگشت = خروج با حفظ پیشرفت).

---

## 🚀 راه‌اندازی (محلی)

```bash
# ۱) دریافت کد و ساخت محیط مجازی
python3 -m venv .venv
source .venv/bin/activate        # ویندوز: .venv\Scripts\activate

# ۲) نصب وابستگی‌ها
pip install -r requirements.txt

# ۳) تنظیمات
cp .env.example .env
# ویرایش .env → BOT_TOKEN (از @BotFather) و ADMIN_IDS

# ۴) اجرا
python -m bot                    # یا: python bot/main.py
```

نمونه‌ی `.env`:

```env
BOT_TOKEN=123456789:AAF...
ADMIN_IDS=123456789,987654321
```

> شناسه‌ی خود را با فرمان **`/id`** از خود ربات بگیرید.

---

## 🧪 تست‌ها

```bash
pip install -r requirements-dev.txt
pytest            # ۹۹ تست — فلوهای کاربر، منو، ویزارد ۷ مرحله‌ای، پنل، همگانی، صف و یادآورها
ruff check .      # لینت
ruff format .     # فرمت
```

---

## 🏗 معماری

```
bot/
├── main.py            # نقطه‌ی ورود polling + ساخت اپلیکیشن
├── webhook.py         # حالت وب‌هوک (هاست اشتراکی)
├── navigation.py      # رندر یکنواخت صفحه‌ها
├── constants.py       # کالبک‌ها و الگوها
├── config/
│   ├── settings.py    # خواندن .env (BOT_TOKEN, ADMIN_IDS, …)
│   └── content.py     # تمام متن‌های فارسی — تنها منبع محتوا
├── keyboards/
│   ├── user.py        # منوی کاربر و صفحه‌ی سمینار
│   └── admin.py       # کیبوردهای پنل مدیریت
├── handlers/
│   ├── start.py       # /start /menu /id + منوی اصلی
│   ├── seminars.py    # صفحه‌ی سمینار (کاربر)
│   ├── wizard.py      # فرم ثبت‌نام چندمرحله‌ای
│   ├── admin.py       # پنل مدیریت (گروه ۰)
│   └── errors.py      # خطای سراسری + fallback
└── services/
    ├── database.py    # SQLite: اسکیما + مهاجرت سبک
    ├── seminars.py    # سمینارها + ثبت‌نام‌ها (تنها لایه‌ی SQL)
    ├── users.py       # کاربران استارت‌کرده (گیرنده‌های همگانی)
    └── reminders.py   # یادآورهای خودکار (حلقه‌ی پس‌زمینه)
```

**ترتیب گروه‌های هندلر (مهم):** پنل ادمین گروه ۰ (اگر state فعالی نداشته
باشد عبور می‌دهد)، ویزارد گروه ۱، پیام پیش‌فرض گروه ۲.

---

## 🛠 پنل مدیریت

دسترسی فقط برای شناسه‌های `ADMIN_IDS` (فایل `.env`). شناسه‌ی خود را با
فرمان **`/id`** بگیرید. ورود: **`/admin`**

- 📚 **مدیریت سمینارها:** لیست همه‌ی سمینارها (🟢 باز / 🔴 بسته) با **آمار
  جداگانه‌ی هر سمینار** (کل / کامل / نیمه‌کاره) + ساخت سمینار جدید با
  **فقط دو ورودی: اسم سمینار + پیام آخر**.
- 🎓 **صفحه‌ی هر سمینار:** وضعیت، فیلدها (از جمله **زمان شروع**)، آمار
  (کل/کامل/نیمه‌کاره) و قیف مرحله‌به‌مرحله.
- ✏️ **ویرایش:** اسم سمینار / **پیام آخر** / زمان شروع (اختیاری) — هر کدام جدا.
- ✉️ **پیام آخر:** «-» یا خالی = پیام سراسری؛ «پیش‌فرض» = بازگشت به سراسری؛
  سقف ۸۰۰ نویسه؛ جای‌گذارهای `{name}` و `{seminar}`.
- 📣 **پیام همگانی:** هر پیام مدیر (متن، عکس، ویدیو، فایل، فوروارد و…)
  بعد از تأیید، **عیناً** به همه‌ی کاربرانی که ربات را استارت کرده‌اند
  کپی می‌شود؛ با شمار گیرنده‌ها و گزارش موفق/ناموفق.
- ⏰ **یادآورها:** خاموش/روشن کردن از پنل (پیش‌فرض: روشن).
- 📖 **متن «درباره آکادمی»:** ویرایش پست صفحه‌ی درباره از پنل
  («پیش‌فرض» = بازگشت به متن اولیه؛ HTML مجاز؛ سقف ۲۵۰۰ نویسه).
- 🔒 **باز/بسته:** کلید وضعیت ثبت‌نام.
- 🗑 **حذف:** تأیید دومرحله‌ای (ثبت‌نام‌های سمینار هم حذف می‌شوند).
- 📋 **ثبت‌نام‌ها:** شمارش در بازه + خروجی **پیام تلگرامی** و **CSV**
  (نام، گروه، شهر، شماره، وضعیت) با فیلتر تاریخ شمسی.

> ⚠️ «گروه» فقط برای سمینارهای گروه‌بندی‌دار در گزارش می‌آید؛ قیفِ
> سمینار بدون گروه، مرحله‌ی گروه را نشان نمی‌دهد.

---

## 🗓 فیلتر بازه‌ی تاریخ شمسی خروجی‌ها

در صفحه‌ی «ثبت‌نام‌ها»ی هر سمینار: دکمه‌های **امروز / ۷ روز / ۳۰ روز /
۹۰ روز اخیر / همه‌ی زمان‌ها** یا **بازه‌ی دلخواه** با فرستادن دو تاریخ
شمسی (مثل `۱۴۰۵/۰۷/۰۱ تا ۱۴۰۵/۰۷/۱۵`؛ ارقام فارسی یا انگلیسی،
جداکننده‌ی `/` یا `-` یا `.`). فیلتر روی هر دو خروجی (پیام و CSV) اعمال
می‌شود. تاریخ‌ها در گزارش‌ها شمسی نمایش داده می‌شوند؛ CSV برای سازگاری
ماشین، ISO میلادی نگه می‌دارد (ماژول داخلی `bot/utils/jalali.py` — بدون
وابستگی جدید).

---

## ⏰ یادآورهای خودکار

سرویس پس‌زمینه (`bot/services/reminders.py`) هر ۱۰ دقیقه چک می‌کند:

| گیرنده | یادآور | شرط |
|--------|--------|------|
| ثبت‌نام **ناتمام** | «ادامه‌ی ثبت‌نام» + دکمه‌ی بازکردن همان مرحله | گذشت یک روز کامل (روزانه) از آخرین فعالیت و سمینار هنوز شروع نشده |
| ثبت‌نام **کامل** | یادآور ۱۲ ساعت قبل از شروع | ۱۲ > زمان باقیمانده > ۲ ساعت |
| ثبت‌نام **کامل** | یادآور ۲ ساعت قبل از شروع | ۰ < زمان باقیمانده ≤ ۲ ساعت |

**ضد اسپم:** هر یادآور برای هر کاربر فقط **یک بار** ارسال می‌شود (جدول
`reminders` در دیتابیس)؛ بعد از شروع سمینار **هیچ** یادآوری نمی‌آید؛
سمینار بدون زمان شروع حداکثر **۸** یادآور ناتمامی می‌فرستد (نه تا ابد)؛
سمینار بسته و کلید خاموش پنل = بدون یادآور.

- **زمان شروع** هنگام ساخت/ویرایش سمینار با فرمت شمسی داده می‌شود:
  `۱۴۰۵/۰۸/۱۵ ۱۸:۰۰` (پیش‌فرض ساعت ۱۲:۰۰؛ «`-`» یا «هیچ» = بدون زمان).
- منطق زمانی روی ساعت **سرور** است؛ برای ایران روی VPS تنظیم کنید:
  `sudo timedatectl set-timezone Asia/Tehran`
- در حالت **وب‌هوک** هم حلقه‌ی یادآور داخل پروسه‌ی ربات اجرا می‌شود
  (نیازی به cron جدا نیست).

---

## 📤 صف ارسال انبوه (ضد 429)

همه‌ی ارسال‌های گروهی (پیام همگانی و یادآورها) از **صف واحد**
(`bot/services/sender.py`) می‌گذرند:

- نرخ ارسال: **۵ گیرنده در ثانیه** (فاصله‌ی ۰٫۲ ثانیه بین پیام‌ها)؛
- خطای `429 TooManyRequests` → صبر به‌اندازه‌ی اعلام‌شده‌ی تلگرام + ۱ ثانیه،
  سپس تا ۳ تلاش؛
- خطای دیگر تلگرام (مثل بلاک‌شدن کاربر) فقط همان گیرنده را رد می‌کند؛
- دیتابیس قدیمی (ستون‌های جاافتاده مثل `started_at`) هنگام اجرا
  **خودکار مهاجرت** می‌شود.

---

## 🖥 Deployment (production)

### VPS (recommended — polling mode)

```bash
# 1) Prerequisites
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git

# 2) Get the code onto the server
sudo mkdir -p /opt/tizgam-seminar-bot && sudo chown $USER /opt/tizgam-seminar-bot
cd /opt/tizgam-seminar-bot
# copy the project here (git clone, or unzip the release zip)

# 3) Virtual environment and dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4) Configuration
cp .env.example .env
nano .env          # set BOT_TOKEN + ADMIN_IDS

# 5) One-shot test run before installing the service
python -m bot      # must start without errors; stop with Ctrl+C

# 6) systemd service (auto-start on boot, restart on crash)
sudo cp deploy/tizgam-seminar-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tizgam-seminar-bot
sudo systemctl status tizgam-seminar-bot     # must be active (running)

# Logs:
journalctl -u tizgam-seminar-bot -f
```

### Shared hosting / cPanel (polling + nohup — same as tizgam bot)

The Python App in cPanel is used **only** to create the virtualenv and install
dependencies (`passenger_wsgi.py` is a plain health page and never runs the
bot). The bot itself runs as a background polling process via `nohup`, kept
alive by a cron script.

```bash
# 1) cPanel → Setup Python App → Create Application
#      Python version:            3.10+
#      Application root:          tizgam-seminar-bot
#      Application startup file:  passenger_wsgi.py
#    Then "Run pip install" for requirements.txt (app page).

# 2) cPanel → Terminal — start the bot:
cd ~/tizgam-seminar-bot
source ~/virtualenv/tizgam-seminar-bot/3.X/bin/activate   # exact path is shown on the app page
curl -s "https://api.telegram.org/bot<TOKEN>/deleteWebhook"  # required once
nohup python bot/main.py >> data/polling.log 2>&1 &
tail -f data/polling.log        # Ctrl+C exits only the log view

# 3) Keep-alive + crash recovery (shared hosts kill background processes):
#    edit paths at the top of deploy/keepalive.sh, then
bash deploy/keepalive.sh        # manual test: silent if the bot is alive
#    cPanel → Cron Jobs → Every minute (fallback: every 5 minutes) →
#    command (this line only!):
#    bash /home/USER/tizgam-seminar-bot/deploy/keepalive.sh

# Restart / stop:
bash deploy/restart.sh          # clean restart (also starts if stopped)
pkill -f "run_forever.sh"; pkill -f "bot/main.py"    # full stop
```

- A cross-process single-instance lock (`bot/utils/instance.py`, `tmp/bot.lock`)
  guarantees only one bot process runs, no matter how many times keepalive or
  a Passenger worker fires.
- Recovery layers: PTB auto-reconnects polling across network drops;
  `deploy/run_forever.sh` restarts the bot within seconds of a crash; the cron
  job revives everything after a host reboot (within one cron interval).
  `bash deploy/restart.sh` is the one-command clean restart.
- The app URL shows `bot process: running ✔` / `stopped` as a quick health check.
- The detection pattern `bot/main.py` is intentionally different from the
  tizgam bot's `-m bot`, so both bots can live on the same host.

---

## 📄 مجوز

مالکیت: تیم تیزگام — استفاده‌ی تجاری با هماهنگی.
