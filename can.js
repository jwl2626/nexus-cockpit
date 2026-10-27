// 周立功 CAN 工具页面逻辑：SSE 收帧 + POST 发命令 + 本地演示模式兜底
(function () {
  const el = (id) => document.getElementById(id);
  const state = {
    url: localStorage.getItem('zlg-bridge-url') || 'http://127.0.0.1:8790',
    es: null,
    connected: false,
    paused: false,
    frames: [],
    rx: 0,
    tx: 0,
    rateRx: 0,
    periodTimer: null,
    demo: false,
  };

  const MAX_ROWS = 500;

  function setPill(node, text, cls) {
    node.textContent = text;
    node.className = 'pill' + (cls ? ' ' + cls : '');
  }

  function now() {
    const d = new Date();
    return d.toTimeString().slice(0, 8) + '.' + String(d.getMilliseconds()).padStart(3, '0');
  }

  function stamp(t) {
    const d = typeof t === 'number' ? new Date(t * 1000) : new Date();
    const p = (n, w = 2) => String(n).padStart(w, '0');
    return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`;
  }

  function rowOf(frame) {
    const tr = document.createElement('tr');
    const dirCls = frame.dir === 'rx' ? 'dir-rx' : 'dir-tx';
    const time = frame.timeLabel || (typeof frame.t === 'number' ? stamp(frame.t) : now());
    tr.innerHTML = `
      <td>${time}</td>
      <td class="${dirCls}">${frame.dir === 'rx' ? 'RX' : 'TX'}</td>
      <td>${frame.ch ?? 0}</td>
      <td>${frame.id}</td>
      <td>${frame.ext ? '扩展' : '标准'}${frame.fd ? ' · FD' : ''}</td>
      <td>${frame.dlc ?? (frame.data ? frame.data.length / 2 : 0)}</td>
      <td class="data">${frame.data || ''}</td>`;
    return tr;
  }

  function matchesFilter(frame) {
    const q = (el('filter').value || '').trim().toLowerCase();
    if (!q) return true;
    return String(frame.id).toLowerCase().includes(q) || String(frame.data || '').toLowerCase().includes(q);
  }

  function appendFrame(frame) {
    state.frames.push(frame);
    if (state.frames.length > MAX_ROWS) state.frames.shift();
    if (frame.dir === 'rx') state.rx += 1; else state.tx += 1;
    el('rxCount').textContent = state.rx;
    el('txCount').textContent = state.tx;
    el('lastFrame').textContent = frame.id + ' ' + (frame.data || '');
    if (state.paused || !matchesFilter(frame)) return;

    const body = el('frameBody');
    const empty = body.querySelector('.empty');
    if (empty) empty.remove();
    body.appendChild(rowOf(frame));
    while (body.children.length > MAX_ROWS) body.removeChild(body.firstChild);
    body.parentElement.parentElement.scrollTop = body.parentElement.parentElement.scrollHeight;
  }

  function connectBridge() {
    if (state.es) { state.es.close(); state.es = null; }
    const url = el('bridgeUrl').value.replace(/\/$/, '');
    state.url = url;
    localStorage.setItem('zlg-bridge-url', url);
    setPill(el('bridgePill'), '连接中…', '');

    const es = new EventSource(url + '/events');
    state.es = es;
    es.onopen = () => setPill(el('bridgePill'), '桥接已连接', 'on');
    es.onerror = () => {
      setPill(el('bridgePill'), '桥接断开', 'off');
      es.close();
      state.es = null;
    };
    es.onmessage = (event) => {
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      if (data.type === 'frame') appendFrame(data);
      else if (data.type === 'status') {
        state.connected = !!data.connected;
        setPill(el('busPill'), state.connected ? '总线已连接' : '总线空闲', state.connected ? 'on' : '');
        setPill(el('modePill'), data.mode === 'hw' ? '硬件模式' : data.mode === 'sim' ? '模拟模式' : '—', data.mode === 'hw' ? 'on' : '');
        el('btnOpen').disabled = state.connected;
        el('btnClose').disabled = !state.connected;
        el('btnSend').disabled = !state.connected;
      } else if (data.type === 'log') {
        appendFrame({ t: now(), dir: 'rx', ch: '—', id: 'INFO', data: data.msg, ext: false, fd: false, dlc: 0 });
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

  function openDevice() {
    const type = el('devType').value;
    const cfg = {
      type,
      ip: el('devIp').value,
      channel: Number(el('channel').value),
      nominal: Number(el('nominal').value),
      data: Number(el('dataRate').value),
      fd: el('fdMode').checked,
    };
    post({ cmd: 'open', device: cfg }).catch(showBridgeError);
  }

  function sendFrame() {
    const frame = {
      id: el('txId').value.trim(),
      data: el('txData').value.replace(/\s+/g, '').toUpperCase(),
      ext: el('txExt').checked,
      fd: el('fdMode').checked,
    };
    post({ cmd: 'send', frames: [frame] }).catch(showBridgeError);
  }

  function startPeriodic() {
    stopPeriodic();
    const period = Number(el('txPeriod').value);
    if (!period || period < 10) return;
    state.periodTimer = setInterval(sendFrame, period);
  }

  function stopPeriodic() {
    if (state.periodTimer) clearInterval(state.periodTimer);
    state.periodTimer = null;
  }

  function exportCsv() {
    const header = 'time,direction,channel,id,type,dlc,data\n';
    const lines = state.frames.map((f) =>
      [f.t, f.dir, f.ch ?? 0, f.id, f.ext ? 'ext' : 'std', f.dlc ?? (f.data || '').length / 2, f.data].join(',')
    );
    const blob = new Blob([header + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `can-log-${Date.now()}.csv`;
    link.click();
  }

  function showBridgeError() {
    setPill(el('bridgePill'), '桥接未启动', 'off');
    appendFrame({ t: now(), dir: 'rx', ch: '—', id: 'ERR', data: '无法连接桥接服务，请先运行 bridge.py', ext: false, fd: false, dlc: 0 });
  }

  function bind() {
    el('bridgeUrl').value = state.url;
    el('bridgeConnect').addEventListener('click', connectBridge);
    el('btnOpen').addEventListener('click', openDevice);
    el('btnClose').addEventListener('click', () => post({ cmd: 'close' }).catch(showBridgeError));
    el('btnSend').addEventListener('click', () => {
      sendFrame();
      startPeriodic();
    });
    el('txPeriod').addEventListener('change', stopPeriodic);
    el('filter').addEventListener('input', () => {
      const body = el('frameBody');
      body.innerHTML = '';
      const list = state.frames.filter(matchesFilter).slice(-MAX_ROWS);
      if (!list.length) {
        body.innerHTML = '<tr class="empty"><td colspan="7">无匹配报文</td></tr>';
        return;
      }
      list.forEach((f) => body.appendChild(rowOf(f)));
    });
    el('btnPause').addEventListener('click', (e) => {
      state.paused = !state.paused;
      e.target.textContent = state.paused ? '继续' : '暂停';
    });
    el('btnClear').addEventListener('click', () => {
      state.frames = [];
      state.rx = 0;
      state.tx = 0;
      el('rxCount').textContent = '0';
      el('txCount').textContent = '0';
      el('lastFrame').textContent = '—';
      el('frameBody').innerHTML = '<tr class="empty"><td colspan="7">尚未收到报文</td></tr>';
    });
    el('btnExport').addEventListener('click', exportCsv);
    el('devType').addEventListener('change', () => {
      el('ipRow').hidden = el('devType').value !== 'CANFDNET-400U-TCP';
    });
    document.querySelectorAll('.btn.quick').forEach((btn) => {
      btn.addEventListener('click', () => {
        el('txId').value = btn.dataset.id;
        el('txData').value = btn.dataset.data;
        el('txExt').checked = true;
      });
    });
  }

  setInterval(() => {
    el('rateCount').textContent = state.rateRx;
    state.rateRx = 0;
  }, 1000);

  bind();
  connectBridge();
})();
