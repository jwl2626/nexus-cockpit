// 全矩阵验证：每个域 + 联合，各自导出的 8D 模块数
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, readdir, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const ROOT = path.resolve(process.cwd(), "..");
const DL = path.resolve(process.cwd(), "report", "scope-matrix");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 8783, CDP = 9339;
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

const proc = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", `--remote-debugging-port=${CDP}`, `--user-data-dir=${path.join(os.tmpdir(), "m-" + Date.now())}`, "about:blank"], { stdio: "ignore" });
let page;
for (let i = 0; i < 40; i++) { await sleep(250);
  try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
    page = l.find((t) => t.type === "page"); if (page?.webSocketDebuggerUrl) break; } catch {} }

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
const cdp = new C(ws);
await cdp.send("Page.enable"); await cdp.send("Runtime.enable");

await rm(DL, { recursive: true, force: true });
await mkdir(DL, { recursive: true });
await cdp.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: DL });
await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/index.html` });
for (let i = 0; i < 80; i++) { await sleep(250);
  const c = await cdp.eval(`document.querySelector('#scanChipText')?.textContent || ''`);
  if (/66\s*行/.test(c)) break; }

console.log("build:", await cdp.eval(`document.querySelector('script[src*="app.js"]')?.getAttribute('src')`));

async function exportFrom(label, clickExpr) {
  await cdp.eval(clickExpr);
  await sleep(900);
  const title = await cdp.eval(`document.querySelector('#mainContent h1')?.textContent?.trim()`);
  await cdp.eval(`document.querySelector('#exportBtn').click()`);
  await sleep(250);
  await cdp.eval(`document.querySelector('#exportMenu [data-export="html"]').click()`);
  for (let i = 0; i < 40; i++) { await sleep(400); if ((await readdir(DL)).length) break; }
  const [file] = await readdir(DL);
  const html = await readFile(path.join(DL, file), "utf8");
  const cards = (html.match(/class="module-card"/g) || []).length;
  const id = (html.match(/8D-\d{8}-\d{4}(-\w+)?/g) || [])[0];
  const domains = ["CDC","MDC","VDC"].filter((d) => html.includes(`>${d}</span>`)); const h1 = (html.match(/<h1>(.*?)<\/h1>/)||[])[1]||""; const mdc=(html.match(/MDC/g)||[]).length; const vdc=(html.match(/VDC/g)||[]).length;
  if (label === "CDC") { let i = -1, n = 0; while ((i = html.indexOf("MDC", i + 1)) >= 0 && n < 4) { console.log("   ..." + html.slice(i - 60, i + 40).replace(/\s+/g, " ")); n++; } } console.log(`${label.padEnd(12)} 页面="${title}"  模块=${cards}  编号=${id}  含域=${domains.join("/")}  标题="${h1}"  MDC提及=${mdc} VDC提及=${vdc}`);
  await rm(path.join(DL, file));
}

await exportFrom("CDC", `document.querySelector('[data-domain="cdc"]').click()`);
await exportFrom("MDC", `document.querySelector('[data-domain="mdc"]').click()`);
await exportFrom("VDC", `document.querySelector('[data-domain="vdc"]').click()`);
await exportFrom("联合", `document.querySelector('[data-joint]').click()`);

ws.close(); proc.kill(); server.close();
