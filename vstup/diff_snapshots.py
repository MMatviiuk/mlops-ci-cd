#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diff_snapshots.py — порівнює свіжий зріз із попереднім і друкує, що змінилось.

Викликається з run_twice_daily.sh після vstup_full.py:
    python3 diff_snapshots.py snapshots/2026-09-01_0630.csv

Показує: де побільшало заяв, де змінився ЛО, які пропозиції з'явились
і які зникли. Стан зберігається у state.json.

ЛО — ємність за ліцензією, а не бюджетні місця: зростання «заяв на місце»
означає лише більшу тісноту серед поданих заяв, а не менші шанси на бюджет.
Розподіл держзамовлення торік оприлюднили 15.09 — після дедлайну подачі.
"""

import csv, json, os, sys
from datetime import datetime, timezone, timedelta

KYIV = timezone(timedelta(hours=3))
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
KEY = "Сторінка пропозиції"


def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(rows, stamp):
    st = {r[KEY]: {"lo": to_int(r["Ліцензований обсяг"]),
                   "zayav": to_int(r["Заяв подано"]),
                   "zvo": r["ЗВО"], "spec": r["Спеціальність"]} for r in rows}
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"stamp": stamp, "offers": st}, f, ensure_ascii=False, indent=1)


def main():
    if len(sys.argv) < 2:
        sys.exit("вкажіть шлях до свіжого CSV")
    rows = load_csv(sys.argv[1])
    only = set(sys.argv[2:]) or None      # необов'язковий шортлист URL-ів
    prev = load_state()
    old = prev.get("offers", {})
    stamp = datetime.now(KYIV).strftime("%d.%m.%Y %H:%M")

    tot_lo = sum(to_int(r["Ліцензований обсяг"]) for r in rows)
    tot_za = sum(to_int(r["Заяв подано"]) for r in rows)
    print(f"\n=== {stamp} (Київ) ===")
    print(f"пропозицій: {len(rows)} | ліцензованих місць: {tot_lo} | заяв: {tot_za}"
          + (f" | у середньому {tot_za/tot_lo:.2f} на місце" if tot_lo else ""))

    if not prev:
        print("Перший запуск — порівнювати нема з чим. Базу збережено.")
        save_state(rows, stamp)
        return

    changed, new, seen = [], [], set()
    for r in rows:
        k = r[KEY]
        seen.add(k)
        if only and k not in only:
            continue
        if k not in old:
            new.append(r)
        else:
            o = old[k]
            if o["zayav"] != to_int(r["Заяв подано"]) or o["lo"] != to_int(r["Ліцензований обсяг"]):
                changed.append((r, o))
    gone = [(k, v) for k, v in old.items()
            if k not in seen and (not only or k in only)]

    print(f"з попереднього зрізу ({prev.get('stamp', '?')}):")
    if not (changed or new or gone):
        print("  без змін")

    for r, o in sorted(changed, key=lambda x: -(to_int(x[0]["Заяв подано"]) - x[1]["zayav"])):
        za = to_int(r["Заяв подано"])
        d = za - o["zayav"]
        lo_note = (f"  ЛО {o['lo']}→{r['Ліцензований обсяг']}"
                   if o["lo"] != to_int(r["Ліцензований обсяг"]) else "")
        print(f"  {d:+4d} заяв  {o['zayav']:>3}→{za:<3} "
              f"конкурс {r['Заяв на місце']:>5}  {r['ЗВО'][:40]}{lo_note}\n"
              f"         {r[KEY]}")

    for r in new:
        print(f"  НОВА пропозиція: {r['Спеціальність'][:2]} ЛО {r['Ліцензований обсяг']}, "
              f"заяв {r['Заяв подано']}  {r['ЗВО'][:40]}\n         {r[KEY]}")
    for k, v in gone:
        print(f"  ЗНИКЛА пропозиція: {v.get('spec','')[:2]} {v.get('zvo','')[:40]}\n         {k}")

    hot = [r for r, o in changed if to_int(r["Заяв подано"]) - o["zayav"] >= 5]
    if hot:
        print(f"\n  !! за один зріз 5+ заяв додалось у {len(hot)} пропозиціях — "
              f"перегляньте шортлист")

    save_state(rows, stamp)


if __name__ == "__main__":
    main()
