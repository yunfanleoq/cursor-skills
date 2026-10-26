// 公众号草稿批量发表驱动 v3（状态机 + 精确可见性判断）
// 用法: node wxflow.mjs <file_id,file_id,...>
import fs from "node:fs";
import { execSync } from "node:child_process";

const PORT = Number(process.env.CDP_PORT || 9222);
const BASE = `http://127.0.0.1:${PORT}`;
const TOKEN = process.env.WX_TOKEN || "978829597";
const LIST_URL = `https://mp.weixin.qq.com/cgi-bin/appmsg?begin=0&count=50&type=77&action=list_card&token=${TOKEN}&lang=zh_CN`;
const ALBUM = process.env.WX_ALBUM || "刘思学书画集";
const SCAN_TIMEOUT = Number(process.env.WX_SCAN_TIMEOUT || 180);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(...a);

async function listTargets() {
  const r = await fetch(`${BASE}/json/list`);
  return await r.json();
}

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

// 在「第 idx 个 root」内部点击 inner（用于作用域化的弹窗按钮）
async function clickIn(c, rootSel, rootIdx, innerSel, { settle = 800 } = {}) {
  const info = await js(c, `(()=>{
    const roots=[...document.querySelectorAll(${JSON.stringify(rootSel)})];
    const root=roots[${rootIdx}];
    if(!root) return null;
    const el=root.querySelector(${JSON.stringify(innerSel)});
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

async function closeAllEditorTabs() {
  const eds = await editorTargets();
  for (const t of eds) { try { await fetch(`${BASE}/json/close/${t.id}`); } catch {} }
  if (eds.length) await sleep(800);
  return eds.length;
}

// 每轮探测页面处于哪一步
// 关键：这个页面的弹窗外层容器高度恒为 0，只有内部按钮有真实尺寸，
// 所以一律用「弹窗内部的确定按钮是否可见」来判断该弹窗是否打开。
const STATE_EXPR = `(()=>{${VISF}
  const all=(s)=>[...document.querySelectorAll(s)];
  const idxOf=(s,innerSel)=>all(s).findIndex(e=>{const b=e.querySelector(innerSel);return _vis(b);});
  const claimIdx = idxOf('.claim__original-dialog','button.weui-desktop-btn_primary');
  const albumIdx = idxOf('.album-setting-dialog','button.weui-desktop-btn_primary');
  const dcIdx    = idxOf('.double_check_dialog','button.weui-desktop-btn_primary');
  const massIdx  = idxOf('.new_mass_send_dialog','button.weui-desktop-btn_primary');
  const claimEl = claimIdx>=0 ? all('.claim__original-dialog')[claimIdx] : null;
  const albumEl = albumIdx>=0 ? all('.album-setting-dialog')[albumIdx] : null;
  const massEl  = massIdx>=0 ? all('.new_mass_send_dialog')[massIdx] : null;
  const qrEl    = all('img.qrcode.js_qrcode').find(_vis) || null;
  // 合集下拉的选项是渲染在 body 下的浮层（portal），不一定在 .album-setting-dialog 内部，
  // 所以选项一律全局查、只按可见性过滤。曾因为只查弹窗内部 → 永远判"下拉没打开"
  // → 反复点 .select-input 把它开了又关，卡死在第20幅草稿上。
  const optLi   = all('.select-opt-li').filter(_vis);
  const box = claimEl ? claimEl.querySelector('input.weui-desktop-form__checkbox') : null;
  const sw  = massEl  ? massEl.querySelector('input.weui-desktop-switch__input') : null;
  const inp = albumEl ? albumEl.querySelector('input.weui-desktop-form__input') : null;
  const oriText=(()=>{const r=all('.appmsg-editor__setting-group')
    .map(e=>(e.innerText||'').replace(/\\s+/g,' ').trim()).filter(t=>t.startsWith('原创'))[0]||'';return r;})();
  const albText=(()=>{const e=document.querySelector('#js_article_tags_area');
    return e?(e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,28):'';})();
  return {
    qr: !!qrEl,
    expired: document.body.innerText.includes('二维码已失效'),
    claimIdx, albumIdx, dcIdx, massIdx,
    claimAgreed: box ? box.checked : null,
    albumOptsOpen: optLi.length>0,
    albumInput: inp ? inp.value : '',
    massSwitchOn: sw ? sw.checked : null,
    oriText, albText
  };
})()`;

async function stepOpenEditor(fileId) {
  activateChrome();
  return withPage("action=list_card", async (c) => {
    await c.send("Page.enable").catch(() => {});
    await c.send("Page.bringToFront").catch(() => {});
    await c.send("Page.navigate", { url: LIST_URL });
    await sleep(1500);
    await c.send("Page.bringToFront").catch(() => {});
    await waitFor(async () => (await js(c, `document.querySelectorAll('.weui-desktop-card__inner').length`)) >= 1, 25000, 600, "列表加载");
    await waitFor(async () => (await js(c, `document.visibilityState`)) === "visible", 8000, 300, "标签可见");

    const found = await js(c, `(()=>{
      const cards=[...document.querySelectorAll('.weui-desktop-card__inner')];
      const pick=(el)=>{let n=el,d=0;while(n&&d<8){if(n.__vue__)return n.__vue__;n=n.parentElement;d++;}return null;};
      for(let i=0;i<cards.length;i++){
        const vm=pick(cards[i]);const it=vm&&(vm.$data.list||[])[0];
        if(it && String(it.file_id)===${JSON.stringify(fileId)}) return {i,title:it.title};
      }
      return null;
    })()`);
    if (!found) throw new Error("草稿箱里已无 file_id=" + fileId);

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

    for (let i = 0; i < 90; i++) {
      if (!(await alive())) return { ori: "编辑页已关闭", album: "", hasQr: false };
      const st = await js(c, STATE_EXPR).catch(() => null);
      if (!st) { await sleep(500); continue; }

      const sig = JSON.stringify([st.qr, st.claimIdx, st.claimAgreed, st.albumIdx, st.albumOptsOpen, st.albumInput,
        st.dcIdx, st.massIdx, st.massSwitchOn, st.oriText.slice(0, 6), st.albText.slice(0, 8)]);
      if (sig === last) { repeat++; if (repeat > 10) throw new Error("状态卡死: " + sig.slice(0, 150)); }
      else { repeat = 0; last = sig; }

      if (st.qr) {
        await js(c, `(()=>{const q=[...document.querySelectorAll('img.qrcode.js_qrcode')].find(e=>e.getBoundingClientRect().width>0);if(q&&q.scrollIntoView)q.scrollIntoView({block:"center"});return 1;})()`);
        await c.send("Page.bringToFront").catch(() => {});
        return { ori: st.oriText, album: st.albText, hasQr: true };
      }
      if (st.claimIdx >= 0) {
        if (st.claimAgreed !== true) { await clickIn(c, ".claim__original-dialog", st.claimIdx, "input.weui-desktop-form__checkbox", { settle: 700 }); continue; }
        await clickIn(c, ".claim__original-dialog", st.claimIdx, "button.weui-desktop-btn_primary", { settle: 1800 }); continue;
      }
      if (st.albumIdx >= 0) {
        if (st.albumInput === ALBUM) { await clickIn(c, ".album-setting-dialog", st.albumIdx, "button.weui-desktop-btn_primary", { settle: 1800 }); continue; }
        if (st.albumOptsOpen) {
          const pos = await js(c, `(()=>{${VISF}
            const o=[...document.querySelectorAll('.select-opt-li')].filter(_vis);
            const e=o.find(x=>(x.innerText||'').trim()===${JSON.stringify(ALBUM)});
            if(!e) return null;
            e.scrollIntoView({block:"center"});
            const r=e.getBoundingClientRect();
            return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
          if (!pos) throw new Error("合集列表里没有 " + ALBUM);
          await dispatchAt(c, pos.x, pos.y, 900); continue;
        }
        await clickIn(c, ".album-setting-dialog", st.albumIdx, ".select-input", { settle: 900 }); continue;
      }
      if (st.dcIdx >= 0) { await clickIn(c, ".double_check_dialog", st.dcIdx, "button.weui-desktop-btn_primary", { settle: 2500 }); continue; }
      if (st.massIdx >= 0) {
        const ready = /文字原创|图片原创|漫画原创/.test(st.oriText) && st.albText.includes(ALBUM);
        // 注意：右上角 X 关不干净（会留一层拦截点击的遮罩），必须点「取消」
        if (!ready) { await clickIn(c, ".new_mass_send_dialog", st.massIdx, "button.weui-desktop-btn_default", { settle: 1200 }); continue; }
        // ★ 铁律：默认不群发。订阅号每天只能群发 1 次，草稿箱却有几十篇，额度根本不够。
        //   这里只允许「关闭」开关，永远不打开 —— 不要加任何"要不要群发"的入参。
        //   不群发的发表照样生成永久链接、进主页、可被搜索，只是不推进粉丝订阅列表。
        if (st.massSwitchOn) { await clickIn(c, ".new_mass_send_dialog", st.massIdx, ".mass_send__notify label.weui-desktop-switch", { settle: 1300 }); continue; }
        await clickIn(c, ".new_mass_send_dialog", st.massIdx, "button.weui-desktop-btn_primary", { settle: 2000 }); continue;
      }
      // 无弹窗：按需推进设置
      if (!/文字原创|图片原创|漫画原创/.test(st.oriText)) {
        const pos = await js(c, `(()=>{${VISF}
          const t=[...document.querySelectorAll('.setting-group__title')].filter(_vis);
          const e=t.find(x=>(x.innerText||'').trim()==='原创');
          if(!e) return null;
          e.scrollIntoView({block:"center"});
          const r=e.getBoundingClientRect();
          return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
        if (!pos) throw new Error("找不到可见的原创设置行");
        await dispatchAt(c, pos.x, pos.y, 1800);
        continue;
      }
      if (!st.albText.includes(ALBUM)) {
        await click(c, "#js_article_tags_area .js_article_tags_label", { settle: 1600, scroll: true }); continue;
      }
      await click(c, "#js_send", { settle: 2000, scroll: true });
    }
    throw new Error("状态机循环次数用尽");
  });
}

async function publishOne(fileId, seq, total) {
  const t0 = Date.now();
  log(`\n[${seq}/${total}] file_id=${fileId} 开始`);
  const killed = await closeAllEditorTabs();
  if (killed) log(`        清理了 ${killed} 个残留编辑页`);
  const title = await stepOpenEditor(fileId);
  log(`        卡片: ${title}`);
  const { ori, album, hasQr } = await stepConfigure();
  log(`        原创: ${ori || "(未取到)"}`);
  log(`        合集: ${album || "(未取到)"}`);

  if (!hasQr) {
    const ok = await waitFor(async () => (await editorTargets()).length === 0, 45000, 2000, "编辑页关闭").catch(() => false);
    if (!ok) { log("        ❌ 未出现扫码且编辑页未关闭"); return { ok: false, title, reason: "编辑页未关闭" }; }
    log("        ✅ 无需扫码，已提交");
    return { ok: true, title };
  }

  activateChrome();
  log("        ⏳ 出现扫码验证，已把页面推到最前，等李静扫码…");
  const t1 = Date.now();
  let refreshed = 0;
  while (Date.now() - t1 < SCAN_TIMEOUT * 1000) {
    if ((await editorTargets()).length === 0) { log(`        ✅ 扫码通过，发表完成（用时 ${((Date.now() - t0) / 1000).toFixed(0)}s）`); return { ok: true, title }; }
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

async function main() {
  const ids = (process.argv[2] || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (!ids.length) { log("用法: node wxflow.mjs <file_id,...>"); return; }
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
  fs.writeFileSync("/tmp/wxflow_result.json", JSON.stringify(results, null, 2));
}

main().catch((e) => { console.error("FATAL:", e.message); process.exit(1); });
