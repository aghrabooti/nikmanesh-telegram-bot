#!/bin/bash
# نگهدارنده‌ی ربات در حالت polling روی هاست اشتراکی (cPanel)
# ============================================================
# مشکل: هاست اشتراکی پروسه‌های پس‌زمینه را می‌کشد یا با هر ری‌بوت
# پاک می‌کنند؛ nohup به‌تنهایی کافی نیست.
#
# راه‌حل: این اسکریپت را cron صدا بزنید (ترجیحاً هر دقیقه) — اگر
# ربات یا نگهدارنده‌اش زنده باشد هیچ کاری نمی‌کند و اگر مرده باشد،
# نگهدارنده (deploy/run_forever.sh) را بالا می‌آورد که ربات را اجرا
# و در صورت کرش چند ثانیه‌ای ری‌استارت می‌کند.
#
# نصب (در cPanel → Cron Jobs → Add New Cron Job):
#   Common Settings: Every minute (یا حداقل Every 5 minutes)
#   Command: bash /home/USER/tizgam-seminar-bot/deploy/keepalive.sh
#
# ⚠️ نکته‌ی مهم: خط cron «فقط همین یک فراخوانی» باشد — الگوی pgrep
# باید داخل این فایل بماند، نه در خط cron؛ وگرنه pgrep متنِ خودِ دستور
# cron را هم مچ می‌کند و فکر می‌کند ربات از قبل روشن است!
#
# ⚠️ الگوی شناسایی «bot/main.py» است تا با ربات تیزگام (که با «-m bot»
# اجرا می‌شود) قاطی نشود — همین‌جوری روی یک هاست کنار هم کار می‌کنند.
#
# مسیرها را با حساب هاست خودتان تنظیم کنید:

APP_DIR="${APP_DIR:-/home/nikmanes/tizgam-seminar-bot}"

cd "$APP_DIR" || exit 1
mkdir -p data

# اگر ربات یا نگهدارنده در حال اجراست، کاری نکن
if pgrep -f "bot/main.py" >/dev/null 2>&1 || pgrep -f "run_forever.sh" >/dev/null 2>&1; then
  exit 0
fi

# هیچ‌چیز زنده نیست → نگهدارنده را بالا بیاور + ثبت رویداد
nohup bash "$APP_DIR/deploy/run_forever.sh" >> data/supervisor.log 2>&1 &
echo "$(date '+%F %T') keepalive: supervisor started" >> data/keepalive.log
