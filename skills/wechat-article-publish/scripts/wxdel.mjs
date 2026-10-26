// 公众号草稿箱——批量删除草稿（后台 UI 驱动，零依赖）
// 用法: WX_TOKEN=xxx node wxdel.mjs <file_id,file_id,...>
//      加 DRY=1 只定位不点，用于验证选择器
// 说明: 草稿卡片的删除入口是 hover 后出现的垃圾桶图标（无文字，是 SVG），
//       点它弹出 .weui-desktop-popover 确认框，再点里面的「删除」才真正删除。
//       确认框原文：「确定删除？删除该内容不会删除已发表的内容」——删草稿不影响线上。
import fs from "node:fs";

const PORT = Number(process.env.CDP_PORT || 9222);
const BASE = `http://127.0.0.1:${PORT}`;
const TOKEN = process.env.WX_TOKEN || "978829597";
const LIST_URL = `https://mp.weixin.qq.com/cgi-bin/appmsg?begin=0&count=50&type=77&action=list_card&token=${TOKEN}&lang=zh_CN`;
const DRY = process.env.DRY === "1";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(...a);

const listTargets = async () => (await fetch(`${BASE}/json/list`)).json();

function makeClient(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let seq = 0;
  const pending = new Map();
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", () => res());
    ws.addEventListener("error", () => rej(new Error("ws connect failed")));
  });
  ws.addEventListener("message", (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id);
      pending.delete(m.id);
      m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
    }
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++seq;
    const timer = setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error("timeout: " + method)); } }, 30000);
    timer.unref?.();
    pending.set(id, { resolve: (v) => { clearTimeout(timer); resolve(v); }, reject: (e) => { clearTimeout(timer); reject(e); } });
    ws.send(JSON.stringify({ id, method, params }));
  });
  return { send, ready, close: () => ws.close() };
}

async function withPage(match, fn) {
  const ts = await listTargets();
  const page = ts.find((t) => t.type === "page" && t.url.includes(match));
  if (!page) throw new Error("没有匹配的页面: " + match);
  const c = makeClient(page.webSocketDebuggerUrl);
  await c.ready;
  await c.send("Runtime.enable").catch(() => {});
  try { return await fn(c); } finally { c.close(); }
}

async function js(c, expr) {
  const r = await c.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true, userGesture: true });
  if (r.exceptionDetails) throw new Error("页面内异常: " + (r.exceptionDetails.exception?.description || "").slice(0, 180));
  return r.result?.value;
}

const VISF = `const _vis=(e)=>{if(!e)return false;const r=e.getBoundingClientRect();return r.width>0&&r.height>0;};`;

async function dispatchAt(c, x, y, settle) {
  const m = (type, extra = {}) => c.send("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 1, ...extra });
  await m("mouseMoved", { buttons: 0 });
  await sleep(60);
  await m("mousePressed", { buttons: 1 });
  await sleep(70);
  await m("mouseReleased", { buttons: 0 });
  await sleep(settle);
}

async function waitFor(fn, timeout, step, label) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) { if (await fn()) return true; await sleep(step); }
  throw new Error("等待超时: " + label);
}

// 卡片内「删除」那个 popover 包 wrapper：靠 tooltip 文字定位，别按顺序取（编辑/删除顺序可能变）
const DEL_WRP_EXPR = (idx) => `(()=>{
  const cards=[...document.querySelectorAll('.weui-desktop-card__inner')];
  const card=cards[${idx}]; if(!card) return null;
  const bar=card.querySelector('.weui-desktop-publish__opr'); if(!bar) return null;
  const wrps=[...bar.querySelectorAll('.weui-desktop-popover__wrp')];
  return wrps.findIndex(w=>{const t=w.querySelector('.weui-desktop-tooltip');return t&&(t.innerText||'').trim()==='删除';});
})()`;

async function cardIndexOf(c, fileId) {
  return await js(c, `(()=>{
    const cards=[...document.querySelectorAll('.weui-desktop-card__inner')];
    const pick=(el)=>{let n=el,d=0;while(n&&d<8){if(n.__vue__)return n.__vue__;n=n.parentElement;d++;}return null;};
    for(let i=0;i<cards.length;i++){
      const vm=pick(cards[i]);const it=vm&&(vm.$data.list||[])[0];
      if(it && String(it.file_id)===${JSON.stringify(fileId)}) return {i,title:it.title};
    }
    return null;})()`);
}

async function loadList(c) {
  await c.send("Page.enable").catch(() => {});
  await c.send("Page.bringToFront").catch(() => {});
  await c.send("Page.navigate", { url: LIST_URL });
  await sleep(1500);
  await c.send("Page.bringToFront").catch(() => {});
  await waitFor(async () => (await js(c, `document.querySelectorAll('.weui-desktop-card__inner').length`)) >= 1, 25000, 600, "列表加载");
  await waitFor(async () => (await js(c, `document.visibilityState`)) === "visible", 8000, 300, "标签可见");
}

