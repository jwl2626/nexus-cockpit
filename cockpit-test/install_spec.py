# -*- coding: utf-8 -*-
p = "app.js"
t = open(p, encoding="utf-8").read()
block = open("cockpit-test/metric_spec_block.txt", encoding="utf-8").read()

start = t.index("  const METRIC_SPEC = {")
anchor = t.index("CDC_MODULES.forEach((module) => {\n    const spec = METRIC_SPEC")
end = t.index("  });", anchor) + len("  });")
t = t[:start] + block.rstrip() + t[end:]

old_ret = "return `${content}${diagnosisPanel(moduleState)}`"
new_ret = "return `${content}${monitorSpecPanel(module)}${diagnosisPanel(moduleState)}`"
if "monitorSpecPanel(module)}${diagnosisPanel" not in t:
    t = t.replace(old_ret, new_ret, 1)

open(p, "w", encoding="utf-8", newline="\n").write(t)
print("has panel fn:", "function monitorSpecPanel" in t)
print("panel wired:", "monitorSpecPanel(module)}${diagnosisPanel" in t)
print("spec tuples:", t.count("'5s', 20"))
