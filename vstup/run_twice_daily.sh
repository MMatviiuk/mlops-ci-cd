#!/usr/bin/env bash
# Один прохід моніторингу: вивантажити свіжі дані і показати діф до минулого разу.
#
# Cron — двічі на добу, невдовзі після оновлення ЄДЕБО (~06:00 і ~20:00 за Києвом).
# Рядок для crontab (сервер у UTC — Київ це UTC+3, тому 03:30 і 17:30 UTC):
#
#   30 3,17 * * *  /path/to/vstup/run_twice_daily.sh >> /path/to/vstup/vstup.log 2>&1
#
# Якщо сервер уже живе за Києвом, простіше:
#   CRON_TZ=Europe/Kyiv
#   30 6,20 * * *  /path/to/vstup/run_twice_daily.sh >> /path/to/vstup/vstup.log 2>&1
#
# Куку Cloudflare (якщо потрібна) покладіть у vstup/.cookie — один рядок виду
#   cf_clearance=...
# Файл читається автоматично; тримайте до нього доступ 600.
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p snapshots

STAMP=$(TZ=Europe/Kyiv date +%Y-%m-%d_%H%M)
OUT="snapshots/all_specs_${STAMP}.csv"

if [ -f .cookie ]; then
    export VSTUP_COOKIE="$(head -n1 .cookie)"
fi

echo "----- запуск $(TZ=Europe/Kyiv date '+%d.%m.%Y %H:%M') за Києвом -----"

if ! python3 vstup_full.py --out "$OUT"; then
    echo "[!] вивантаження не вдалося — попередній стан не чіпаю" >&2
    exit 1
fi

cp "$OUT" latest.csv
python3 diff_snapshots.py "$OUT"

# знімки старші за 60 днів прибираємо
find snapshots -name 'all_specs_*.csv' -mtime +60 -delete