async function deleteOne(c, fileId) {
  const found = await cardIndexOf(c, fileId);
  if (!found) return { ok: true, skipped: true, reason: "草稿箱里已无此稿" };

  // 悬停卡片让操作栏出现（别 scrollIntoView 后再测，会丢 hover —— 顺序：先滚动、再悬停、再测）
  const box = await js(c, `(()=>{
    const card=document.querySelectorAll('.weui-desktop-card__inner')[${found.i}];
    card.scrollIntoView({block:"center"});
    const r=card.getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+Math.min(70,r.height/2)};
  })()`);
  await c.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: box.x, y: box.y, buttons: 0 });
  await sleep(600);

  const wrpIdx = await js(c, DEL_WRP_EXPR(found.i));
  if (wrpIdx == null || wrpIdx < 0) throw new Error("卡片里找不到「删除」入口");

  const iconPos = await js(c, `(()=>{${VISF}
    const card=document.querySelectorAll('.weui-desktop-card__inner')[${found.i}];
    const bar=card.querySelector('.weui-desktop-publish__opr');
    const wrp=[...bar.querySelectorAll('.weui-desktop-popover__wrp')][${wrpIdx}];
    const a=wrp.querySelector('a.weui-desktop-icon-btn');
    if(!a) return null;
    const r=a.getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+r.height/2,w:Math.round(r.width),h:Math.round(r.height)};
  })()`);
  if (!iconPos || !iconPos.w) throw new Error("删除图标不可见（hover 没生效？）");

  if (DRY) return { ok: true, dry: true, title: found.title, wrpIdx, iconPos };

  await dispatchAt(c, iconPos.x, iconPos.y, 900);

  // 确认浮层里的「删除」= button.weui-desktop-btn_primary（取消 = btn_default）
  const btn = await js(c, `(()=>{${VISF}
    const card=document.querySelectorAll('.weui-desktop-card__inner')[${found.i}];
    const bar=card.querySelector('.weui-desktop-publish__opr');
    const wrp=[...bar.querySelectorAll('.weui-desktop-popover__wrp')][${wrpIdx}];
    const pop=wrp.querySelector('.weui-desktop-popover');
    if(!pop) return null;
    const b=pop.querySelector('button.weui-desktop-btn_primary');
    if(!_vis(b)) return null;
    const r=b.getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+r.height/2,txt:(b.innerText||'').trim(),wording:(pop.querySelector('.comfirm_delete_wording')||{}).innerText||''};
  })()`);
  if (!btn) throw new Error("确认浮层没出现");
  await dispatchAt(c, btn.x, btn.y, 1800);

  const gone = await waitFor(async () => !(await cardIndexOf(c, fileId)), 15000, 700, "卡片消失").catch(() => false);
  if (!gone) throw new Error("点了删除但卡片还在");
  return { ok: true, title: found.title, wording: (btn.wording || "").trim() };
}

async function main() {
  const ids = (process.argv[2] || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (!ids.length) { log("用法: WX_TOKEN=xx node wxdel.mjs <file_id,...>  [DRY=1 只定位]"); return; }
  const results = [];
  await withPage("action=list_card", async (c) => {
    await loadList(c);
    for (let i = 0; i < ids.length; i++) {
      log(`\n[${i + 1}/${ids.length}] 删除 file_id=${ids[i]}`);
      try {
        const r = await deleteOne(c, ids[i]);
        if (r.skipped) log(`        ⏭️  跳过：${r.reason}`);
        else if (r.dry) log(`        🔍 DRY 定位成功：${r.title}（wrp=${r.wrpIdx}，图标 ${r.iconPos.w}x${r.iconPos.h}）`);
        else { log(`        ✅ 已删除：${r.title}`); if (r.wording) log(`        确认框：${r.wording}`); }
        results.push({ file_id: ids[i], ok: true, ...r });
      } catch (e) {
        log(`        ❌ 失败: ${e.message.slice(0, 150)}`);
        results.push({ file_id: ids[i], ok: false, reason: e.message.slice(0, 150) });
        await loadList(c).catch(() => {});
      }
      await sleep(1200);
    }
  });
  log("\n================ 汇总 ================");
  results.forEach((r) => log(`${r.ok ? "OK  " : "FAIL"}  ${r.file_id}  ${r.title || ""}  ${r.reason || ""}`));
  log(`成功 ${results.filter((r) => r.ok).length} / ${ids.length}`);
  fs.writeFileSync("/tmp/wxdel_result.json", JSON.stringify(results, null, 2));
}

main().catch((e) => { console.error("FATAL:", e.message); process.exit(1); });
