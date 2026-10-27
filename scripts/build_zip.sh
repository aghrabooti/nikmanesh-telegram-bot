#!/usr/bin/env bash
# ساخت زیپ قابل تحویل از سورس — مستقل از git (بر پایه‌ی cp)
# استفاده: bash scripts/build_zip.sh [مسیر-خروجی]
set -euo pipefail

OUT="${1:-dist/tizgam-seminar-bot.zip}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/tizgam-seminar-bot"
cd "$ROOT"
cp -r bot tests deploy scripts docs README.md requirements.txt requirements-dev.txt \
      pyproject.toml .env.example .gitignore "$STAGE/tizgam-seminar-bot/"

# پاک‌سازی فایل‌های بایت‌کد
find "$STAGE" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

mkdir -p "$(dirname "$OUT")"
OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"

if command -v zip >/dev/null 2>&1; then
  (cd "$STAGE" && zip -qr "$OUT" tizgam-seminar-bot)
else  # جایگزین بدون zip
  (cd "$STAGE" && python3 -c "import shutil; shutil.make_archive('${OUT%.zip}', 'zip', '.')")
fi

echo "zip: $OUT ($(du -h "$OUT" | cut -f1), $(unzip -l "$OUT" 2>/dev/null | tail -1 | awk '{print $2}') files)"
