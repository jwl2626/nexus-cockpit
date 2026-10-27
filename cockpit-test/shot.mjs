// 截图：给定页面状态，保存 PNG
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const ROOT = path.resolve(process.cwd(), "..");
const OUT = path.resolve(process.cwd(), "report", "shots");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 8784, CDP = 9340;
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

const proc = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", "--force-device-scale-factor=1", `--remote-debugging-port=${CDP}`, `--user-data-dir=${path.join(os.tmpdir(), "s-" + Date.now())}`, "--window-size=1920,1080", "about:blank"], { stdio: "ignore" });
let page;
for (let i = 0; i < 40; i++) { await sleep(250);
  try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
    page = l.find((t) => t.type === "page"); if (page?.webSocketDebuggerUrl) break; } catch {} }

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
const cdp = new C(ws);
await cdp.send("Page.enable"); await cdp.send("Runtime.enable");
await mkdir(OUT, { recursive: true });
await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/index.html` });
for (let i = 0; i < 80; i++) { await sleep(250);
  const c = await cdp.eval(`document.querySelector('#scanChipText')?.textContent || ''`);
  if (/66\s*行/.test(c)) break; }

async function shot(name, prep) {
  if (prep) { await cdp.eval(prep); await sleep(900); }
  const { data } = await cdp.send("Page.captureScreenshot", { format: "png" });
  await writeFile(path.join(OUT, name + ".png"), Buffer.from(data, "base64"));
  console.log("shot", name, await cdp.eval(`document.documentElement.clientWidth + "x" + document.documentElement.clientHeight`));
}

await shot("zoom-overview");
await shot("zoom-module", `document.querySelector('#moduleNav [data-module="soc"]').click()`);
await shot("zoom-joint", `document.querySelector('[data-joint]').click()`);

ws.close(); proc.kill(); server.close();
