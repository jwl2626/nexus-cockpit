// 复现：8D 报告在不同页面状态下导出的差异（每次导出用独立下载目录）
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, readdir, stat, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const SITE_ROOT = path.resolve(process.cwd(), "..");
const BASE = path.resolve(process.cwd(), "report", "export-probe");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 8780, CDP_PORT = 9336;
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png" };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.p = new Map();
    ws.addEventListener("message", (ev) => { const m = JSON.parse(ev.data);
      if (m.id && this.p.has(m.id)) { const { res, rej } = this.p.get(m.id); this.p.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); } }); }
  send(method, params = {}) { const id = ++this.id;
    return new Promise((res, rej) => { this.p.set(id, { res, rej });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.p.delete(id)) rej(new Error("timeout " + method)); }, 40000); }); }
  async eval(expression) { const r = await this.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true, userGesture: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description); return r.result?.value; }
}

const server = createServer(async (req, res) => {
  try { const p = decodeURIComponent(req.url.split("?")[0]);
    const f = path.join(SITE_ROOT, p === "/" ? "index.html" : p); const d = await readFile(f);
    res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); res.end(d);
  } catch { res.writeHead(404); res.end("nf"); }
});
await new Promise((r) => server.listen(PORT, "127.0.0.1", r));

const proc = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${path.join(os.tmpdir(), "exp-" + Date.now())}`, "about:blank"], { stdio: "ignore" });
let page;
for (let i = 0; i < 40; i++) { await sleep(250);
  try { const l = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json();
    page = l.find((t) => t.type === "page"); if (page?.webSocketDebuggerUrl) break; } catch {} }

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
const cdp = new CDP(ws);
await cdp.send("Page.enable"); await cdp.send("Runtime.enable");
const errs = [];
ws.addEventListener("message", (ev) => { const m = JSON.parse(ev.data);
  if (m.method === "Runtime.exceptionThrown") errs.push(m.params.exceptionDetails?.exception?.description || "exception"); });

await rm(BASE, { recursive: true, force: true });
await mkdir(BASE, { recursive: true });

await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/index.html` });
for (let i = 0; i < 80; i++) { await sleep(250);
  const c = await cdp.eval(`document.querySelector('#scanChipText')?.textContent || ''`);
  if (/66\s*行/.test(c)) break; }

async function exportOnce(label, prepare) {
  const dir = path.join(BASE, label.split(" ")[0]);
  await mkdir(dir, { recursive: true });
  await cdp.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: dir });

  if (prepare) { await prepare(); }
  await sleep(1500);
  const t0 = Date.now();
  await cdp.eval(`document.querySelector('#exportBtn').click()`);

  let file = null, lastSize = -1, stable = 0;
  for (let i = 0; i < 80; i++) {
    await sleep(400);
    const files = (await readdir(dir)).filter((f) => !f.endsWith(".crdownload"));
    if (!files.length) continue;
    const st = await stat(path.join(dir, files[0]));
    if (st.size === lastSize) stable++; else { stable = 0; lastSize = st.size; }
    if (stable >= 2) { file = files[0]; break; }
  }
  if (!file) { console.log(`${label.padEnd(30)} => 80s 内未完成下载`); return; }
  const st = await stat(path.join(dir, file));
  const html = await readFile(path.join(dir, file), "utf8");
  const imgs = (html.match(/data:image\/png;base64/g) || []).length;
  const modules = (html.match(/class="module-card/g) || []).length;
  const d8 = (html.match(/D8/g) || []).length;
  console.log(`${label.padEnd(30)} ${(st.size / 1024).toFixed(1).padStart(8)}KB  img=${String(imgs).padStart(2)}  module-card=${String(modules).padStart(2)}  D8命中=${String(d8).padStart(2)}  ${(Date.now() - t0)}ms`);
}

await exportOnce("A-总览页导出");
await exportOnce("B-SOC模块页导出", async () => { await cdp.eval(`document.querySelector('#moduleNav [data-module="soc"]').click()`); });
await exportOnce("C-回总览再导出", async () => { await cdp.eval(`document.querySelector('#moduleNav [data-view="overview"]').click()`); });
await exportOnce("D-连点第二次", async () => { /* 不切页，直接再导一次 */ });
await exportOnce("E-稳定性模块导出", async () => { await cdp.eval(`document.querySelector('#moduleNav [data-module="stability"]').click()`); });

console.log("页面异常:", errs.length ? errs.slice(0, 3) : "无");
ws.close(); proc.kill(); server.close();
process.exit(0);
