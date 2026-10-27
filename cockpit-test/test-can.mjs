// 验证周立功 CAN 工具页：连接模拟总成 → 发送报文 → 收到帧
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const ROOT = path.resolve(process.cwd(), "..");
const OUT = path.join(process.cwd(), "report", "shots");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 8786, CDP = 9341;
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

const proc = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", "--window-size=1600,900", `--remote-debugging-port=${CDP}`, `--user-data-dir=${path.join(os.tmpdir(), "can-" + Date.now())}`, "about:blank"], { stdio: "ignore" });
let page;
for (let i = 0; i < 40; i++) { await sleep(250);
  try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
    page = l.find((t) => t.type === "page"); if (page?.webSocketDebuggerUrl) break; } catch {} }

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
const cdp = new C(ws);
await cdp.send("Page.enable"); await cdp.send("Runtime.enable");
await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/can.html` });
await sleep(2500);

await sleep(3000); console.log('未连接时行数:', await cdp.eval(`document.querySelectorAll('#frameBody tr').length`)); console.log("桥接状态:", await cdp.eval(`document.querySelector('#bridgePill').textContent`));
await cdp.eval(`document.querySelector('#devType').value='CANFDNET-400U-TCP'; document.querySelector('#devType').dispatchEvent(new Event('change'));`); await sleep(300); console.log('TCP 端口行可见:', await cdp.eval(`!document.querySelector('#portRow').hidden`), '| 通道数:', await cdp.eval(`document.querySelectorAll('#channel option').length`), '| 端口默认:', await cdp.eval(`document.querySelector('#devPort').value`)); await cdp.eval(`document.querySelector('#btnOpen').click()`);
await sleep(2000);
console.log("总线状态:", await cdp.eval(`document.querySelector('#busPill').textContent`), "| 模式:", await cdp.eval(`document.querySelector('#modePill').textContent`));

await cdp.eval(`document.querySelector('#txId').value='0x18DA0BF1'; document.querySelector('#txData').value='3E00';`);
await cdp.eval(`document.querySelector('#btnSend').click()`);
await sleep(2500);

const rows = await cdp.eval(`document.querySelectorAll('#frameBody tr').length`);
const first = await cdp.eval(`Array.from(document.querySelectorAll('#frameBody tr')).slice(0,3).map(r=>r.innerText.replace(/\\s+/g,' ')).join(' | ')`);
const stats = await cdp.eval(`'RX=' + document.querySelector('#rxCount').textContent + ' TX=' + document.querySelector('#txCount').textContent`);
console.log("行数:", rows, "| 统计:", stats);
console.log("样本:", first.slice(0, 220));

await mkdir(OUT, { recursive: true });
const { data } = await cdp.send("Page.captureScreenshot", { format: "png" });
await writeFile(path.join(OUT, "can-tool.png"), Buffer.from(data, "base64"));
console.log("shot saved");

ws.close(); proc.kill(); server.close();
