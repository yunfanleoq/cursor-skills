// 公众号「贴图」（图片消息 / newspic）草稿批量发表驱动
// 用法: node wxtietu.mjs <file_id,file_id,...>
//
// 与 wxflow.mjs（图文）的区别（2026-10-09 实测）：
//   1. 贴图没有「原创」设置、没有「合集」设置 —— 那两步直接跳过
//   2. 贴图的发表弹窗不同：只有「定时发表」开关，**没有「群发通知」开关**
//      （弹窗原文：「发表贴图无需开启群发通知」）
//   3. 从草稿卡片点「发表」，编辑页打开后**发表弹窗会自动弹出**，不需要再点 #js_send
import fs from "node:fs";
import { execSync } from "node:child_process";

const PORT = Number(process.env.CDP_PORT || 9222);
const BASE = `http://127.0.0.1:${PORT}`;
const TOKEN = process.env.WX_TOKEN || "978829597";
const LIST_URL = `https://mp.weixin.qq.com/cgi-bin/appmsg?begin=0&count=50&type=77&action=list_card&token=${TOKEN}&lang=zh_CN`;
const SCAN_TIMEOUT = Number(process.env.WX_SCAN_TIMEOUT || 180);

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

// 真·可见 = 宽高都大于 0（页面里大量同名副本宽>0 但高=0）
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

async function click(c, spec, { settle = 500, scroll = false } = {}) {
  const info = await js(c, `(()=>{${VISF}
    const el=[...document.querySelectorAll(${JSON.stringify(spec)})].find(_vis);
    if(!el) return null;
    if(${scroll}) el.scrollIntoView({block:"center", inline:"center"});
    const r=el.getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+r.height/2,w:Math.round(r.width),h:Math.round(r.height)};
  })()`);
  if (!info) throw new Error("找不到可见元素: " + spec);
  await dispatchAt(c, info.x, info.y, settle);
  return info;
}

// 在「第 idx 个 root」内部点击 inner（作用域化的弹窗按钮）
// ⚠️ 优先取「真正可见」的那个：同名按钮常有宽>0 但高=0 的隐藏副本，
// 点到隐藏副本上等于点了个寂寞（2026-10-09 cncv-02 就是这么卡死的）。
async function clickIn(c, rootSel, rootIdx, innerSel, { settle = 800 } = {}) {
  const info = await js(c, `(()=>{${VISF}
    const roots=[...document.querySelectorAll(${JSON.stringify(rootSel)})];
    const root=roots[${rootIdx}];
    if(!root) return null;
    let el=[...root.querySelectorAll(${JSON.stringify(innerSel)})].find(_vis);
    if(!el) el=root.querySelector(${JSON.stringify(innerSel)});
    if(!el) return null;
    el.scrollIntoView({block:"center"});
    const r=el.getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+r.height/2,w:Math.round(r.width),h:Math.round(r.height)};
  })()`);
  if (!info || !info.w) throw new Error(`clickIn 找不到 ${rootSel}[${rootIdx}] ${innerSel}`);
  await dispatchAt(c, info.x, info.y, settle);
  return info;
}

async function waitFor(fn, timeout, step, label) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) { if (await fn()) return true; await sleep(step); }
  throw new Error("等待超时: " + label);
}

function activateChrome() {
  try { execSync(`osascript -e 'tell application "Google Chrome" to activate'`, { timeout: 8000 }); } catch {}
}

const isEditor = (t) => t.type === "page" && t.url.includes("media/appmsg_edit");
const editorTargets = async () => (await listTargets()).filter(isEditor);

// ⚠️ 2026-10-09 踩过：发表完一篇后，草稿列表页那个标签会被连带关掉，
// 下一轮 withPage("action=list_card") 直接抛「没有匹配的页面」，整批秒退。
// 所以每篇开跑前先确保列表页标签在，不在就重开。
const hasListPage = async () => (await listTargets()).some((t) => t.type === "page" && t.url.includes("action=list_card"));

async function ensureListPage() {
  for (let i = 0; i < 4; i++) {
    if (await hasListPage()) return true;
    log("        · 草稿列表页不在，重新打开…");
    const url = `${BASE}/json/new?${encodeURIComponent(LIST_URL)}`;
    try { await fetch(url, { method: "PUT" }); }
    catch { try { await fetch(url); } catch {} }
    await sleep(2500);
  }
  return await hasListPage();
}

async function closeAllEditorTabs() {
  const eds = await editorTargets();
  for (const t of eds) { try { await fetch(`${BASE}/json/close/${t.id}`); } catch {} }
  if (eds.length) await sleep(800);
  return eds.length;
}

