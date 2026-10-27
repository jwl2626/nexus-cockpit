# -*- coding: utf-8 -*-
"""把「显示屏 SerDes 链路」面板从外设区搬到显示监控区，并注册新的详情模板。"""

p = "app.js"
t = open(p, encoding="utf-8").read()

start = t.index("        ${panelHTML('显示屏 SerDes 链路'")
end = t.index("FPD-LINK IV' })}", start) + len("FPD-LINK IV' })}\n")
serdes = t[start:end]
t = t[:start] + t[end:]

display_fn = (
    "  function displayDetailTemplate() {\n"
    "    return `\n"
    "      <div class=\"detail-panels\">\n"
    + serdes
    + "      </div>\n"
    "    `;\n"
    "  }\n\n"
)

anchor = "  function peripheralsDetailTemplate() {"
if "function displayDetailTemplate" not in t:
    t = t.replace(anchor, display_fn + anchor, 1)

old_case = "case 'peripherals': content = peripheralsDetailTemplate(); break;"
new_case = old_case + "\n      case 'display': content = displayDetailTemplate(); break;"
if "case 'display'" not in t:
    t = t.replace(old_case, new_case, 1)

open(p, "w", encoding="utf-8", newline="\n").write(t)
print("serdes moved:", len(serdes), "chars")
print("has displayDetailTemplate:", "function displayDetailTemplate" in t)
print("has case display:", "case 'display'" in t)
print("serdes still in peripherals:", "显示屏 SerDes 链路" in t[t.index("function peripheralsDetailTemplate"):t.index("function displayDetailTemplate")])
