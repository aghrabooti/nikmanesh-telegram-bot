#!/bin/bash
# ری‌استارت تمیز ربات (اگر خاموش باشد، روشنش می‌کند)
# استفاده:  bash ~/tizgam-seminar-bot/deploy/restart.sh
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR" || exit 1
mkdir -p data

# اول نگهدارنده را ببند تا ربات را دوباره اجرا نکند، بعد خودِ ربات را
pkill -f "run_forever.sh" 2>/dev/null
pkill -f "bot/main.py" 2>/dev/null
sleep 2
pkill -9 -f "bot/main.py" 2>/dev/null

# بالا آوردن مجدد زیر نظر نگهدارنده
nohup bash "$APP_DIR/deploy/run_forever.sh" >> data/supervisor.log 2>&1 &
sleep 4

if pgrep -f "bot/main.py" >/dev/null 2>&1; then
  echo "✅ ربات بالا آمد — لاگ زنده: tail -f $APP_DIR/data/polling.log"
else
  echo "❌ ربات بالا نیامد — آخر لاگ: tail -30 $APP_DIR/data/polling.log"
fi
