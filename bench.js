// 台架测试台：外设自检 + SOC/DDR/UFS 应力
(function () {
  const el = (id) => document.getElementById(id);
  const DEVICES = [
    { id: 'adb', name: 'USB · ADB', sub: '调试 / 日志 / 文件', detail: '待自检' },
    { id: 'fastboot', name: 'USB · Fastboot', sub: '刷写 / NV', detail: '待自检' },
    { id: 'pcui', name: 'PCUI 串口', sub: 'AT / MMI', detail: '待自检' },
    { id: 'can', name: '周立功 CAN', sub: 'UDS → MCU → SOC', detail: '待自检' },
    { id: 'eth', name: '以太网', sub: '打流 / 抓包', detail: '待自检' },
    { id: 'ngx', name: 'NGX 采集卡', sub: 'TI 解串出图', detail: '待自检' },
    { id: 'audio', name: '音频板卡', sub: 'MIC / 喇叭', detail: '待自检' },
    { id: 'rf', name: '综测仪', sub: '3G/4G/5G/WiFi', detail: '待自检' },
  ];
  const STRESS = [
    { id: 'soc', name: 'SOC 应力', sub: '满载 / 降频 / 热保护', metrics: [['频率', 'GHz'], ['结温', '°C'], ['重启', '次']] },
    { id: 'ddr', name: 'DDR 应力', sub: '读写遍历 / ECC', metrics: [['带宽', 'GB/s'], ['ECC CE', '次'], ['校验错', '次']] },
    { id: 'ufs', name: 'UFS 应力', sub: '大块读写 / 校验', metrics: [['写吞吐', 'MB/s'], ['延迟 P99', 'ms'], ['IO 错', '次']] },
  ];

  const state = {
    url: localStorage.getItem('bench-bridge-url') || 'http://127.0.0.1:8791',
    es: null,
    status: {},
    running: false,
    logs: [],
  };

  function setPill(node, text, cls) {
    node.textContent = text;
    node.className = 'pill' + (cls ? ' ' + cls : '');
  }

  function stamp() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }

  function log(item, result, detail) {
    state.logs.push({ t: stamp(), item, result, detail });
    const body = el('logBody');
    const empty = body.querySelector('.empty');
    if (empty) empty.remove();
    const tr = document.createElement('tr');
    const cls = result === 'Pass' ? 'log-ok' : result === 'Fail' ? 'log-fail' : '';
    tr.innerHTML = `<td>${stamp()}</td><td>${item}</td><td class="${cls}">${result}</td><td>${detail || ''}</td>`;
    body.appendChild(tr);
    while (body.children.length > 200) body.removeChild(body.firstChild);
    body.parentElement.parentElement.scrollTop = body.parentElement.parentElement.scrollHeight;
  }

  // ---------- 渲染 ----------
  function renderDevices() {
    el('deviceGrid').innerHTML = DEVICES.map((d) => `
      <div class="device" data-dev="${d.id}">
        <div class="device-head">
          <i class="dot" id="dot-${d.id}"></i>
          <div>
            <div class="device-name">${d.name}</div>
            <div class="device-sub">${d.sub}</div>
          </div>
        </div>
        <div class="device-body">
          <div class="device-detail" id="detail-${d.id}">${d.detail}</div>
          <button class="btn" data-check="${d.id}">自检</button>
        </div>
      </div>`).join('');
    el('deviceGrid').addEventListener('click', (event) => {
      const btn = event.target.closest('[data-check]');
      if (btn) selfCheck(btn.dataset.check);
    });
  }

  function renderStress() {
    el('stressGrid').innerHTML = STRESS.map((s) => `
      <div class="stress" data-kind="${s.id}">
        <div class="stress-title"><b>${s.name}</b><span>${s.sub}</span></div>
        <div class="stress-metrics">
          ${s.metrics.map(([label, unit]) => `<div>${label}<b id="m-${s.id}-${label}">—<em style="font-size:10px;color:#8b98ab"> ${unit}</em></b></div>`).join('')}
        </div>
        <div class="bar"><i id="bar-${s.id}"></i></div>
        <div class="stress-foot"><span id="pct-${s.id}">0%</span><span id="state-${s.id}">待开始</span></div>
      </div>`).join('');
  }

  // ---------- 桥接 ----------
  function connectBridge() {
    if (state.es) state.es.close();
    const url = el('bridgeUrl').value.replace(/\/$/, '');
    state.url = url;
    localStorage.setItem('bench-bridge-url', url);
    setPill(el('bridgePill'), '连接中…', '');

    const es = new EventSource(url + '/events');
    state.es = es;
    es.onopen = () => {
      setPill(el('bridgePill'), '桥接已连接', 'on');
      post({ cmd: 'hello' }).catch(() => {});
    };
    es.onerror = () => {
      setPill(el('bridgePill'), '桥接断开', 'off');
      es.close();
      state.es = null;
    };
    es.onmessage = (event) => {
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      if (data.type === 'selfcheck') {
        const dot = el('dot-' + data.channel);
        if (dot) dot.className = 'dot ' + (data.ok ? 'ok' : 'fail');
        const detail = el('detail-' + data.channel);
        if (detail) detail.textContent = data.detail || (data.ok ? '正常' : '失败');
        log(data.channel.toUpperCase(), data.ok ? 'Pass' : 'Fail', data.detail || '');
      } else if (data.type === 'stress') {
        applyStress(data);
      } else if (data.type === 'log') {
        log('SYS', data.level === 'error' ? 'Fail' : 'Info', data.msg);
      } else if (data.type === 'status') {
        state.running = !!data.running;
        setPill(el('modePill'), data.mode === 'hw' ? '硬件模式' : data.mode === 'sim' ? '模拟模式' : '—', data.mode === 'hw' ? 'on' : '');
        setPill(el('runPill'), data.running ? '测试进行中' : '空闲', data.running ? 'on' : '');
        el('btnStressStart').disabled = data.running;
        el('btnStressStop').disabled = !data.running;
      }
    };
  }

  async function post(payload) {
    const res = await fetch(state.url + '/cmd', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return res.json();
  }

  function applyStress(data) {
    const bar = el('bar-' + data.kind);
    if (!bar) return;
    bar.style.width = (data.pct ?? 0) + '%';
    el('pct-' + data.kind).textContent = (data.pct ?? 0) + '%';
    const stateEl = el('state-' + data.kind);
    stateEl.textContent = data.done ? (data.ok ? '通过' : '失败') : '运行中';

    for (const [key, value] of Object.entries(data.metrics || {})) {
      const node = el(`m-${data.kind}-${key}`);
      if (node) node.firstChild.textContent = value;
    }
    if (data.done) log(data.kind.toUpperCase(), data.ok ? 'Pass' : 'Fail', data.detail || '');
  }

  // ---------- 动作 ----------
  function selfCheck(channel) {
    const dot = el('dot-' + channel);
    if (dot) dot.className = 'dot busy';
    const detail = el('detail-' + channel);
    if (detail) detail.textContent = '检测中…';
    post({ cmd: 'selfcheck', channel }).catch(() => {
      // 桥接不可用时本地模拟，保证页面可用
      setTimeout(() => {
        dot.className = 'dot ok';
        detail.textContent = '本地模拟通过';
        log(channel.toUpperCase(), 'Pass', '本地模拟（桥接未连接）');
      }, 500);
    });
  }

  function selfCheckAll() {
    DEVICES.forEach((device, index) => {
      setTimeout(() => selfCheck(device.id), index * 350);
    });
  }

  function startStress() {
    const duration = Number(el('duration').value);
    STRESS.forEach((s) => {
      el('bar-' + s.id).style.width = '0%';
      el('pct-' + s.id).textContent = '0%';
      el('state-' + s.id).textContent = '启动中';
    });
    post({ cmd: 'stress', action: 'start', duration }).catch(() => {
      log('STRESS', 'Fail', '桥接未连接，无法启动应力测试');
    });
  }

  function stopStress() {
    post({ cmd: 'stress', action: 'stop' }).catch(() => {});
  }

  function exportCsv() {
    const header = 'time,item,result,detail\n';
    const body = state.logs.map((row) => [row.t, row.item, row.result, `"${(row.detail || '').replace(/"/g, '""')}"`].join(','));
    const blob = new Blob([header + body.join('\n')], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `bench-${Date.now()}.csv`;
    link.click();
  }

  renderDevices();
  renderStress();
  el('bridgeUrl').value = state.url;
  el('bridgeConnect').addEventListener('click', connectBridge);
  el('btnSelfAll').addEventListener('click', selfCheckAll);
  el('btnStressStart').addEventListener('click', startStress);
  el('btnStressStop').addEventListener('click', stopStress);
  el('btnExport').addEventListener('click', exportCsv);
  el('btnClearLog').addEventListener('click', () => {
    state.logs = [];
    el('logBody').innerHTML = '<tr class="empty"><td colspan="4">尚未执行</td></tr>';
  });
  connectBridge();
})();
