# -*- coding: utf-8 -*-
"""重写 monitorSpecPanel（去掉嵌套模板字符串导致的语法错误），并重新挂到详情页。"""

p = "app.js"
t = open(p, encoding="utf-8").read()

start = t.index("  function monitorSpecPanel(target) {")
end = t.index("  const SAMPLE_LOG = `")

new_fn = '''  function monitorSpecPanel(target) {
    const def = MODULE_DEFS.find((item) => item.id === (target && target.id)) || {};
    const rows = (def.cardMetrics || []).filter((metric) => metric.source);
    if (!rows.length) return '';
    const body = rows.map((metric) =>
      '<tr><td class="strong">' + escapeHtml(metric.label) + '</td>'
      + '<td class="mono">' + escapeHtml(metric.source) + '</td>'
      + '<td class="mono">' + escapeHtml(metric.period || '—') + '</td>'
      + '<td>' + escapeHtml(metric.threshold || '—') + '</td>'
      + '<td class="mono">' + (metric.weight == null ? '—' : metric.weight) + '</td></tr>'
    ).join('');
    return panelHTML('监控与诊断方案', 'scan',
      '<div class="table-scroll"><table class="data-table" style="min-width:640px">'
      + '<thead><tr><th>指标</th><th>采集源</th><th>周期</th><th>告警阈值</th><th>权重</th></tr></thead>'
      + '<tbody>' + body + '</tbody></table></div>',
      { span2: true, sub: 'SOURCE / PERIOD / THRESHOLD / WEIGHT' });
  }

'''

t = t[:start] + new_fn + t[end:]

old_ret = "return `${content}${diagnosisPanel(moduleState)}`"
new_ret = "return `${content}${monitorSpecPanel(moduleState)}${diagnosisPanel(moduleState)}`"
if "monitorSpecPanel(moduleState)}${diagnosisPanel" not in t:
    t = t.replace(old_ret, new_ret, 1)

open(p, "w", encoding="utf-8", newline="\n").write(t)
print("rewritten:", "escapeHtml(metric.source)" in t)
print("wired:", "monitorSpecPanel(moduleState)}${diagnosisPanel" in t)
