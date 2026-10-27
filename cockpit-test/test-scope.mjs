// 验证「单域诊断 vs 三域联合诊断」的 8D 范围隔离
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, readdir, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const ROOT = path.resolve(process.cwd(), "..");
const DL = path.resolve(process.cwd(), "report", "scope-test");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 8782, CDP = 9338;
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png" };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class C {
  constructor(ws) { this.ws = ws; this.id = 0; this.p = new Map();
    ws.addEventListener("message", (e) => { const m = JSON.parse(e.data);
      if (m.id && this.p.has(m.id)) { const x = this.p.get(m.id); this.p.delete(m.id);
        m.error ? x.rej(new Error(JSON.stringify(m.error))) : x.res(m.result); } }); }
  send(method, params = {}) { const id = ++this.id;
    return new Promise((res, rej) => { this.p.set(id, { res, rej });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.p.delete(id)) rej(new Error("timeout " + method)); }, 40000); }); }
  async eval(expr) { const r = await this.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true, userGesture: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description); return r.result?.value; }
}

const server = createServer(async (req, res) => {
  try { const p = decodeURIComponent(req.url.split("?")[0]);
    const f = path.join(ROOT, p === "/" ? "index.html" : p); const d = await readFile(f);
    res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); res.end(d);
  } catch { res.writeHead(404); res.end("nf"); }
});
await new Promise((r) => server.listen(PORT, "127.0.0.1", r));

const proc = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", `--remote-debugging-port=${CDP}`, `--user-data-dir=${path.join(os.tmpdir(), "scope-" + Date.now())}`, "about:blank"], { stdio: "ignore" });
let page;
for (let i = 0; i < 40; i++) { await sleep(250);
  try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
    page = l.find((t) => t.type === "page"); if (page?.webSocketDebuggerUrl) break; } catch {} }

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
const cdp = new C(ws);
await cdp.send("Page.enable"); await cdp.send("Runtime.enable");
const errs = [];
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data);
  if (m.method === "Runtime.exceptionThrown") errs.push(m.params.exceptionDetails?.exception?.description || "ex"); });

await rm(DL, { recursive: true, force: true });
await mkdir(DL, { recursive: true });
await cdp.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: DL });
await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/index.html` });
for (let i = 0; i < 80; i++) { await sleep(250);
  const c = await cdp.eval(`document.querySelector('#scanChipText')?.textContent || ''`);
  if (/66\s*行/.test(c)) break; }

const domButtons = await cdp.eval(`Array.from(document.querySelectorAll('#domainSwitch .domain-btn')).map(b => b.textContent.replace(/\\s+/g,' ').trim())`);
console.log("侧栏域按钮:", domButtons);

await cdp.eval(`document.querySelector('[data-joint]').click()`);
await sleep(900);
console.log("联合页标题:", await cdp.eval(`document.querySelector('#mainContent h1')?.textContent`));
console.log("联合页副标题:", await cdp.eval(`document.querySelector('#mainContent .page-sub')?.textContent.trim().slice(0,80)`));
console.log("联合页时间轴行数:", await cdp.eval(`document.querySelectorAll('#mainContent tbody tr').length`));

await cdp.eval(`document.querySelector('#exportBtn').click()`);
await sleep(300);
await cdp.eval(`document.querySelector('#exportMenu [data-export="html"]').click()`);
for (let i = 0; i < 40; i++) { await sleep(500); if ((await readdir(DL)).some((f) => f.startsWith("NEXUS"))) break; }

const report = (await readdir(DL)).find((f) => f.startsWith("NEXUS"));
const html = await readFile(path.join(DL, report), "utf8");
console.log("联合导出:", report, "模块卡片:", (html.match(/class="module-card"/g) || []).length, "CDC标记:", (html.match(/>CDC</g) || []).length);

await rm(path.join(DL, report));
await cdp.eval(`document.querySelector('[data-domain="cdc"]').click()`);
await sleep(900);
console.log("切换到:", await cdp.eval(`document.querySelector('#mainContent h1')?.textContent`));
await cdp.eval(`document.querySelector('#exportBtn').click()`);
await sleep(300);
await cdp.eval(`document.querySelector('#exportMenu [data-export="html"]').click()`);
for (let i = 0; i < 40; i++) { await sleep(500); if ((await readdir(DL)).some((f) => f.startsWith("NEXUS"))) break; }
const single = (await readdir(DL)).find((f) => f.startsWith("NEXUS"));
const h2 = await readFile(path.join(DL, single), "utf8");
console.log("单域导出:", single, "模块卡片:", (h2.match(/class="module-card"/g) || []).length,
  "| 报告编号:", (h2.match(/8D-\d{8}-\d{4}-\w+/g) || [])[0]);

console.log("页面异常:", errs.length ? errs.slice(0, 3) : "无");
ws.close(); proc.kill(); server.close();
