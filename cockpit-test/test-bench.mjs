// 验证台架页：外设自检 + 应力测试（模拟桥接）
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const ROOT = path.resolve(process.cwd(), "..");
const OUT = path.join(process.cwd(), "report", "shots");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 8787, CDP = 9342;
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

const proc = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1600,1000", `--remote-debugging-port=${CDP}`, `--user-data-dir=${path.join(os.tmpdir(), "bench-" + Date.now())}`, "about:blank"], { stdio: "ignore" });
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
await sleep(2500);
console.log("桥接:", await cdp.eval(`document.querySelector('#bridgePill').textContent`));
console.log("外设卡片:", await cdp.eval(`document.querySelectorAll('.device').length`));

await cdp.eval(`document.querySelector('#btnSelfAll').click()`);
await sleep(4500);
console.log("自检通过数:", await cdp.eval(`document.querySelectorAll('.device .dot.ok').length`), "/", await cdp.eval(`document.querySelectorAll('.device').length`));

await cdp.eval(`document.querySelector('#duration').value = '20'; document.querySelector('#btnStressStart').click()`);
await sleep(6000);
console.log("应力进度:", await cdp.eval(`['soc','ddr','ufs'].map(k => document.querySelector('#pct-'+k).textContent).join(' / ')`));
console.log("SOC 指标:", await cdp.eval(`['频率','结温','重启'].map(l => document.querySelector('#m-soc-'+l).innerText.replace(/\\n/g,'')).join(' | ')`));
console.log("执行记录行数:", await cdp.eval(`document.querySelectorAll('#logBody tr').length`));

await mkdir(OUT, { recursive: true });
const { data } = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
await writeFile(path.join(OUT, "bench.png"), Buffer.from(data, "base64"));
console.log("页面异常:", errs.length ? errs.slice(0, 2) : "无");

ws.close(); proc.kill(); server.close();
