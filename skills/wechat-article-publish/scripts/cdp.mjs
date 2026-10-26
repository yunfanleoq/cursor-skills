// 极简 Chrome DevTools Protocol 客户端（零依赖，靠 Node 内置 WebSocket/fetch）
// 用法：
//   node cdp.mjs tabs
//   node cdp.mjs eval "<js 表达式>"
//   node cdp.mjs shot <输出路径.png>
//   node cdp.mjs nav <url>
//   node cdp.mjs click "<css 选择器>"
//   node cdp.mjs clicktext "<包含的文本>"
import fs from "node:fs";

const PORT = process.env.CDP_PORT || 9222;
const BASE = `http://127.0.0.1:${PORT}`;

// 选择器支持 "@N:selector" —— 取第 N 个匹配元素（N 从 0 开始）
// 注意：页面里大量同名隐藏副本（宽>0 但高=0），普通选择器优先取真正可见的
const PICK_FN = `const _pick = (spec) => {
  const m = spec.match(/^@(\\d+):([\\s\\S]*)$/);
  if (m) { const all = [...document.querySelectorAll(m[2])]; return all[+m[1]] || null; }
  const all = [...document.querySelectorAll(spec)];
  return all.find((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; }) || all[0] || null;
};`;

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
    ws.addEventListener("error", (e) => rej(new Error("ws error: " + (e.message || "connect failed"))));
  });
  ws.addEventListener("message", (ev) => {
    let m;
    try { m = JSON.parse(ev.data); } catch { return; }
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id);
      pending.delete(m.id);
      m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
    }
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++seq;
    const timer = setTimeout(() => {
      if (pending.has(id)) { pending.delete(id); reject(new Error(`timeout: ${method}`)); }
    }, 60000);
    timer.unref?.();
    pending.set(id, {
      resolve: (v) => { clearTimeout(timer); resolve(v); },
      reject: (e) => { clearTimeout(timer); reject(e); },
    });
    ws.send(JSON.stringify({ id, method, params }));
  });
  return { send, ready, close: () => ws.close() };
}

