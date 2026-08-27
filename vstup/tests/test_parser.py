# -*- coding: utf-8 -*-
"""
Регресійні тести парсера на збережених сторінках сайту.

Живий сайт стоїть за Cloudflare і з CI недосяжний, тому тести ганяються по
знімках реальної розмітки у tests/fixtures/. Головна перевірка та сама, що й
у --debug: скільки блоків розібрано проти того, що сайт пише в «Знайдено».

    python3 -m pytest tests/ -q      або      python3 tests/test_parser.py
"""

import gzip, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import parser as P

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# сторінка -> (скільки блоків має бути, що сайт пише в «Знайдено»)
EXPECTED = {
    "f3_page1": (50, 67),   # перша сторінка з двох
    "f3_page2": (17, 67),   # 50 + 17 = 67, збігається з «Знайдено»
    "f2_page1": (27, 27),
    "f7_page1": (21, 21),
    "g5_page1": (33, 33),   # G5 — спеціальність поза галуззю IT
    "f1_page1": (32, 32),
}


def load(name):
    with gzip.open(os.path.join(FIX, name + ".html.gz"), "rt",
                   encoding="utf-8", errors="replace") as f:
        return f.read()


def test_block_count_matches_site():
    for name, (blocks, found) in EXPECTED.items():
        html = load(name)
        assert len(P.parse_page(html)) == blocks, f"{name}: не той підрахунок блоків"
        assert P.found_count(html) == found, f"{name}: не зчитано «Знайдено»"


def test_pagination_adds_up():
    total = len(P.parse_page(load("f3_page1"))) + len(P.parse_page(load("f3_page2")))
    assert total == P.found_count(load("f3_page1")) == 67


def test_fields_are_populated():
    """Той самий баг, через який ваги були порожні: регулярки під markdown."""
    rows = P.parse_page(load("f3_page1"))
    assert all(r["ЗВО"] != "?" for r in rows), "не зчитано назви ЗВО"
    assert all(r["Освітня програма"] for r in rows), "не зчитано освітні програми"
    assert all(r["Заяв подано"] > 0 for r in rows), "не зчитано кількість заяв"
    # хоча б у 90% має бути ненульова вага іспиту зі спеціальності
    with_k = sum(1 for r in rows if r["Іспит зі спец. (вага)"] > 0)
    assert with_k >= 0.9 * len(rows), f"ваги зчитано лише у {with_k} з {len(rows)}"


def test_non_it_specialty_label():
    """Мітку спеціальності треба зчитувати не лише для галузі F."""
    rows = P.parse_page(load("g5_page1"))
    assert all(r["Спеціальність"].startswith("G5") for r in rows), \
        "мітка G5 не зчитана — регулярка знову прив'язана до однієї літери"


def test_minimum_scores_extracted():
    """Мінімальні бали вирішують допуск і мають зчитуватись окремо."""
    rows = P.parse_page(load("f3_page1"))
    assert all(r["Мін. бал ТЗНК"] == "150" for r in rows)
    assert {r["Мін. бал ЄВВ"] for r in rows} >= {"100", "150"}


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn(); print(f"  ok  {fn.__name__}")
    print("усі тести пройдено")
