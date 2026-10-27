# -*- coding: utf-8 -*-
"""解析导出的 8D HTML 报告，抽出结构化数据供 PPT 使用（纯 XPath，无 cssselect）。"""

import json
import os
import re
import sys

from lxml import html as LH

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "report", "export-probe", "A-总览页导出")
if os.path.isdir(SRC):
    SRC = [os.path.join(SRC, f) for f in os.listdir(SRC) if f.endswith(".html")][0]

doc = LH.parse(SRC).getroot()


def txt(el):
    return re.sub(r"\s+", " ", el.text_content()).strip() if el is not None else ""


def first(el, xpath):
    r = el.xpath(xpath)
    return r[0] if r else None


report = {"source": os.path.basename(SRC), "sections": [], "modules": []}

t = doc.xpath("//title")
report["title"] = txt(t[0]) if t else ""

cover = doc.xpath('//*[contains(@class,"cover")]')
report["cover_text"] = txt(cover[0]) if cover else ""

for h2 in doc.xpath("//h2"):
    sec = h2.getparent()
    report["sections"].append({"title": txt(h2), "text": txt(sec)[:800]})

for card in doc.xpath('//article[contains(@class,"module-card")]'):
    h3 = first(card, ".//h3")
    tag_el = first(h3, './/span[contains(@class,"tag")]') if h3 is not None else None
    tag = txt(tag_el)
    name = txt(h3).replace(tag, "").strip()
    desc_el = first(card, './/div[contains(@class,"module-head")]//p')
    score_el = first(card, './/*[contains(@class,"module-score")]')
    events = []
    for ev in card.xpath('.//div[contains(@class,"mini-event")]'):
        cls = (ev.get("class") or "").split()
        sev = [c for c in cls if c != "mini-event"]
        events.append({
            "severity": sev[0] if sev else "",
            "time": txt(first(ev, ".//time")),
            "title": txt(first(ev, ".//b")),
            "detail": txt(first(ev, ".//p")),
        })
    report["modules"].append({
        "index": txt(first(card, './/*[contains(@class,"module-index")]')),
        "domain": tag,
        "name": name,
        "desc": txt(desc_el),
        "score": txt(score_el).replace("/ 100", "").strip(),
        "events": events,
    })

sev = {"critical": 0, "warning": 0, "info": 0}
dom = {}
for m in report["modules"]:
    dom.setdefault(m["domain"], 0)
    for e in m["events"]:
        sev[e["severity"]] = sev.get(e["severity"], 0) + 1
        dom[m["domain"]] += 1

report["stats"] = {
    "modules": len(report["modules"]),
    "events": sum(sev.values()),
    "critical": sev.get("critical", 0),
    "warning": sev.get("warning", 0),
    "info": sev.get("info", 0),
    "by_domain": dom,
}

out = os.path.join(BASE, "report", "8d-data.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("saved:", out)
print("stats:", json.dumps(report["stats"], ensure_ascii=False))
print("sections:")
for s in report["sections"]:
    print("   -", s["title"][:40])
print("modules:")
for m in report["modules"]:
    print(f"  {m['index']:>2} [{m['domain']}] {m['name'][:16]:<16} score={m['score']:<6} events={len(m['events'])}")
