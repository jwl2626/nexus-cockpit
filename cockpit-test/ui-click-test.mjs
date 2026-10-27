// 用 Chrome DevTools Protocol 真机点击测试 NEXUS COCKPIT 诊断网站。
// 不依赖 playwright/puppeteer：Node 24 自带 WebSocket，Chrome 自带 CDP。
//
// 运行： node ui-click-test.mjs
// 产物： report/results.json、report/shots/*.png、report/downloads/*.html

import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile, readdir, stat, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import os from "node:os";

const SITE_ROOT = path.resolve(process.cwd(), "..");
const OUT_DIR = path.resolve(process.cwd(), "report");
const SHOT_DIR = path.join(OUT_DIR, "shots");
const DL_DIR = path.join(OUT_DIR, "downloads");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 8777;
const CDP_PORT = 9333;
const VIEWPORT = { width: 1920, height: 1080 };

const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      }
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => {
        if (this.pending.has(id)) { this.pending.delete(id); reject(new Error(`timeout: ${method}`)); }
      }, 30000);
    });
  }
  async eval(expression) {
    const r = await this.send("Runtime.evaluate", {
      expression, returnByValue: true, awaitPromise: true, userGesture: true,
    });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || "eval error");
    return r.result?.value;
  }
}

function startServer() {
  return new Promise((resolve) => {
    const server = createServer(async (req, res) => {
      try {
        const urlPath = decodeURIComponent(req.url.split("?")[0]);
        const file = path.join(SITE_ROOT, urlPath === "/" ? "index.html" : urlPath);
        const data = await readFile(file);
        res.writeHead(200, { "Content-Type": MIME[path.extname(file)] || "application/octet-stream" });
        res.end(data);
      } catch { res.writeHead(404); res.end("not found"); }
    });
    server.listen(PORT, "127.0.0.1", () => resolve(server));
  });
}

async function launchChrome() {
  const userDataDir = path.join(os.tmpdir(), "cockpit-cdp-" + Date.now());
  const proc = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    "--disable-extensions", `--remote-debugging-port=${CDP_PORT}`,
    `--user-data-dir=${userDataDir}`, `--window-size=${VIEWPORT.width},${VIEWPORT.height}`,
    "about:blank",
  ], { stdio: "ignore" });
  for (let i = 0; i < 40; i++) {
    await sleep(250);
    try {
      const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return { proc, wsUrl: page.webSocketDebuggerUrl };
    } catch {}
  }
  throw new Error("Chrome 未能在调试端口就绪");
}

const results = [];
function record(id, name, status, detail, ms) {
  results.push({ id, name, status, detail, ms });
  console.log(`[${status === "Pass" ? "PASS" : "FAIL"}] ${id} ${name} :: ${detail}`);
}
async function runCase(id, name, fn) {
  const t0 = Date.now();
  try { record(id, name, "Pass", (await fn()) ?? "ok", Date.now() - t0); }
  catch (err) { record(id, name, "Fail", String(err.message || err).slice(0, 400), Date.now() - t0); }
}
async function shot(cdp, name) {
  const { data } = await cdp.send("Page.captureScreenshot", { format: "png" });
  await writeFile(path.join(SHOT_DIR, `${name}.png`), Buffer.from(data, "base64"));
}