async function main() {
  const [cmd, arg] = process.argv.slice(2);

  if (cmd === "newtab") {
    const r = await fetch(`${BASE}/json/new?${encodeURIComponent(arg)}`, { method: "PUT" });
    const j = await r.json();
    console.log("已新建标签:", (j.url || "").slice(0, 120));
    return;
  }

  if (cmd === "tabs") {
    const ts = await listTargets();
    console.log(JSON.stringify(ts.map((t) => ({ type: t.type, title: t.title, url: t.url })), null, 2));
    return;
  }

  const targets = await listTargets();
  const MATCH = process.env.CDP_MATCH || "";
  let pages = targets.filter((t) => t.type === "page" && !t.url.startsWith("devtools://"));
  if (MATCH) {
    pages = pages.filter((t) => t.url.includes(MATCH));
    if (!pages.length) throw new Error(`没有 URL 含 "${MATCH}" 的页面。当前页面：\n` +
      targets.filter(t => t.type === "page").map(t => "  " + t.url.slice(0, 120)).join("\n"));
  } else {
    // 取 URL 最像公众号后台的那个页面
    pages.sort((a, b) => (b.url.includes("weixin.qq.com") ? 1 : 0) - (a.url.includes("weixin.qq.com") ? 1 : 0));
  }
  const t = pages[0];

  const c = makeClient(t.webSocketDebuggerUrl);
  await c.ready;
  await c.send("Runtime.enable").catch(() => {});

  try {
    if (cmd === "eval") {
      const r = await c.send("Runtime.evaluate", {
        expression: arg, returnByValue: true, awaitPromise: true, userGesture: true,
      });
      if (r.exceptionDetails) {
        console.error("页面内异常:", JSON.stringify(r.exceptionDetails.exception?.description || r.exceptionDetails));
        process.exit(2);
      }
      const v = r.result?.value;
      console.log(typeof v === "string" ? v : JSON.stringify(v, null, 2));
    } else if (cmd === "front") {
      // 把当前匹配的标签页推到浏览器最前（配合 osascript 激活 App）
      await c.send("Page.enable").catch(() => {});
      await c.send("Page.bringToFront").catch(() => {});
      await c.send("Runtime.evaluate", { expression: "window.focus()" }).catch(() => {});
      const u = await c.send("Runtime.evaluate", { expression: "location.href", returnByValue: true });
      console.log("已置前:", (u.result?.value || "").slice(0, 110));
    } else if (cmd === "shot") {
      const r = await c.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
      fs.writeFileSync(arg, Buffer.from(r.data, "base64"));
      console.log("已保存", arg);
    } else if (cmd === "shotel") {
      // shotel <选择器> <输出路径>：按元素外框裁剪截图（二维码/blobs 都能截）
      const sel = arg;
      const out = process.argv[4];
      const box = await c.send("Runtime.evaluate", {
        expression: `(() => {
          const el = document.querySelector(${JSON.stringify(sel)});
          if (!el) return null;
          el.scrollIntoView({block:"center"});
          const r = el.getBoundingClientRect();
          return {x:r.x, y:r.y, w:r.width, h:r.height, src:(el.src||"").slice(0,120)};
        })()`,
        returnByValue: true,
      });
      const b = box.result?.value;
      if (!b || !b.w) throw new Error("找不到元素或尺寸为 0: " + sel);
      const r = await c.send("Page.captureScreenshot", {
        format: "png",
        clip: { x: b.x, y: b.y, width: b.w, height: b.h, scale: 2 },
      });
      fs.writeFileSync(out, Buffer.from(r.data, "base64"));
      console.log("已保存", out, `${Math.round(b.w)}x${Math.round(b.h)}`, "src=" + b.src);
    } else if (cmd === "hover" || cmd === "realclick") {
      // hover <选择器> / realclick <选择器>：用 CDP Input 域发真实鼠标事件
      const sel = arg;
      const box = await c.send("Runtime.evaluate", {
        expression: `(() => {
          ${PICK_FN}
          const el = _pick(${JSON.stringify(sel)});
          if (!el) return null;
          el.scrollIntoView({block:"center", inline:"center"});
          const r = el.getBoundingClientRect();
          return {x: r.x + r.width/2, y: r.y + r.height/2, w: r.width, h: r.height};
        })()`,
        returnByValue: true,
      });
      const b = box.result?.value;
      if (!b || !b.w) throw new Error("找不到元素或尺寸为 0: " + sel);
      const mouse = (type, extra = {}) => c.send("Input.dispatchMouseEvent", {
        type, x: b.x, y: b.y, button: "left", clickCount: 1, ...extra,
      });
      await mouse("mouseMoved", { buttons: 0 });
      await new Promise((r) => setTimeout(r, 350));
      if (cmd === "realclick") {
        await mouse("mouseMoved", { buttons: 1 });
        await mouse("mousePressed", { buttons: 1 });
        await new Promise((r) => setTimeout(r, 60));
        await mouse("mouseReleased", { buttons: 0 });
      }
      console.log(`${cmd} @ (${Math.round(b.x)},${Math.round(b.y)}) ${Math.round(b.w)}x${Math.round(b.h)}`);
    } else if (cmd === "pubclick") {
      // pubclick <卡片序号>：滚动到该卡片 → 悬停（等工具栏出现）→ 精确点击「发表」
      const idx = Number(arg);
      const cardExpr = `document.querySelectorAll('.weui-desktop-card__inner')[${idx}]`;
      const info = await c.send("Runtime.evaluate", {
        expression: `(() => {
          const card = ${cardExpr};
          if (!card) return null;
          card.scrollIntoView({block:"center"});
          const r = card.getBoundingClientRect();
          return {x: r.x + r.width/2, y: r.y + Math.min(70, r.height/2), title:(card.innerText||'').replace(/\\s+/g,' ').slice(0,44)};
        })()`,
        returnByValue: true,
      });
      const b = info.result?.value;
      if (!b) throw new Error("找不到卡片 " + idx);
      await c.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: b.x, y: b.y, buttons: 0 });
      await new Promise((r) => setTimeout(r, 450));   // 等工具栏由 hover 显现
      const pos = await c.send("Runtime.evaluate", {
        expression: `(() => {
          const btn = ${cardExpr}.querySelector('.publish_enable_button a');
          if (!btn) return null;
          const r = btn.getBoundingClientRect();
          return {x: r.x + r.width/2, y: r.y + r.height/2, w: Math.round(r.width), h: Math.round(r.height), vis: getComputedStyle(btn).visibility, txt: (btn.innerText||'').trim()};
        })()`,
        returnByValue: true,
      });
      const p = pos.result?.value;
      if (!p) throw new Error("找不到发表按钮");
      await c.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: p.x, y: p.y, buttons: 0 });
      await new Promise((r) => setTimeout(r, 150));
      await c.send("Input.dispatchMouseEvent", { type: "mousePressed", x: p.x, y: p.y, button: "left", clickCount: 1, buttons: 1 });
      await new Promise((r) => setTimeout(r, 90));
      await c.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: p.x, y: p.y, button: "left", clickCount: 1, buttons: 0 });
      console.log(`pubclick 卡片${idx} 「${b.title}」 按钮=${p.txt} @(${Math.round(p.x)},${Math.round(p.y)}) ${p.w}x${p.h} ${p.vis}`);
    } else if (cmd === "rclicktext" || cmd === "hovertext") {
      // rclicktext <文字>：找可见且文字精确匹配的最深元素，发真实鼠标点击
      const want = arg;
      const box = await c.send("Runtime.evaluate", {
        expression: `(() => {
          const want = ${JSON.stringify(want)};
          const all = [...document.querySelectorAll("a,button,span,div,li,label,section,p")];
          const hits = all.filter(e => {
            const t = (e.innerText || "").trim();
            if (t !== want) return false;
            const r = e.getBoundingClientRect();
            if (r.width < 1 || r.height < 1) return false;
            const cs = getComputedStyle(e);
            return cs.visibility !== "hidden" && cs.display !== "none";
          });
          if (!hits.length) return null;
          const el = hits[hits.length - 1];
          el.scrollIntoView({block:"center", inline:"center"});
          const r = el.getBoundingClientRect();
          return {x: r.x + r.width/2, y: r.y + r.height/2, w: r.width, h: r.height, tag: el.tagName, cls: (el.className||"").toString().slice(0,50)};
        })()`,
        returnByValue: true,
      });
      const b = box.result?.value;
      if (!b || !b.w) throw new Error("找不到可见且文字为「" + want + "」的元素");
      const mouse = (type, extra = {}) => c.send("Input.dispatchMouseEvent", {
        type, x: b.x, y: b.y, button: "left", clickCount: 1, ...extra,
      });
      await mouse("mouseMoved", { buttons: 0 });
      await new Promise((r) => setTimeout(r, 300));
      if (cmd === "rclicktext") {
        await mouse("mouseMoved", { buttons: 1 });
        await mouse("mousePressed", { buttons: 1 });
        await new Promise((r) => setTimeout(r, 60));
        await mouse("mouseReleased", { buttons: 0 });
      }
      console.log(`${cmd}「${want}」@ (${Math.round(b.x)},${Math.round(b.y)}) ${b.tag}.${b.cls}`);
    } else if (cmd === "type") {
      // type <选择器> <文本>
      const sel = arg;
      const text = process.argv[4] ?? "";
      await c.send("Runtime.evaluate", {
        expression: `(() => {
          const el = document.querySelector(${JSON.stringify(sel)});
          if (!el) return "NOT_FOUND";
          el.focus(); return "FOCUSED";
        })()`,
        returnByValue: true,
      });
      for (const ch of text) {
        await c.send("Input.dispatchKeyEvent", { type: "keyDown", text: ch });
        await c.send("Input.dispatchKeyEvent", { type: "keyUp", text: ch });
      }
      console.log("已输入", text.length, "字符");
    } else if (cmd === "nav") {
      await c.send("Page.enable").catch(() => {});
      await c.send("Page.navigate", { url: arg });
      console.log("已导航到", arg);
    } else if (cmd === "click") {
      const js = `(() => {
        const el = document.querySelector(${JSON.stringify(arg)});
        if (!el) return "NOT_FOUND";
        el.scrollIntoView({block:"center"});
        el.click();
        return "CLICKED";
      })()`;
      const r = await c.send("Runtime.evaluate", { expression: js, returnByValue: true, userGesture: true });
      console.log(r.result?.value);
    } else if (cmd === "clicktext") {
      const js = `(() => {
        const want = ${JSON.stringify(arg)};
        const all = [...document.querySelectorAll("a,button,span,div,li,label")];
        const cands = all.filter(e => (e.innerText||"").trim() === want || (e.innerText||"").trim().includes(want));
        if (!cands.length) return "NOT_FOUND";
        // 取最深的那个（避免点到外层容器）
        const el = cands[cands.length-1];
        el.scrollIntoView({block:"center"});
        el.click();
        return "CLICKED: " + (el.tagName) + " " + (el.innerText||"").trim().slice(0,30);
      })()`;
      const r = await c.send("Runtime.evaluate", { expression: js, returnByValue: true, userGesture: true });
      console.log(r.result?.value);
    } else {
      console.error("未知命令:", cmd);
      process.exit(1);
    }
  } finally {
    c.close();
    // 定时器已 unref，WS 关闭后事件循环自然排空退出；不用 process.exit 以免截断 stdout
  }
}

main().catch((e) => { console.error("ERR:", e.message); process.exit(1); });
