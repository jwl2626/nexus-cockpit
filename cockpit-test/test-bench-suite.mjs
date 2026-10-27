// 验证台架页：用例注册 + 老化循环（模拟）
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const ROOT = path.resolve(process.cwd(), "..");
const OUT = path.join(process.cwd(), "report", "shots");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 8788, CDP = 9343;
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
      setTimeout(() => { if (this.p.delete(id)) rej(new Error("timeout " + method)); }, 30000); }); }
  async eval(e) { const r = await this.send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true, userGesture: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description); return r.result?.value; }
}

const server = createServer(async (req, res) => {
  try { const p = decodeURIComponent(req.url.split("?")[0]);
    const f = path.join(ROOT, p === "/" ? "index.html" : p); const d = await readFile(f);
    res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); res.end(d);
  } catch { res.writeHead(404); res.end("nf"); }
});
await new Promise((r) => server.listen(PORT, "127.0.0.1", r));

const proc = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1600,1100", `--remote-debugging-port=${CDP}`, `--user-data-dir=${path.join(os.tmpdir(), "bench2-" + Date.now())}`, "about:blank"], { stdio: "ignore" });
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

await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/bench.html` });
await sleep(2400);
console.log("用例卡片:", await cdp.eval(`document.querySelectorAll('.case').length`));

await cdp.eval(`document.querySelector('#suiteDuration').value='20'; document.querySelector('#btnSuiteStart').click()`);
await sleep(12000);
console.log("用例状态:", await cdp.eval(`['wifi','bt','nearlink','camera_bar'].map(id => document.querySelector('#cstate-'+id).textContent).join(' / ')`));
console.log("进度:", await cdp.eval(`['wifi','camera_bar'].map(id => document.querySelector('#cpct-'+id).textContent).join(' / ')`));
console.log("记录行数:", await cdp.eval(`document.querySelectorAll('#logBody tr').length`));

await mkdir(OUT, { recursive: true });
const { data } = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
await writeFile(path.join(OUT, "bench-suite.png"), Buffer.from(data, "base64"));
console.log("异常:", errs.length ? errs.slice(0, 2) : "无");

ws.close(); proc.kill(); server.close();
