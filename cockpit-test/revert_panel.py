# -*- coding: utf-8 -*-
p = "app.js"
t = open(p, encoding="utf-8").read()
old = "return `${content}${monitorSpecPanel(moduleState)}${diagnosisPanel(moduleState)}`"
new = "return `${content}${diagnosisPanel(moduleState)}`"
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="\n").write(t)
print("detached:", old not in t)
