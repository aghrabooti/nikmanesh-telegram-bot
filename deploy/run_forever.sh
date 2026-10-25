#!/bin/bash
# نگهدارنده‌ی ربات — کرش را چندثانیه‌ای ری‌استارت می‌کند.
# ============================================================
# اجرا از طریق deploy/keepalive.sh (کران) یا deploy/restart.sh انجام
# می‌شود؛ مستقیم هم می‌شود اجرا کرد:
#   nohup bash deploy/run_forever.sh >> data/supervisor.log 2>&1 &
#
# قفل تک‌نمونه‌ای داخل خودِ ربات (bot/utils/instance.py) جلوی اجرای
# دوتایی را می‌گیرد.

# مسیر پایتونِ virtualenv اپ cPanel — با حساب خودتان تنظیم کنید:
PYTHON="${PYTHON:-/home/nikmanes/virtualenv/tizgam-seminar-bot/3.12/bin/python}"

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR" || exit 1
mkdir -p data

DELAY=5
while true; do
  START=$(date +%s)
  "$PYTHON" bot/main.py >> data/polling.log 2>&1
  UPTIME=$(( $(date +%s) - START ))
  if [ "$UPTIME" -ge 60 ]; then
    DELAY=5                                   # اجرای بلند → ریست تأخیر
  else
    DELAY=$(( DELAY * 2 )); [ "$DELAY" -gt 60 ] && DELAY=60
  fi
  echo "$(date '+%F %T') supervisor: bot exited after ${UPTIME}s — restart in ${DELAY}s" >> data/supervisor.log
  sleep "$DELAY"
done
