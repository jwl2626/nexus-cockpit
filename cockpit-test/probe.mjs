// 探针：把页面关键 DOM 结构打印出来，用于修正点击用例的选择器
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const SITE_ROOT = path.resolve(process.cwd(), "..");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 8778;
const CDP_PORT = 9334;
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png" };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.addEventListener("message", (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) {
        const { resolve, reject } = this.pending.get(m.id);
        this.pending.delete(m.id);
        m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
      }
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.pending.delete(id)) reject(new Error("timeout " + method)); }, 30000);
    });
  }
  async eval(expression) {
    const r = await this.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description);
    return r.result?.value;
  }
}

const server = createServer(async (req, res) => {
  try {
    const p = decodeURIComponent(req.url.split("?")[0]);
    const f = path.join(SITE_ROOT, p === "/" ? "index.html" : p);
    const data = await readFile(f);
    res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" });
    res.end(data);
  } catch { res.writeHead(404); res.end("nf"); }
});
await new Promise((r) => server.listen(PORT, "127.0.0.1", r));

const proc = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${path.join(os.tmpdir(), "probe-" + Date.now())}`, "about:blank"], { stdio: "ignore" });
let page;
for (let i = 0; i < 40; i++) {
  await sleep(250);
  try {
    const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json();
    page = list.find((t) => t.type === "page");
    if (page?.webSocketDebuggerUrl) break;
  } catch {}
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
const cdp = new CDP(ws);
await cdp.send("Page.enable");
await cdp.send("Runtime.enable");
await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/index.html` });
await sleep(3000);

console.log("=== nav items ===");
console.log(await cdp.eval(`Array.from(document.querySelectorAll('#moduleNav .nav-item')).map(b => ({
  text: b.textContent.trim().replace(/\\s+/g,' ').slice(0,24),
  dataset: JSON.stringify(b.dataset),
  cls: b.className
}))`));

console.log("\n=== 点击 CDC 第一个模块后的主区文本 ===");
await cdp.eval(`document.querySelector('#domainSwitch [data-domain="cdc"]').click()`);
await sleep(500);
await cdp.eval(`document.querySelectorAll('#moduleNav .nav-item')[1]?.click()`);
await sleep(800);
console.log(await cdp.eval(`document.querySelector('#mainContent').innerText.slice(0, 700)`));

console.log("\n=== 时间轴/筛选相关元素 ===");
console.log(await cdp.eval(`(() => {
  const sel = '[class*="timeline"], [class*="filter"], [class*="chip"], [role="tab"]';
  return Array.from(document.querySelectorAll(sel)).slice(0, 25).map(e => e.tagName + '.' + e.className).filter((v,i,a)=>a.indexOf(v)===i);
})()`));

console.log("\n=== 带 data-* 的按钮 ===");
console.log(await cdp.eval(`Array.from(document.querySelectorAll('button[data-*], button')).slice(0,30).map(b => b.textContent.trim().replace(/\\s+/g,' ').slice(0,18) + ' | ' + JSON.stringify(b.dataset))`));

ws.close(); proc.kill(); server.close();
process.exit(0);