// 每轮探测页面处于哪一步
// 贴图没有原创/合集，所以这里只关心：发表弹窗 / 二次确认 / 二维码
const STATE_EXPR = `(()=>{${VISF}
  const all=(s)=>[...document.querySelectorAll(s)];
  // 发表弹窗：可见、内部有可见的 primary 按钮、且文案含「定时发表」
  const pubIdx = all('.weui-desktop-dialog__wrp').findIndex(e=>{
    if(!_vis(e)) return false;
    const b=e.querySelector('button.weui-desktop-btn_primary');
    if(!b||!_vis(b)) return false;
    const t=(e.innerText||'');
    return t.includes('定时发表') || t.trim().startsWith('发表');
  });
  const dcIdx   = all('.double_check_dialog').findIndex(e=>_vis(e.querySelector('button.weui-desktop-btn_primary')));
  const qrEl    = all('img.qrcode.js_qrcode').find(_vis) || null;
  let schedOn = null;
  if (pubIdx >= 0) {
    const root = all('.weui-desktop-dialog__wrp')[pubIdx];
    // 「定时发表」这一行的小字节点 → 向上找到含开关的容器
    let sw = null;
    const leaf = [...root.querySelectorAll('*')].find(x=>x.children.length===0 && (x.innerText||'').trim()==='定时发表');
    let n = leaf;
    for (let d=0; n && d<4; d++, n=n.parentElement) { const s=n.querySelector('input.weui-desktop-switch__input'); if(s){sw=s;break;} }
    if (!sw) sw = root.querySelector('input.weui-desktop-switch__input');
    schedOn = sw ? sw.checked : null;
  }
  const pubText = pubIdx>=0 ? (all('.weui-desktop-dialog__wrp')[pubIdx].innerText||'').replace(/\\s+/g,' ').slice(0,80) : '';
  return { qr: !!qrEl, expired: document.body.innerText.includes('二维码已失效'), pubIdx, dcIdx, schedOn, pubText };
})()`;

async function stepOpenEditor(fileId) {
  activateChrome();
  await ensureListPage();
  return withPage("action=list_card", async (c) => {
    await c.send("Page.enable").catch(() => {});
    await c.send("Page.bringToFront").catch(() => {});
    await c.send("Page.navigate", { url: LIST_URL });
    await sleep(1500);
    await c.send("Page.bringToFront").catch(() => {});
    await waitFor(async () => (await js(c, `document.querySelectorAll('.weui-desktop-card__inner').length`)) >= 1, 25000, 600, "列表加载");
    await waitFor(async () => (await js(c, `document.visibilityState`)) === "visible", 8000, 300, "标签可见");

    // 参数既可以是 file_id（纯数字），也可以是标题关键词。
    // ⚠️ 2026-10-09：发表失败的草稿会被重存，Vue 里的 file_id 变成占位值 0，
    //    此时只能靠标题匹配来定位卡片。
    const numeric = /^\d+$/.test(fileId);
    const found = await js(c, `(()=>{
      const cards=[...document.querySelectorAll('.weui-desktop-card__inner')];
      const pick=(el)=>{let n=el,d=0;while(n&&d<8){if(n.__vue__)return n.__vue__;n=n.parentElement;d++;}return null;};
      const want=${JSON.stringify(fileId)};
      const numeric=${numeric};
      const norm=(s)=>String(s).replace(/&nbsp;/g,' ').replace(/\\s+/g,'').trim();
      for(let i=0;i<cards.length;i++){
        const vm=pick(cards[i]);const it=vm&&(vm.$data.list||[])[0];
        if(!it) continue;
        if(numeric){ if(String(it.file_id)===want) return {i,title:it.title}; }
        else { if(norm(it.title).includes(norm(want))) return {i,title:it.title}; }
      }
      return null;
    })()`);
    if (!found) throw new Error("草稿箱里找不到 " + fileId);

    const box = await js(c, `(()=>{
      const card=document.querySelectorAll('.weui-desktop-card__inner')[${found.i}];
      card.scrollIntoView({block:"center"});
      const r=card.getBoundingClientRect();
      return {x:r.x+r.width/2,y:r.y+Math.min(70,r.height/2)};
    })()`);
    await c.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: box.x, y: box.y, buttons: 0 });
    await sleep(500);
    const pos = await js(c, `(()=>{
      const b=document.querySelectorAll('.weui-desktop-card__inner')[${found.i}].querySelector('.publish_enable_button a');
      if(!b) return null;
      const r=b.getBoundingClientRect();
      return {x:r.x+r.width/2,y:r.y+r.height/2};
    })()`);
    if (!pos) throw new Error("找不到发表按钮");
    const m = (type, extra = {}) => c.send("Input.dispatchMouseEvent", { type, x: pos.x, y: pos.y, button: "left", clickCount: 1, ...extra });
    await m("mouseMoved", { buttons: 0 });
    await sleep(160);
    await m("mousePressed", { buttons: 1 });
    await sleep(90);
    await m("mouseReleased", { buttons: 0 });
    return found.title;
  });
}

