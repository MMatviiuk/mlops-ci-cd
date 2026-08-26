# -*- coding: utf-8 -*-
"""
Парсер сторінки переліку конкурсних пропозицій ІС «Вступ.ОСВІТА.UA».

Регулярки написані під РЕАЛЬНУ HTML-розмітку сайту (перевірено на знімку
сторінки F3 від 26.02.2026: 50 блоків на сторінку, «Знайдено: 67»).

Попередня версія парсера була написана під markdown-конвертацію сторінки
(`**Освітня програма:**`, `[97. НУ ...](url)`), а fetch() віддає сирий HTML,
тому ЗВО/програма/факультет/ваги не зчитувалися ніколи.

Структура одного блоку в HTML:

    <div class="row no-gutters table-of-specs-item-row">
      <!--/r27/3746/1564633/-->
      <span class="search">
        <b>F3 Комп'ютерні науки</b><br><b>Доктор філософії</b> / Магістр/ ЛО 5 / Фіксована<br>
        <b>Освітня програма:</b> ...<br><b>Факультет:</b> ...<br>
        <a href="/r27/3746/">3746. Інститут ...</a>
      </span>
      <li><div class="sub_93"><b>Вcтупний іспит зі спеціальності</b>
          <div class="sub">(Іспит, бал<sub>min</sub>=<span class="minbal">120</span>,
                            k=<span class="coef">0.40</span>)</div></div></li>
      <a href="/y2026/r27/3746/1564633/" class="green-button">Детальніше</a>
      <div class="zayava-count"><span>заяв: </span><span>10</span></div>
    </div>
"""

import re

BASE = "https://vstup.osvita.ua"

# Маркер початку блоку пропозиції.
BLOCK_SPLIT = re.compile(r'<div class="row no-gutters table-of-specs-item-row">')
# Ідентифікатор пропозиції: у HTML-коментарі та в посиланні «Детальніше».
ID_COMMENT = re.compile(r"<!--\s*/(r\d+)/(\d+)/(\d+)/\s*-->")
ID_LINK = re.compile(r'href="/y(\d{4})/(r\d+)/(\d+)/(\d+)/"[^>]*class="green-button"')

FOUND_RE = re.compile(r"Знайдено:\s*(\d+)")
UPDATED_RE = re.compile(r"Дані отримані з ЄДЕБО[^\d]{0,20}([\d.]+\s*[\d:]*)")

SPEC_RE = re.compile(r"<b>(F\d[^<]{0,80})</b>")
LO_RE = re.compile(r"ЛО\s*(\d+)")
# Число заяв лежить в ОКРЕМОМУ <span>, тому старе r"заяв:\s*(\d+)" не працювало.
ZAYAV_RE = re.compile(r'zayava-count"><span>\s*заяв:\s*</span>\s*<span>\s*(\d+)\s*</span>')
ZVO_RE = re.compile(r'<a href="/r\d+/\d+/"[^>]*>\s*(\d+)\.\s*([^<]{3,200}?)\s*</a>')
PROG_RE = re.compile(r"<b>\s*Освітня програма:\s*</b>\s*([^<]+)")
FAK_RE = re.compile(r"<b>\s*Факультет:\s*</b>\s*([^<]+)")
# «<b>Назва</b> <div class="sub">(Тип, бал<sub>min</sub>=<span class="minbal">100</span>,
#                                 k=<span class="coef">0.60</span>)</div>»
COMP_RE = re.compile(
    r"<b>\s*([^<]{3,160}?)\s*</b>\s*"
    r'<div class="sub">\s*\(\s*([^,()]*?)\s*,?\s*'
    r'(?:бал<sub>min</sub>\s*=\s*<span class="minbal">\s*(\d+)\s*</span>\s*,\s*)?'
    r'k\s*=\s*<span class="coef">\s*([\d.]+)\s*</span>\s*\)',
    re.S)


def strip_tags(html):
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", "\n", html)


def unescape(s):
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'),
                 ("&#039;", "'"), ("&laquo;", "«"), ("&raquo;", "»")):
        s = s.replace(a, b)
    return " ".join(s.split())