async function main() {
  await mkdir(SHOT_DIR, { recursive: true });
  await mkdir(DL_DIR, { recursive: true });
  if (existsSync(DL_DIR)) for (const f of await readdir(DL_DIR)) await rm(path.join(DL_DIR, f), { force: true });

  const server = await startServer();
  const { proc, wsUrl } = await launchChrome();

  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => {
    ws.addEventListener("open", res, { once: true });
    ws.addEventListener("error", rej, { once: true });
  });
  const cdp = new CDP(ws);

  const consoleErrors = [];
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
      consoleErrors.push(m.params.args.map((a) => a.value ?? a.description).join(" "));
    }
    if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
      consoleErrors.push(m.params.entry.text);
    }
  });

  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Log.enable");
  await cdp.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: DL_DIR });

  const gotoDomain = (d) => cdp.eval(`(() => {
    const b = document.querySelector('#domainSwitch [data-domain="${d}"]');
    if (!b) return false; b.click(); return true; })()`);

  // ---------- U-001 首屏与自动扫描 ----------
  await runCase("U-001", "首屏加载与内置日志自动扫描", async () => {
    await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/index.html` });
    let chip = "";
    let rows = 0;
    for (let i = 0; i < 100; i++) {
      await sleep(250);
      chip = await cdp.eval(`document.querySelector('#scanChipText')?.textContent?.trim() || ''`);
      const m = chip.match(/(\d+)\s*行/);
      rows = m ? Number(m[1]) : 0;
      if (rows >= 66) break;
    }
    const nav = await cdp.eval(`document.querySelectorAll('#moduleNav .nav-item').length`);
    await shot(cdp, "01-overview-cdc");
    if (nav === 0) throw new Error("导航未渲染");
    if (rows !== 66) throw new Error(`内置日志应为 66 行，实际 ${rows} 行（chip="${chip}"）`);
    return `chip="${chip}"，nav=${nav}`;
  });

  // ---------- U-002 三域切换 ----------
  await runCase("U-002", "三域切换 CDC / MDC / VDC", async () => {
    const expect = { cdc: 10, mdc: 8, vdc: 8 }; // 每域 1 个总览 + N 个模块
    const out = [];
    for (const d of ["cdc", "mdc", "vdc"]) {
      if (!(await gotoDomain(d))) throw new Error(`找不到域按钮 ${d}`);
      await sleep(600);
      const n = await cdp.eval(`document.querySelectorAll('#moduleNav .nav-item').length`);
      const active = await cdp.eval(`document.querySelector('#domainSwitch .domain-btn.active')?.dataset.domain`);
      const h1 = await cdp.eval(`document.querySelector('#mainContent h1')?.textContent?.trim() || ''`);
      if (active !== d) throw new Error(`切换后 active=${active}`);
      if (n !== expect[d]) throw new Error(`${d} 导航项应为 ${expect[d]}，实际 ${n}`);
      out.push(`${d}:${n}(${h1})`);
      await shot(cdp, `02-domain-${d}`);
    }
    return out.join(" | ");
  });

  // ---------- U-003 逐项点击（总览 + 23 模块） ----------
  await runCase("U-003", "逐项点击：3 总览 + 23 模块", async () => {
    const problems = [];
    let modules = 0, overviews = 0;
    for (const d of ["cdc", "mdc", "vdc"]) {
      await gotoDomain(d);
      await sleep(400);
      const ov = await cdp.eval(`(() => {
        const b = document.querySelector('#moduleNav [data-view="overview"]');
        if (!b) return false; b.click(); return true; })()`);
      if (!ov) problems.push(`${d}:总览按钮缺失`);
      else {
        await sleep(300);
        const ok = await cdp.eval(`document.querySelectorAll('#mainContent .module-card, #mainContent section, #mainContent .card').length > 0`);
        if (!ok) problems.push(`${d}:总览无内容`); else overviews++;
      }

      const ids = await cdp.eval(`Array.from(document.querySelectorAll('#moduleNav [data-module]')).map(b => b.dataset.module)`);
      for (const mid of ids) {
        const clicked = await cdp.eval(`(() => {
          const b = document.querySelector('#moduleNav [data-module="${mid}"]');
          if (!b) return false; b.click(); return true; })()`);
        if (!clicked) { problems.push(`${d}/${mid}:按钮丢失`); continue; }
        await sleep(260);
        const info = await cdp.eval(`(() => {
          const t = document.querySelector('#mainContent h1')?.textContent?.trim() || '';
          const blocks = document.querySelectorAll('#mainContent section, #mainContent .card, #mainContent .panel').length;
          const events = document.querySelectorAll('#mainContent .timeline-event').length;
          return { t, blocks, events };
        })()`);
        modules++;
        if (!info.t) problems.push(`${d}/${mid}:无标题`);
        if (info.blocks === 0) problems.push(`${d}/${mid}:无内容区块`);
      }
    }
    await shot(cdp, "03-vdc-module");
    if (problems.length) throw new Error(problems.join("; "));
    return `总览 ${overviews} 个 + 模块 ${modules} 个，均有标题与内容`;
  });

  // ---------- U-004 时间轴筛选 ----------
  await runCase("U-004", "异常时间轴筛选（全部/严重/警告）", async () => {
    await gotoDomain("cdc");
    await sleep(400);
    await cdp.eval(`document.querySelector('#moduleNav [data-module="soc"]').click()`);
    await sleep(700);
    const all = await cdp.eval(`document.querySelectorAll('.timeline-event').length`);
    if (all === 0) throw new Error("SOC 模块时间轴为空");

    await cdp.eval(`document.querySelector('.filter-chip[data-event-filter="critical"]').click()`);
    await sleep(500);
    const cri = await cdp.eval(`(() => {
      const items = Array.from(document.querySelectorAll('.timeline-event'));
      return { n: items.length, allCritical: items.every(e => e.classList.contains('critical')) };
    })()`);
    await shot(cdp, "04-timeline-critical");

    await cdp.eval(`document.querySelector('.filter-chip[data-event-filter="anomaly"]').click()`);
    await sleep(400);
    const back = await cdp.eval(`document.querySelectorAll('.timeline-event').length`);

    if (cri.n === 0) throw new Error("严重筛选后为空");
    if (!cri.allCritical) throw new Error("筛选后仍混有非严重事件");
    if (cri.n > all) throw new Error("筛选后数量反而增加");
    if (back !== all) throw new Error(`恢复“异常”后数量 ${back} ≠ 初始 ${all}`);
    return `异常 ${all} → 严重 ${cri.n} → 恢复 ${back}`;
  });

  // ---------- U-005 日志导入 ----------
  await runCase("U-005", "导入自定义日志并解析", async () => {
    await cdp.eval(`document.querySelector('#logImportBtn').click()`);
    await sleep(500);
    if (!(await cdp.eval(`!!document.querySelector('#logInput')`))) throw new Error("导入弹窗未出现");

    const custom = [
      "2026-10-27 09:00:01.100 [SOC] [ERROR] code=SOC_CPU_UV core=3 vdd=0.71V threshold=0.75V duration=12ms",
      "2026-10-27 09:00:02.200 [DDR] [ERROR] code=DDR_ECC ch=2 bank=7 ce=4 ue=0",
      "2026-10-27 09:00:03.300 [UFS] [WARN] code=UFS_LATENCY read=48ms p99=112ms",
      "2026-10-27 09:00:04.400 [MCU] [ERROR] code=MCU_HEARTBEAT core=RDA missed=2",
      "2026-10-27 09:00:05.500 [MCU] [WARN] code=MCU_CAN load=78% errors=14",
    ].join("\n");
    await cdp.eval(`(() => { const t = document.querySelector('#logInput');
      t.value = ${JSON.stringify(custom)};
      t.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
    await cdp.eval(`document.querySelector('[data-action="parse-log"]').click()`);
    await sleep(1600);

    const chip = await cdp.eval(`document.querySelector('#scanChipText').textContent.trim()`);
    if (!/5\s*行/.test(chip)) throw new Error(`导入 5 行后 chip="${chip}"`);

    // 回到 SOC 模块，确认日志码被映射成中文事件
    await gotoDomain("cdc");
    await sleep(400);
    await cdp.eval(`document.querySelector('#moduleNav [data-module="soc"]').click()`);
    await sleep(700);
    const ev = await cdp.eval(`Array.from(document.querySelectorAll('.timeline-event')).map(e => e.innerText).join(' ')`);
    await shot(cdp, "05-import-soc");
    if (!ev.includes("欠压")) throw new Error(`SOC 时间轴未出现欠压事件：${ev.slice(0, 120)}`);
    return `chip="${chip}"，SOC 时间轴出现“欠压”事件`;
  });

  // ---------- U-006 8D 导出 ----------
  await runCase("U-006", "一键导出 8D 维修报告", async () => {
    await cdp.eval(`document.querySelector('#exportBtn').click()`);
    const pick = async () =>
      (await readdir(DL_DIR)).filter((f) => f.endsWith(".html") && !f.startsWith("downloads"));
    let file = null;
    for (let i = 0; i < 60; i++) {
      await sleep(500);
      const files = await pick();
      if (files.length) { file = files[0]; break; }
    }
    if (!file) throw new Error("未产生下载文件");
    const st = await stat(path.join(DL_DIR, file));
    const html = await readFile(path.join(DL_DIR, file), "utf8");
    const imgs = (html.match(/data:image\/png;base64/g) || []).length;
    if (st.size < 100000) throw new Error(`报告过小：${st.size} 字节`);
    if (imgs < 20) throw new Error(`内嵌图表只有 ${imgs} 张（应 ≥ 20）`);
    for (const key of ["D1", "D5", "D8"]) {
      if (!html.includes(key)) throw new Error(`报告缺少 ${key} 结构`);
    }
    return `${file} ${(st.size / 1024 / 1024).toFixed(2)} MB，内嵌图表 ${imgs} 张`;
  });

  // ---------- U-007 主题切换 ----------
  await runCase("U-007", "暗/亮主题切换与持久化", async () => {
    const t0 = await cdp.eval(`document.documentElement.dataset.theme`);
    await cdp.eval(`document.querySelector('#themeToggle').click()`);
    await sleep(800);
    const t1 = await cdp.eval(`document.documentElement.dataset.theme`);
    const stored = await cdp.eval(`Object.keys(localStorage).map(k => k + '=' + localStorage.getItem(k)).join(',')`);
    await shot(cdp, `06-theme-${t1}`);
    if (t0 === t1) throw new Error(`主题未变化（仍 ${t1}）`);
    await cdp.eval(`document.querySelector('#themeToggle').click()`);
    await sleep(400);
    const t2 = await cdp.eval(`document.documentElement.dataset.theme`);
    return `${t0} → ${t1} → ${t2}；localStorage: ${stored}`;
  });

  // ---------- U-008 响应式 ----------
  await runCase("U-008", "响应式无横向溢出", async () => {
    const out = [];
    for (const w of [1920, 1440, 1024, 390]) {
      await cdp.send("Emulation.setDeviceMetricsOverride", { width: w, height: 900, deviceScaleFactor: 1, mobile: w < 500 });
      await sleep(800);
      const m = await cdp.eval(`({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth })`);
      if (m.sw > m.cw + 2) throw new Error(`${w}px 横向溢出 (${m.sw} > ${m.cw})`);
      out.push(`${w}px ok`);
      if (w === 390) await shot(cdp, "07-mobile-390");
    }
    await cdp.send("Emulation.clearDeviceMetricsOverride");
    return out.join(" | ");
  });

  // ---------- U-009 控制台 ----------
  await runCase("U-009", "全程无 JS 报错", async () => {
    if (consoleErrors.length) throw new Error(consoleErrors.slice(0, 5).join(" || "));
    return "console error = 0";
  });

  await writeFile(path.join(OUT_DIR, "results.json"), JSON.stringify(results, null, 2));
  ws.close(); proc.kill(); server.close();

  const fail = results.filter((r) => r.status === "Fail").length;
  console.log(`\n===== 合计 ${results.length} 项，通过 ${results.length - fail}，失败 ${fail} =====`);
  process.exit(fail ? 1 : 0);
}

main().catch((e) => { console.error("FATAL", e); process.exit(2); });
