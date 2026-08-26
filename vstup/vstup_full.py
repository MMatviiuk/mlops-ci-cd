#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vstup_full.py — вивантаження конкурсних пропозицій до аспірантури (денна форма)
за спеціальностями галузі «Інформаційні технології» з ІС «Вступ.ОСВІТА.UA».

Дістає ЛО, кількість заяв і СКЛАДОВІ КОНКУРСНОГО БАЛА (ваги k та мін. бали).

    python3 vstup_full.py                      # усі сім кодів F1-F7
    python3 vstup_full.py --specs F1 F6        # тільки потрібні
    python3 vstup_full.py --debug              # діагностика парсера
    python3 vstup_full.py --from-file p1.html  # розібрати збережену сторінку
    python3 vstup_full.py --cookie "cf_clearance=..."   # обхід Cloudflare

Cron — двічі на добу, коли оновлюється ЄДЕБО (див. run_twice_daily.sh):
    30 6,20 * * *  cd /path/vstup && ./run_twice_daily.sh

------------------------------------------------------------------------------
ДОСТУП ДО САЙТУ. vstup.osvita.ua стоїть за Cloudflare з JS-челенджем. Запит без
браузерної сесії отримує 403 «Just a moment...». Це НЕ поламані регулярки — при
403 скрипт скаже про це прямо. Два робочі шляхи:
  1. запускати скрипт з машини, де сайт відкривається у браузері (звичайний
     домашній комп'ютер в Україні чи ЄС — челендж проходить мовчки);
  2. якщо челендж все одно спрацьовує — відкрити сайт у браузері, зі вкладки
     DevTools → Application → Cookies скопіювати значення cf_clearance і
     передати його через --cookie або змінну VSTUP_COOKIE. Кука живе ~годину-дві,
     для cron краще перший шлях.

ВАЖЛИВІ ЗАСТЕРЕЖЕННЯ ПРО ДАНІ (не видаляти):
  * «Ліцензований обсяг» (ЛО) — це НЕ кількість бюджетних місць, а ємність за
    ліцензією. Скільки місць держзамовлення дістанеться конкретному ЗВО, з цієї
    колонки не видно. Торік розподіл держзамовлення між вишами відбувся
    15 вересня — вже ПІСЛЯ дедлайну подачі заяв. Тобто на момент подачі
    (07.09.2026, 18:00) бюджетних цифр не існує в природі, і «заяв на місце»,
    порахований від ЛО, — лише груба проксі-оцінка конкурсу.
  * У 2026 на аспірантуру виділено 6 073 місця держзамовлення, на всю галузь
    «Інформаційні технології» — 769.
  * Формат навчання (дистанційно / очно) НІДЕ централізовано не публікується.
    Ні ЄДЕБО, ні ця сторінка його не містять. З'ясовується лише запитом у відділ
    аспірантури конкретного ЗВО. Колонки «Дистанційний формат» і «Скільки
    приїздів на рік» у робочій книзі заповнюються вручну за відповідями вишів.
  * Дані ЄДЕБО оновлюються двічі на добу, близько 06:00 і 20:00 за Києвом.
    Частіше запускати сенсу немає. Cache-busting параметр додається, бо інакше
    можна отримати вчорашній кеш.
"""

import argparse, csv, os, sys, time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parser as P

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

KYIV = timezone(timedelta(hours=3))
BASE = "https://vstup.osvita.ua"

SPECS = {
    "F1": ("2546", "Прикладна математика"),
    "F2": ("2547", "Інженерія програмного забезпечення"),
    "F3": ("2548", "Комп'ютерні науки"),
    "F4": ("2549", "Системний аналіз та наука про дані"),
    "F5": ("2550", "Кібербезпека та захист інформації"),
    "F6": ("2551", "Інформаційні системи і технології"),
    "F7": ("2552", "Комп'ютерна інженерія"),
}
# 7-640-1 = Доктор філософії / на основі магістра / денна форма
PATH = "/spec/7-640-1/0-0-{code}-0-0-{offset}/"
PAGE_SIZE = 50          # сайт віддає рівно 50 пропозицій на сторінку

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


class Blocked(Exception):
    """Cloudflare не пустив — це не проблема парсера."""


def fetch(path, cookie=None, debug=False):
    url = BASE + path + f"?_={int(time.time())}"
    h = dict(HEADERS)
    if cookie:
        h["Cookie"] = cookie
    r = requests.get(url, headers=h, timeout=45)
    if r.status_code == 403 or "Just a moment" in r.text[:3000]:
        raise Blocked(
            f"403 / Cloudflare-челендж на {url}\n"
            "        Сайт не пустив запит. Регулярки тут ні до чого.\n"
            "        Запустіть з машини, де сайт відкривається у браузері,\n"
            "        або передайте свіжу куку: --cookie \"cf_clearance=...\"")
    r.raise_for_status()
    if debug:
        print(f"    {path} → {len(r.text)}Б, ЄДЕБО {P.edebo_stamp(r.text)}, "
              f"знайдено {P.found_count(r.text)}")
    return r.text


def collect(spec_key, cookie=None, debug=False):
    code, label = SPECS[spec_key]
    rows, offset, total = [], 0, None
    while True:
        html = fetch(PATH.format(code=code, offset=offset), cookie, debug)
        if total is None:
            total = P.found_count(html)
        got = P.parse_page(html, f"{spec_key} {label}")
        if debug:
            print(f"    offset {offset}: розібрано {len(got)} блоків"
                  + (f" (усього за сайтом: {total})" if total is not None else ""))
        if not got:
            break
        rows += got
        offset += PAGE_SIZE
        if total is not None and len(rows) >= total:
            break
        if offset > 1000:
            print("    [!] забагато сторінок — зупиняюсь", file=sys.stderr)
            break
        time.sleep(1)

    uniq = list({r["Сторінка пропозиції"]: r for r in rows}.values())
    if total is not None and len(uniq) != total:
        print(f"    [!] розібрано {len(uniq)}, а сайт каже «Знайдено: {total}». "
              f"Перевірте регулярки в parser.py — верстку могли змінити.",
              file=sys.stderr)
    return uniq


def sort_key(r):
    v = r["Заяв на місце"]
    return (not isinstance(v, float), v if isinstance(v, float) else 0)


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", nargs="*", default=list(SPECS), choices=list(SPECS))
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--out", default="all_specs.csv")
    ap.add_argument("--cookie", default=os.environ.get("VSTUP_COOKIE"),
                    help="значення Cookie для обходу Cloudflare (cf_clearance=...)")
    ap.add_argument("--from-file", nargs="*", metavar="HTML",
                    help="розібрати збережені сторінки замість мережі")
    a = ap.parse_args()

    allrows, blocked = [], False

    if a.from_file:
        for p in a.from_file:
            html = open(p, encoding="utf-8", errors="replace").read()
            got = P.parse_page(html)
            print(f"[{p}] розібрано {len(got)} блоків "
                  f"(сайт каже «Знайдено: {P.found_count(html)}»)")
            allrows += got
    else:
        for s in a.specs:
            print(f"[{s}] {SPECS[s][1]}")
            try:
                got = collect(s, a.cookie, a.debug)
            except Blocked as e:
                print(f"    [!] {e}", file=sys.stderr); blocked = True; continue
            except Exception as e:
                print(f"    [!] {e}", file=sys.stderr); continue
            lo = sum(r["Ліцензований обсяг"] for r in got)
            za = sum(r["Заяв подано"] for r in got)
            if lo:
                print(f"    {len(got)} пропозицій | ЛО {lo} | заяв {za} | "
                      f"{za/lo:.2f} на місце")
            else:
                print(f"    {len(got)} пропозицій")
            allrows += got

    if not allrows:
        sys.exit("Cloudflare заблокував усі запити — див. підказку вище."
                 if blocked else
                 "нічого не зібрано — перевірте регулярки в parser.py")

    allrows = list({r["Сторінка пропозиції"]: r for r in allrows}.values())
    allrows.sort(key=sort_key)
    write_csv(allrows, a.out)

    print(f"\nзбережено: {a.out} ({len(allrows)} рядків), "
          f"{datetime.now(KYIV):%d.%m.%Y %H:%M} за Києвом")
    print("Нагадування: ЛО — це ліцензія, а не бюджетні місця. Розподіл "
          "держзамовлення торік стався 15.09, вже після дедлайну подачі.")
    print("\nТОП-15 за найнижчим конкурсом:")
    for r in allrows[:15]:
        print(f"  {str(r['Заяв на місце']):>6} | {r['Спеціальність'][:2]} | "
              f"ЛО {r['Ліцензований обсяг']:>2} | заяв {r['Заяв подано']:>3} | "
              f"през {r['Дослідн. пропозиція (вага)']} | {r['ЗВО'][:44]}")


if __name__ == "__main__":
    main()