def found_count(html):
    m = FOUND_RE.search(strip_tags(html))
    return int(m.group(1)) if m else None


def edebo_stamp(html):
    m = UPDATED_RE.search(strip_tags(html))
    return m.group(1).strip() if m else "?"


def classify(name):
    """Куди віднести випробування: іспит зі спец., дослідн. пропозиція, чи інше.

    ЄВВ, іноземна та ТЗНК у конкурсний бал входять з фіксованими вагами (або
    не входять зовсім), але їхні МІНІМАЛЬНІ БАЛИ вирішують допуск і в різних
    ЗВО різні — тому вони повертаються окремими категоріями, а не «ignore».
    """
    n = name.lower()
    if "євв" in n:
        return "evv"
    if "тзнк" in n:
        return "tznk"
    if "іноземна мова" in n:
        return "mova"
    if "конкурсний показник" in n:
        return "ignore"
    if "презентац" in n or "дослідниц" in n or "пропозиц" in n:
        return "pres"
    if "іспит зі спеціальності" in n or "іспит із спеціальності" in n:
        return "isp"
    return "other"


def parse_page(html, spec_label=""):
    """Повертає список пропозицій. Один елемент = один блок таблиці."""
    rows = []
    starts = [m.start() for m in BLOCK_SPLIT.finditer(html)]
    for i, s in enumerate(starts):
        block = html[s: starts[i + 1] if i + 1 < len(starts) else len(html)]

        ids = ID_LINK.search(block)
        if ids:
            year, reg, zvo_id, offer_id = ids.groups()
        else:
            c = ID_COMMENT.search(block)
            if not c:
                continue
            reg, zvo_id, offer_id = c.groups()
            year = "2026"

        lo = LO_RE.search(block)
        lo = int(lo.group(1)) if lo else 0
        za = ZAYAV_RE.search(block)
        za = int(za.group(1)) if za else 0

        zvo = ZVO_RE.search(block)
        zvo = unescape(zvo.group(2)) if zvo else "?"
        prog = PROG_RE.search(block)
        prog = unescape(prog.group(1)) if prog else ""
        fak = FAK_RE.search(block)
        fak = unescape(fak.group(1)) if fak else ""
        spec = SPEC_RE.search(block)
        spec = unescape(spec.group(1)) if spec else spec_label

        k_isp = k_pres = 0.0
        min_isp = min_pres = ""
        min_evv = min_mova = min_tznk = ""
        other = []
        for name, typ, bmin, k in COMP_RE.findall(block):
            name = unescape(name)
            kind = classify(name)
            k = float(k)
            if kind == "isp":
                k_isp, min_isp = k, bmin
            elif kind == "pres":
                k_pres, min_pres = k, bmin
            elif kind == "evv":
                min_evv = bmin or min_evv
            elif kind == "tznk":
                min_tznk = bmin or min_tznk
            elif kind == "mova":
                min_mova = bmin or min_mova
            elif kind == "other" and k > 0:
                other.append(f"{name} (k={k}" + (f", мін.{bmin}" if bmin else "") + ")")

        rows.append({
            "Спеціальність": spec,
            "ЗВО": zvo,
            "Освітня програма": prog,
            "Факультет": fak,
            "Ліцензований обсяг": lo,
            "Заяв подано": za,
            "Заяв на місце": round(za / lo, 2) if lo else "н/д (ЛО=0)",
            "Іспит зі спец. (вага)": k_isp,
            "Мін. бал за іспит зі спец.": min_isp or "не встановлено",
            "Дослідн. пропозиція (вага)": k_pres,
            "Мін. бал за пропозицію": min_pres or "—",
            "Мін. бал ЄВВ": min_evv or "—",
            "Мін. бал іноземної": min_mova or "—",
            "Мін. бал ТЗНК": min_tznk or "—",
            "Інші випробування / нюанси": "; ".join(other),
            "Контакти приймальної комісії": f"{BASE}/{reg}/{zvo_id}/entrance.html",
            "Сторінка пропозиції": f"{BASE}/y{year}/{reg}/{zvo_id}/{offer_id}/",
        })
    return rows
