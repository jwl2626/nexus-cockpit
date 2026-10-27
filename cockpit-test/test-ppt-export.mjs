// 验证：页面点「导出 8D 报告」→ 菜单 → 导出 PPT，能否真的产出 pptx
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, readdir, stat, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const ROOT = path.resolve(process.cwd(), "..");
const DL = path.resolve(process.cwd(), "report", "ppt-export");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 8781, CDP = 9337;
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
  async eval(expression) { const r = await this.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true, userGesture: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || "eval err"); return r.result?.value; }
}

const server = createServer(async (req, res) => {
  try { const p = decodeURIComponent(req.url.split("?")[0]);
    const f = path.join(ROOT, p === "/" ? "index.html" : p); const d = await readFile(f);
    res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); res.end(d);
  } catch { res.writeHead(404); res.end("nf"); }
});
await new Promise((r) => server.listen(PORT, "127.0.0.1", r));

const proc = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", `--remote-debugging-port=${CDP}`, `--user-data-dir=${path.join(os.tmpdir(), "ppt-" + Date.now())}`, "about:blank"], { stdio: "ignore" });
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
  if (m.method === "Runtime.exceptionThrown") errs.push(m.params.exceptionDetails?.exception?.description || "ex");
  if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") errs.push(m.params.args.map(a => a.value).join(" ")); });

await rm(DL, { recursive: true, force: true });
await mkdir(DL, { recursive: true });
await cdp.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: DL });
await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/index.html` });
for (let i = 0; i < 80; i++) { await sleep(250);
  const c = await cdp.eval(`document.querySelector('#scanChipText')?.textContent || ''`);
  if (/66\s*行/.test(c)) break; }

console.log("PptxGenJS 载入:", await cdp.eval(`typeof PptxGenJS`));
await cdp.eval(`document.querySelector('#exportBtn').click()`);
await sleep(400);
console.log("菜单项:", await cdp.eval(`Array.from(document.querySelectorAll('#exportMenu [data-export]')).map(b => b.textContent.trim())`));
await cdp.eval(`document.querySelector('#exportMenu [data-export="ppt"]').click()`);

let file = null;
for (let i = 0; i < 90; i++) {
  await sleep(500);
  const files = (await readdir(DL)).filter((f) => f.endsWith(".pptx"));
  if (files.length) { const st = await stat(path.join(DL, files[0])); if (st.size > 50000) { file = files[0]; break; } }
}
console.log("下载:", file ? path.join(DL, file) + "  " + Math.round((await stat(path.join(DL, file))).size / 1024) + " KB" : "失败");
console.log("页面报错:", errs.length ? errs.slice(0, 3) : "无");
ws.close(); proc.kill(); server.close();
process.exit(file ? 0 : 1);
