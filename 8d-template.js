/* Jinja2-style 8D repair report template.
   Placeholders: {{ path }} / loops: {% for item in items %}...{% endfor %}
   The template is rendered by the small template engine in app.js. */
window.EIGHT_D_TEMPLATE = String.raw`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>8D 维修分析报告 · {{ report.id }}</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: #e9eef6; color: #172033; font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif; line-height: 1.62; }
  .page { width: min(1040px, calc(100% - 32px)); margin: 26px auto; background: #fff; box-shadow: 0 22px 70px rgba(15, 35, 70, .15); }
  .cover { position: relative; overflow: hidden; padding: 36px 42px 30px; color: #fff; background: linear-gradient(130deg, #0b1020 0%, #15213d 58%, #132d35 100%); }
  .cover::after { content: ""; position: absolute; right: -80px; top: -90px; width: 320px; height: 320px; border-radius: 50%; background: radial-gradient(circle, rgba(76, 141, 255, .35), transparent 68%); }
  .brand { position: relative; z-index: 1; font-size: 21px; font-weight: 700; letter-spacing: .2em; }
  .brand span { color: #6ea5ff; }
  .cover h1 { position: relative; z-index: 1; margin: 14px 0 5px; font-size: 31px; letter-spacing: .02em; }
  .cover p { position: relative; z-index: 1; margin: 0; color: #b6c4dc; font-size: 12px; }
  .cover-meta { position: relative; z-index: 1; display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-top: 28px; }
  .cover-id b { display: block; color: #fff; font-family: "Cascadia Mono", Consolas, monospace; font-size: 16px; font-weight: 500; letter-spacing: .03em; }
  .cover-id span { display: block; margin-top: 3px; color: #9eb0cc; font-size: 10px; }
  .demo { display: inline-block; margin-top: 10px; padding: 3px 8px; border: 1px solid rgba(251, 191, 36, .5); border-radius: 4px; color: #fbbf24; font-size: 9px; letter-spacing: .1em; }
  .status-stamp { padding: 9px 13px; border: 1px solid rgba(110, 165, 255, .45); border-radius: 6px; color: #cfe0ff; background: rgba(76, 141, 255, .12); font-size: 10px; text-align: right; }
  .status-stamp b { display: block; color: #fff; font-size: 14px; font-weight: 600; }
  .content { padding: 26px 34px 32px; }
  .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 22px; }
  .summary-card { padding: 12px 13px; border: 1px solid #e1e8f2; border-radius: 7px; background: #f8fafc; }
  .summary-card span { display: block; color: #6b7b93; font-size: 9px; }
  .summary-card b { display: block; margin-top: 3px; color: #13233d; font-family: "Cascadia Mono", Consolas, monospace; font-size: 21px; font-weight: 600; }
  .summary-card b.red { color: #c23d58; }
  .summary-card b.amber { color: #b46d08; }
  .summary-card b.green { color: #0b8a5c; }
  .summary-card small { color: #94a3b8; font-size: 8px; }
  .d-section { margin-top: 22px; padding-top: 16px; border-top: 1px solid #e6edf5; break-inside: avoid; }
  .d-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 9px; }
  .d-mark { display: grid; place-items: center; width: 29px; height: 29px; flex: 0 0 auto; border-radius: 7px; color: #fff; background: #1f4f8f; font-family: "Cascadia Mono", Consolas, monospace; font-size: 11px; font-weight: 600; }
  .d-head h2 { margin: 0; color: #101b2e; font-size: 15px; font-weight: 650; }
  .d-head p { margin: 1px 0 0; color: #7b8ba3; font-size: 9px; }
  .text-block { padding: 11px 13px; border: 1px solid #e3eaf3; border-radius: 6px; color: #44536b; background: #fbfcfe; font-size: 10.5px; line-height: 1.75; }
  .text-block strong { color: #17233a; }
  .team-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .team-card { padding: 10px; border: 1px solid #e3eaf3; border-radius: 6px; background: #fbfcfe; }
  .avatar { display: grid; place-items: center; width: 28px; height: 28px; margin-bottom: 6px; border-radius: 50%; color: #fff; background: #2c5f9e; font-size: 10px; font-weight: 600; }
  .team-card b { display: block; color: #1b2a42; font-size: 10px; font-weight: 600; }
  .team-card span { display: block; color: #7b8ba3; font-size: 8px; }
  .team-card p { margin: 4px 0 0; color: #55647a; font-size: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 9.5px; }
  th { padding: 7px 8px; color: #607089; background: #f3f7fb; text-align: left; font-weight: 500; white-space: nowrap; }
  td { padding: 7px 8px; border-bottom: 1px solid #edf2f7; color: #3d4c62; vertical-align: top; }
  td strong { color: #18263d; }
  .tag { display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 8px; white-space: nowrap; }
  .tag.critical { color: #b52d49; background: #ffe8ed; }
  .tag.warning { color: #9a5b04; background: #fff1da; }
  .tag.info { color: #246b9f; background: #e8f3fc; }
  .tag.green { color: #0b7a52; background: #e4f7ee; }
  .action-list, .why-list { margin: 0; padding: 0; list-style: none; }
  .action-list li { display: flex; gap: 8px; padding: 7px 0; border-bottom: 1px solid #edf2f7; font-size: 10px; color: #3d4c62; }
  .action-list li:last-child { border-bottom: 0; }
  .action-list .idx { display: grid; place-items: center; width: 18px; height: 18px; flex: 0 0 auto; border-radius: 4px; color: #fff; background: #2f629d; font-family: "Cascadia Mono", Consolas, monospace; font-size: 8px; }
  .action-list b { color: #18263d; }
  .action-list small { color: #8997ab; }
  .why-list li { display: grid; grid-template-columns: 45px 1fr; gap: 8px; padding: 7px 0; border-bottom: 1px solid #edf2f7; font-size: 10px; }
  .why-list li:last-child { border-bottom: 0; }
  .why-list b { color: #2f629d; font-family: "Cascadia Mono", Consolas, monospace; font-size: 8px; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .module-card { margin-top: 12px; padding: 13px; border: 1px solid #e2e9f2; border-radius: 7px; break-inside: avoid; }
  .module-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 8px; }
  .module-index { display: grid; place-items: center; width: 26px; height: 26px; flex: 0 0 auto; border-radius: 6px; color: #fff; background: #2c5f9e; font-family: "Cascadia Mono", Consolas, monospace; font-size: 9px; }
  .module-head h3 { margin: 0; color: #14233a; font-size: 12px; }
  .module-head p { margin: 1px 0 0; color: #8391a6; font-size: 8px; }
  .module-score { margin-left: auto; color: #2c5f9e; font-family: "Cascadia Mono", Consolas, monospace; font-size: 20px; font-weight: 600; }
  .module-score small { color: #8b9bb1; font-size: 8px; }
  .module-layout { display: grid; grid-template-columns: 1fr 300px; gap: 12px; }
  .mini-timeline { border-left: 2px solid #dbe7f5; padding-left: 9px; }
  .mini-event { position: relative; padding: 5px 0 6px 8px; border-bottom: 1px dashed #edf2f7; font-size: 9px; }
  .mini-event:last-child { border-bottom: 0; }
  .mini-event::before { content: ""; position: absolute; left: -14px; top: 9px; width: 6px; height: 6px; border: 2px solid #fff; border-radius: 50%; background: #9aa8bb; box-shadow: 0 0 0 1px #cbd8e7; }
  .mini-event.critical::before { background: #d94660; }
  .mini-event.warning::before { background: #d18a12; }
  .mini-event time { color: #8c9bae; font-family: "Cascadia Mono", Consolas, monospace; font-size: 7.5px; }
  .mini-event b { display: block; color: #2a3a52; font-weight: 500; }
  .mini-event p { margin: 1px 0 0; color: #7d8ba0; font-size: 8px; line-height: 1.5; }
  .chart-box { border: 1px solid #e6edf5; border-radius: 5px; overflow: hidden; background: #fbfcfe; }
  .chart-box img { display: block; width: 100%; height: auto; }
  .chart-box figcaption { padding: 4px 6px; border-top: 1px solid #edf2f7; color: #8a98ac; font-size: 7.5px; }
  .appendix { margin-top: 28px; padding-top: 18px; border-top: 2px solid #dbe6f3; }
  .appendix h2 { margin: 0 0 3px; color: #13233d; font-size: 17px; }
  .appendix > p { margin: 0 0 12px; color: #7b8ba3; font-size: 9px; }
  .footer { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-top: 24px; padding: 14px 0 0; border-top: 1px solid #e6edf5; color: #8c9bb0; font-size: 8px; }
  .signature { display: flex; gap: 26px; margin-top: 12px; color: #6c7c91; font-size: 9px; }
  .signature div { min-width: 130px; padding-top: 24px; border-top: 1px solid #b9c7d8; }
  .print-btn { position: fixed; top: 18px; right: 18px; z-index: 10; padding: 9px 14px; border: 1px solid #cbd6e2; border-radius: 6px; color: #33445a; background: #fff; font-size: 11px; cursor: pointer; box-shadow: 0 5px 16px rgba(22, 35, 55, .1); }
  @media (max-width: 760px) {
    .cover { padding: 24px 20px; }
    .content { padding: 20px 18px; }
    .summary, .team-grid { grid-template-columns: 1fr 1fr; }
    .two-col, .module-layout { grid-template-columns: 1fr; }
    .cover-meta { align-items: flex-start; flex-direction: column; }
    .footer { flex-direction: column; }
    .print-btn { display: none; }
  }
  @media print {
    body { background: #fff; }
    .page { width: 100%; margin: 0; box-shadow: none; }
    .print-btn { display: none; }
    .d-section, .module-card { break-inside: avoid; }
  }
  @page { size: A4; margin: 12mm; }
</style>
</head>
<body>
  <button class="print-btn" onclick="window.print()">打印 / 保存 PDF</button>
  <div class="page">
    <header class="cover">
      <div class="brand">NEXUS <span>COCKPIT</span></div>
      <h1>{{ report.title }}</h1>
      <p>{{ report.subtitle }}</p>
      <div class="cover-meta">
        <div class="cover-id">
          <b>{{ report.id }}</b>
          <span>{{ report.date }} · {{ report.software }}</span>
          <span>VIN {{ report.vin }} · {{ report.model }}</span>
          <span class="demo">DEMO DATA · 模拟数据</span>
        </div>
        <div class="status-stamp">
          综合诊断结论
          <b>{{ report.statusLabel }}</b>
          <span>健康度 {{ summary.health }} 分 · {{ summary.modulesAffected }} / {{ summary.moduleCount }} 模块受影响</span>
        </div>
      </div>
    </header>

    <main class="content">
      <div class="summary">
        <div class="summary-card"><span>座舱综合健康度</span><b class="amber">{{ summary.health }}</b><small>0 - 100</small></div>
        <div class="summary-card"><span>异常事件</span><b class="red">{{ summary.anomalies }}</b><small>跨 {{ summary.moduleCount }} 个模块</small></div>
        <div class="summary-card"><span>严重事件</span><b class="red">{{ summary.critical }}</b><small>需优先处置</small></div>
        <div class="summary-card"><span>日志扫描</span><b class="green">{{ summary.logLines }}</b><small>解析命中 {{ summary.totalEvents }} 条</small></div>
      </div>

      <div class="text-block">
        <strong>自动诊断摘要：</strong>{{ report.summary }}
      </div>

      <section class="d-section">
        <div class="d-head"><div class="d-mark">D1</div><div><h2>成立专项小组</h2><p>跨域联合诊断与维修责任矩阵</p></div></div>
        <div class="team-grid">
          {% for member in team %}
          <div class="team-card">
            <div class="avatar">{{ member.initials }}</div>
            <b>{{ member.name }}</b>
            <span>{{ member.role }}</span>
            <p>{{ member.duty }}</p>
          </div>
          {% endfor %}
        </div>
      </section>

      <section class="d-section">
        <div class="d-head"><div class="d-mark">D2</div><div><h2>问题描述</h2><p>日志扫描结果与跨模块异常关联</p></div></div>
        <div class="text-block">{{ d2Narrative }}</div>
        <table style="margin-top:9px">
          <thead><tr><th style="width:65px">时间</th><th style="width:145px">模块</th><th>异常现象</th><th style="width:62px">等级</th></tr></thead>
          <tbody>
            {% for event in topEvents %}
            <tr>
              <td><span style="font-family:'Cascadia Mono',Consolas,monospace;font-size:8px;color:#71829a">{{ event.time }}</span></td>
              <td><strong>{{ event.module }}</strong></td>
              <td>{{ event.title }}<br><span style="color:#7b8ba3;font-size:8px">{{ event.detail }}</span></td>
              <td><span class="tag {{ event.severity }}">{{ event.severityLabel }}</span></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </section>

      <section class="d-section">
        <div class="d-head"><div class="d-mark">D3</div><div><h2>临时遏制措施</h2><p>先恢复可用性，防止异常扩散</p></div></div>
        <ul class="action-list">
          {% for item in containment %}
          <li><span class="idx">{{ item.index }}</span><div><b>{{ item.action }}</b><br><small>{{ item.owner }} · {{ item.due }} · 状态：{{ item.status }}</small></div></li>
          {% endfor %}
        </ul>
      </section>

      <section class="d-section">
        <div class="d-head"><div class="d-mark">D4</div><div><h2>根本原因分析</h2><p>5 Why 与跨模块证据链</p></div></div>
        <div class="two-col">
          <div>
            <ul class="why-list">
              {% for item in rootCauses %}
              <li><b>{{ item.why }}</b><span>{{ item.answer }}</span></li>
              {% endfor %}
            </ul>
          </div>
          <div class="text-block">
            <strong>证据链关联：</strong><br>
            {% for item in correlations %}
            · <strong>{{ item.title }}</strong>：{{ item.detail }}<br>
            {% endfor %}
          </div>
        </div>
      </section>

      <section class="d-section">
        <div class="d-head"><div class="d-mark">D5</div><div><h2>永久纠正措施</h2><p>软件、硬件与标定联合修复</p></div></div>
        <table>
          <thead><tr><th>措施</th><th style="width:96px">责任人</th><th style="width:76px">目标日期</th><th>验证方式</th></tr></thead>
          <tbody>
            {% for item in corrective %}
            <tr><td><strong>{{ item.action }}</strong></td><td>{{ item.owner }}</td><td>{{ item.due }}</td><td>{{ item.validation }}</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </section>

      <section class="d-section">
        <div class="d-head"><div class="d-mark">D6</div><div><h2>实施与验证</h2><p>修复后回归验证矩阵</p></div></div>
        <table>
          <thead><tr><th>验证项</th><th>方法</th><th>通过标准</th><th style="width:64px">结果</th></tr></thead>
          <tbody>
            {% for item in validation %}
            <tr><td><strong>{{ item.item }}</strong></td><td>{{ item.method }}</td><td>{{ item.criteria }}</td><td><span class="tag {{ item.resultClass }}">{{ item.result }}</span></td></tr>
            {% endfor %}
          </tbody>
        </table>
      </section>

      <section class="d-section">
        <div class="d-head"><div class="d-mark">D7</div><div><h2>预防再发生</h2><p>监控规则、门限与组织机制</p></div></div>
        <ul class="action-list">
          {% for item in prevention %}
          <li><span class="idx">{{ item.index }}</span><div><b>{{ item.item }}</b><br><small>{{ item.owner }} · {{ item.detail }}</small></div></li>
          {% endfor %}
        </ul>
      </section>

      <section class="d-section">
        <div class="d-head"><div class="d-mark">D8</div><div><h2>小组认可与关闭</h2><p>最终结论与签核</p></div></div>
        <div class="text-block">
          {{ d8Narrative }}
          <div class="signature">
            <div>诊断负责人 / {{ report.date }}</div>
            <div>质量负责人 / {{ report.date }}</div>
            <div>维修负责人 / {{ report.date }}</div>
          </div>
        </div>
      </section>

      <section class="appendix">
        <h2>附件 A · {{ report.appendix }}</h2>
        <p>按日志解析顺序汇总全部诊断模块，包含严重 / 警告 / 提示三级事件。</p>
        {% for module in modules %}
        <article class="module-card">
          <div class="module-head">
            <div class="module-index">{{ module.index }}</div>
            <div><h3><span class="tag info">{{ module.domainCode }}</span> {{ module.name }}</h3><p>{{ module.subtitle }}</p></div>
            <div class="module-score">{{ module.health }}<small> / 100</small></div>
          </div>
          <div class="module-layout">
            <div class="mini-timeline">
              {% for event in module.events %}
              <div class="mini-event {{ event.severity }}">
                <time>{{ event.time }}</time>
                <b>{{ event.title }}</b>
                <p>{{ event.detail }}</p>
              </div>
              {% endfor %}
            </div>
            <figure class="chart-box">
              <img src="{{ module.chart }}" alt="{{ module.name }} 实时监控图">
              <figcaption>实时监控快照 · {{ module.chartCaption }}</figcaption>
            </figure>
          </div>
        </article>
        {% endfor %}
      </section>

      <footer class="footer">
        <span>NEXUS COCKPIT · 智能座舱诊断工作台 · {{ report.software }} · Jinja2-style 8D Template</span>
        <span>本报告由日志解析器与 8D 模板自动生成，演示数据不作为真实维修依据。</span>
      </footer>
    </main>
  </div>
</body>
</html>`;