async function stepConfigure() {
  await waitFor(async () => (await editorTargets()).length > 0, 30000, 700, "编辑页打开");
  const editorId = (await editorTargets())[0].id;
  return withPage("media/appmsg_edit", async (c) => {
    await c.send("Page.enable").catch(() => {});
    await c.send("Page.bringToFront").catch(() => {});
    await sleep(700);

    const alive = async () => (await listTargets()).some((t) => t.id === editorId);
    let last = "", repeat = 0;

    for (let i = 0; i < 80; i++) {
      if (!(await alive())) return { hasQr: false, note: "编辑页已关闭" };
      const st = await js(c, STATE_EXPR).catch(() => null);
      if (!st) { await sleep(500); continue; }

      const sig = JSON.stringify([st.qr, st.pubIdx, st.dcIdx, st.schedOn, st.pubText.slice(0, 30)]);
      if (sig === last) { repeat++; if (repeat > 12) throw new Error("状态卡死: " + sig.slice(0, 160)); }
      else { repeat = 0; last = sig; }

      if (st.qr) {
        await js(c, `(()=>{const q=[...document.querySelectorAll('img.qrcode.js_qrcode')].find(e=>e.getBoundingClientRect().width>0);if(q&&q.scrollIntoView)q.scrollIntoView({block:'center'});return 1;})()`);
        await c.send("Page.bringToFront").catch(() => {});
        return { hasQr: true, note: "出现扫码" };
      }
      if (st.dcIdx >= 0) {
        await clickIn(c, ".double_check_dialog", st.dcIdx, "button.weui-desktop-btn_primary", { settle: 2500 });
        continue;
      }
      if (st.pubIdx >= 0) {
        // ★ 定时发表必须关（默认就是关的；万一被打开就关回去）
        if (st.schedOn) {
          const pos = await js(c, `(()=>{${VISF}
            const root=[...document.querySelectorAll('.weui-desktop-dialog__wrp')][${st.pubIdx}];
            if(!root) return null;
            let sw=null;
            const leaf=[...root.querySelectorAll('*')].find(x=>x.children.length===0&&(x.innerText||'').trim()==='定时发表');
            let n=leaf;
            for(let d=0;n&&d<4;d++,n=n.parentElement){const s=n.querySelector('input.weui-desktop-switch__input');if(s){sw=s;break;}}
            if(!sw) sw=root.querySelector('input.weui-desktop-switch__input');
            if(!sw) return null;
            const lab=sw.closest('label')||sw.parentElement;
            const r=lab.getBoundingClientRect();
            return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
          if (!pos) throw new Error("找不到定时发表开关");
          await dispatchAt(c, pos.x, pos.y, 1200);
          continue;
        }
        await clickIn(c, ".weui-desktop-dialog__wrp", st.pubIdx, "button.weui-desktop-btn_primary", { settle: 2500 });
        continue;
      }
      // 没有任何弹窗 → 兜底点页面底部「发表」
      await click(c, "#js_send", { settle: 2200, scroll: true });
    }
    throw new Error("状态机循环次数用尽");
  });
}

async function clickTextAny(c, texts) {
  for (const t of texts) {
    const info = await js(c, `(()=>{${VISF}
      const el=[...document.querySelectorAll('a,span,div,button')].filter(e=>_vis(e)&&(e.innerText||'').trim()===${JSON.stringify(t)}
        && e.children.length<=1).pop();
      if(!el) return null;const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    if (info) { await dispatchAt(c, info.x, info.y, 1500); return t; }
  }
  return null;
}

async function publishOne(fileId, seq, total) {
  const t0 = Date.now();
  log(`\n[${seq}/${total}] file_id=${fileId} 开始`);
  const killed = await closeAllEditorTabs();
  if (killed) log(`        清理了 ${killed} 个残留编辑页`);
  let title;
  try { title = await stepOpenEditor(fileId); }
  catch (e) {
    log(`        ↻ ${e.message.slice(0, 70)} —— 重开列表页后重试一次`);
    await ensureListPage();
    await sleep(1500);
    title = await stepOpenEditor(fileId);
  }
  log(`        卡片: ${title}`);
  // ⚠️ 编辑页打开偶发超时（时序抖动，不是内容问题）。原样重开一次通常就过。
  let cfg;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try { cfg = await stepConfigure(); break; }
    catch (e) {
      if (attempt === 2) throw e;
      log(`        ↻ ${e.message.slice(0, 70)} —— 清理残留后重开编辑页再试一次`);
      await closeAllEditorTabs();
      await ensureListPage();
      await sleep(1800);
      try { await stepOpenEditor(fileId); } catch (e2) { log(`        · 重开卡片失败: ${e2.message.slice(0, 60)}`); }
      await sleep(1500);
    }
  }
  const { hasQr, note } = cfg;
  log(`        弹窗: ${note || ""}`);

  if (!hasQr) {
    const ok = await waitFor(async () => (await editorTargets()).length === 0, 45000, 2000, "编辑页关闭").catch(() => false);
    if (!ok) { log("        ❌ 未出现扫码且编辑页未关闭"); return { ok: false, title, reason: "编辑页未关闭" }; }
    log("        ✅ 无需扫码，已提交");
    return { ok: true, title, file_id: fileId };
  }

  activateChrome();
  log("        ⏳ 出现扫码验证，已把页面推到最前，等扫码…");
  const t1 = Date.now();
  let refreshed = 0;
  while (Date.now() - t1 < SCAN_TIMEOUT * 1000) {
    if ((await editorTargets()).length === 0) { log(`        ✅ 扫码通过，发表完成（用时 ${((Date.now() - t0) / 1000).toFixed(0)}s）`); return { ok: true, title, file_id: fileId }; }
    const expired = await withPage("media/appmsg_edit", (cc) => js(cc, `document.body.innerText.includes('二维码已失效')`)).catch(() => false);
    if (expired && refreshed < 4) {
      refreshed++;
      log("        ♻️ 二维码失效，尝试刷新");
      await withPage("media/appmsg_edit", (cc) => clickTextAny(cc, ["刷新", "点击刷新"])).catch(() => {});
      activateChrome();
      continue;
    }
    await sleep(2500);
  }
  log("        ❌ 扫码等待超时");
  return { ok: false, title, reason: "扫码超时" };
}

async function dumpList() {
  return withPage("action=list_card", async (c) => {
    await c.send("Page.enable").catch(() => {});
    await c.send("Page.bringToFront").catch(() => {});
    await waitFor(async () => (await js(c, `document.querySelectorAll('.weui-desktop-card__inner').length`)) >= 1, 25000, 600, "列表加载");
    const rows = await js(c, `(()=>{
      const cards=[...document.querySelectorAll('.weui-desktop-card__inner')];
      const pick=(el)=>{let n=el,d=0;while(n&&d<8){if(n.__vue__)return n.__vue__;n=n.parentElement;d++;}return null;};
      const out=[];
      for(let i=0;i<cards.length;i++){
        const vm=pick(cards[i]);const it=vm&&(vm.$data.list||[])[0];
        if(it) out.push({i,file_id:String(it.file_id),title:String(it.title).replace(/&nbsp;/g,' '),update_time:it.update_time});
      }
      return out;
    })()`);
    return rows || [];
  });
}

async function main() {
  const ids = (process.argv[2] || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (!ids.length) { log("用法: node wxtietu.mjs <file_id,...>   |   node wxtietu.mjs list"); return; }
  if (ids[0] === "list") {
    const rows = await dumpList();
    log(`共 ${rows.length} 条草稿：`);
    rows.forEach((r, i) => log(`${String(i).padStart(2)}  ${r.file_id}  ${r.title}`));
    fs.writeFileSync(process.env.WX_LIST_OUT || "/tmp/wxtietu_list.json", JSON.stringify(rows, null, 2));
    return;
  }
  const results = [];
  for (let i = 0; i < ids.length; i++) {
    try { results.push(await publishOne(ids[i], i + 1, ids.length)); }
    catch (e) {
      log(`        ❌ 失败: ${e.message.slice(0, 150)}`);
      await closeAllEditorTabs();
      results.push({ ok: false, title: ids[i], reason: e.message.slice(0, 150) });
    }
    await sleep(1500);
  }
  log("\n================ 汇总 ================");
  results.forEach((r, i) => log(`${r.ok ? "OK  " : "FAIL"}  ${ids[i]}  ${r.title || ""}  ${r.reason || ""}`));
  log(`成功 ${results.filter((r) => r.ok).length} / ${ids.length}`);
  fs.writeFileSync(process.env.WX_RESULT_OUT || "/tmp/wxtietu_result.json", JSON.stringify(results, null, 2));
}

main().catch((e) => { console.error("FATAL:", e.message); process.exit(1); });
