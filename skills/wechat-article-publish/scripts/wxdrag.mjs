// 公众号「合集编辑页」文章拖拽排序 —— CDP 真实鼠标事件驱动
//
// 背景：合集默认「正序」= 按发表时间从早到晚。补发的老文章（比如批量发表时失败、
//       第二天才补发成功的那几篇）会掉到合集最末，必须手动拖回原位。
//
// 用法：
//   CDP_MATCH="action=edit" node wxdrag.mjs --from "源标题关键词" --to "目标标题关键词" \
//       --mode before|after [--scroll 800]
//
//   --mode 是「落点在目标的哪半区」，但**语义与直觉相反**（2026-10-09 实测）：
//     落点上半区（before）→ 源项插到目标的**后面**
//     落点下半区（after） → 源项插到目标的**前面**
//
// 必须遵守（否则拖不动，只看得到文字被选中）：
//   1. 起手必须按在**行尾的拖拽手柄** `.album__list-action-move` 上（x≈1199），
//      按在行中央只会选中文本。脚本已自动取手柄中心。
//   2. 先 `Page.bringToFront`，否则 Input 域鼠标事件被丢弃/挂起。
//   3. 源项别停在视口底部 100px 内，也别压在右下「问题反馈」悬浮球上——
//      改 --scroll 把源项挪到视口中间。
//   4. **合成 DOM 事件（isTrusted=false）无效**，库不接收；鼠标事件和 pointer 事件都白试。
//   5. 拖完顺序只在前端生效，**必须再点编辑页底部的「发布」按钮**才写回服务器。
//
// 改简介同理：textarea.weui-desktop-form__textarea，用原生 value setter + dispatch input，
// 然后点 `button.weui-desktop-btn_primary`（文案是「发布」）。成功后页面自动跳回合集列表。
const PORT = process.env.CDP_PORT || 9222;
const BASE = `http://127.0.0.1:${PORT}`;

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf("--" + k); return i >= 0 ? args[i + 1] : d; };
const FROM = opt("from");
const TO = opt("to");
const MODE = opt("mode", "before");
const SCROLL = parseInt(opt("scroll", "800"), 10);
if (!FROM || !TO) { console.error("需要 --from 和 --to"); process.exit(1); }

const log = (...a) => { console.error("[drag]", ...a); };
const match = process.env.CDP_MATCH || "action=edit";
log("连接 CDP", BASE);
const list = await (await fetch(BASE + "/json/list")).json();
const target = list.find((t) => t.type === "page" && t.url.includes(match));
if (!target) { console.error("未找到匹配页面:", match); process.exit(1); }

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", rej); });
log("WebSocket 已连接");
let seq = 0; const pending = new Map();
ws.addEventListener("message", (ev) => {
  let m; try { m = JSON.parse(ev.data); } catch { return; }
  if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result); }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++seq;
  const timer = setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error("timeout: " + method)); } }, 15000);
  pending.set(id, { resolve: (v) => { clearTimeout(timer); resolve(v); }, reject: (e) => { clearTimeout(timer); reject(e); } });
  ws.send(JSON.stringify({ id, method, params }));
});
const evalJs = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 400));
  return r.result.value;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 关键：把目标页面推到最前并激活，否则 Input 域的鼠标事件会被丢弃/挂起
await send("Page.bringToFront");
log("Page.bringToFront 完成");

const PROBE = (fromKw, toKw) => `(()=>{
  const items=[...document.querySelectorAll("div.weui-desktop-drag-list__item.album__list-item")];
  const info=items.map((it,i)=>{
    const r=it.getBoundingClientRect();
    const tx=(it.querySelector(".album__list-item-title-text")||{}).innerText||"";
    const hd=it.querySelector(".album__list-action-move");
    const hr=hd?hd.getBoundingClientRect():null;
    return {i,t:tx.replace(/\\s+/g," ").trim(),top:Math.round(r.top),bottom:Math.round(r.bottom),x:Math.round(r.left+r.width/2),cy:Math.round(r.top+r.height/2),
      hx:hr?Math.round(hr.left+hr.width/2):null,hy:hr?Math.round(hr.top+hr.height/2):null};
  });
  const src=info.find(o=>o.t.includes(${JSON.stringify(fromKw)}));
  const dst=info.find(o=>o.t.includes(${JSON.stringify(toKw)}));
  return JSON.stringify({vh:innerHeight,count:info.length,src,dst,titles:info.map(o=>o.t.slice(0,24))});
})()`;

// 1) 滚动到源/目标都可见的位置
log("滚动到", SCROLL);
await evalJs(`window.scrollTo(0, ${SCROLL}); 'ok'`);
await sleep(700);
log("探查列表");

let p = JSON.parse(await evalJs(PROBE(FROM, TO)));
if (!p.src || !p.dst) { console.error("找不到源/目标项", JSON.stringify(p, null, 1)); process.exit(1); }
console.log("源:", p.src.i, p.src.t, "y=", p.src.cy);
console.log("目标:", p.dst.i, p.dst.t, "y=", p.dst.cy);

const sx = p.src.hx ?? p.src.x, sy = p.src.hy ?? p.src.cy;
// 落在目标元素上/下半区，决定插前还是插后
const ty = MODE === "before"
  ? Math.round(p.dst.top + (p.dst.bottom - p.dst.top) * 0.22)
  : Math.round(p.dst.top + (p.dst.bottom - p.dst.top) * 0.78);
const tx = p.dst.x;

const mouse = (type, x, y, extra = {}) =>
  send("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: type === "mouseReleased" ? 0 : 1, ...extra });

// 2) 起手：移到源，按下，轻推一点触发拖拽阈值
await mouse("mouseMoved", sx, sy, { buttons: 0 });
await sleep(120);
await mouse("mousePressed", sx, sy, { clickCount: 1 });
await sleep(120);
await mouse("mouseMoved", sx, sy - 4);

// 3) 平滑移动到目标（分步，避免被识别成瞬移）
const STEPS = 22;
for (let k = 1; k <= STEPS; k++) {
  const t = k / STEPS;
  const ease = t * t * (3 - 2 * t);           // smoothstep，收尾更慢
  const x = Math.round(sx + (tx - sx) * ease);
  const y = Math.round(sy + (ty - sy) * ease);
  await mouse("mouseMoved", x, y);
  await sleep(18);
}
await sleep(150);
await mouse("mouseMoved", tx, ty);
await sleep(250);
await mouse("mouseReleased", tx, ty, { clickCount: 1 });
await sleep(600);

// 4) 验证
const after = JSON.parse(await evalJs(PROBE(FROM, TO)));
const fromIdx = after.titles.findIndex((t) => t.includes(FROM.slice(0, 8)) || t.includes(FROM));
console.log("拖拽后新顺序：");
after.titles.forEach((t, i) => console.log(`  ${String(i).padStart(2)}  ${t}`));
console.log(`源项现在位于第 ${after.src ? after.src.i : "?"} 位`);
ws.close();
