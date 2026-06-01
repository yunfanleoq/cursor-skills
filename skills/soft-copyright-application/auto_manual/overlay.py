"""Inject red-box callout overlays on live pages before Playwright screenshots."""

from __future__ import annotations

from typing import Any

OVERLAY_INSTALL_JS = """
(specs) => {
  document.getElementById('sc-manual-overlay-root')?.remove();

  const root = document.createElement('div');
  root.id = 'sc-manual-overlay-root';
  root.style.cssText =
    'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:2147483646;';

  const style = document.createElement('style');
  style.textContent = `
    #sc-manual-overlay-root .sc-hl {
      position: absolute;
      border: 2px solid #e53935;
      border-radius: 3px;
      box-sizing: border-box;
      background: rgba(229, 57, 53, 0.04);
    }
    #sc-manual-overlay-root .sc-lbl {
      position: absolute;
      font: 11px/1.25 "Microsoft YaHei", "PingFang SC", sans-serif;
      color: #c62828;
      max-width: 96px;
      text-align: center;
    }
    #sc-manual-overlay-root .sc-lbl span {
      display: inline-block;
      padding: 1px 4px;
      background: rgba(255,255,255,0.96);
      border: 1px solid #e53935;
      border-radius: 2px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.08);
    }
    #sc-manual-overlay-root svg.sc-arrows {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      overflow: visible;
      pointer-events: none;
    }
  `;
  root.appendChild(style);

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('sc-arrows');
  root.appendChild(svg);
  document.body.appendChild(root);

  const docW = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  const docH = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
  svg.setAttribute('width', String(docW));
  svg.setAttribute('height', String(docH));

  const pad = 3;
  const gap = 8;
  const margin = 6;
  const maxGap = 28;

  function pickElement(spec) {
    if (spec.selector) {
      const nodes = document.querySelectorAll(spec.selector);
      if (nodes.length) {
        const idx = Math.min(spec.index || 0, nodes.length - 1);
        return nodes[idx];
      }
    }
    if (spec.text) {
      const all = [
        ...document.querySelectorAll(
          'label, .el-form-item__label, button, .el-input__wrapper, input, span, a, th, td'
        ),
      ];
      const exact = spec.exact !== false;
      const matched = all.filter((el) => {
        const t = (el.innerText || el.textContent || '').trim();
        if (!t) return false;
        return exact ? t === spec.text : t === spec.text || t.includes(spec.text);
      });
      matched.sort((a, b) => {
        const ra = a.getBoundingClientRect();
        const rb = b.getBoundingClientRect();
        return ra.width * ra.height - rb.width * rb.height;
      });
      return matched[0] || null;
    }
    return null;
  }

  function pageRect(el) {
    const r = el.getBoundingClientRect();
    return {
      left: r.left + window.scrollX,
      top: r.top + window.scrollY,
      width: r.width,
      height: r.height,
      right: r.left + window.scrollX + r.width,
      bottom: r.top + window.scrollY + r.height,
      cx: r.left + window.scrollX + r.width / 2,
      cy: r.top + window.scrollY + r.height / 2,
    };
  }

  function addLine(x1, y1, x2, y2) {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', String(x1));
    line.setAttribute('y1', String(y1));
    line.setAttribute('x2', String(x2));
    line.setAttribute('y2', String(y2));
    line.setAttribute('stroke', '#e53935');
    line.setAttribute('stroke-width', '1.2');
    line.setAttribute('stroke-linecap', 'round');
    svg.appendChild(line);
  }

  function labelWidth(label) {
    return Math.min(96, Math.max(44, label.length * 11 + 10));
  }

  function placement(r, side, lw) {
    let lx = 0;
    let ly = 0;
    let ax = r.cx;
    let ay = r.cy;
    if (side === 'top') {
      lx = r.cx - lw / 2;
      ly = r.top - pad - gap - 16;
      ay = r.top - pad;
    } else if (side === 'bottom') {
      lx = r.cx - lw / 2;
      ly = r.bottom + pad + gap;
      ay = r.bottom + pad;
    } else if (side === 'left') {
      lx = r.left - pad - gap - lw;
      ly = r.cy - 8;
      ax = r.left - pad;
      ay = r.cy;
    } else {
      lx = r.right + pad + gap;
      ly = r.cy - 8;
      ax = r.right + pad;
      ay = r.cy;
    }
    return { lx, ly, ax, ay };
  }

  function fits(lx, ly, lw, side, r) {
    if (lx < margin || lx + lw > docW - margin) return false;
    if (ly < margin || ly > docH - 18) return false;
    if (side === 'left' && r.left - (lx + lw) > maxGap) return false;
    if (side === 'right' && lx - r.right > maxGap) return false;
    if (side === 'top' && r.top - (ly + 16) > maxGap) return false;
    if (side === 'bottom' && ly - r.bottom > maxGap) return false;
    return true;
  }

  for (const spec of specs || []) {
    const el = pickElement(spec);
    if (!el) continue;
    const r = pageRect(el);
    if (r.width < 2 || r.height < 2) continue;

    const box = document.createElement('div');
    box.className = 'sc-hl';
    box.style.left = `${r.left - pad}px`;
    box.style.top = `${r.top - pad}px`;
    box.style.width = `${r.width + pad * 2}px`;
    box.style.height = `${r.height + pad * 2}px`;
    root.appendChild(box);

    const label = (spec.label || '').trim();
    if (!label) continue;

    const lw = labelWidth(label);
    const preferred = (spec.side || 'top').toLowerCase();
    const trySides = [preferred, 'top', 'right', 'bottom', 'left'].filter(
      (s, i, arr) => arr.indexOf(s) === i
    );
    let chosen = null;
    for (const side of trySides) {
      const p = placement(r, side, lw);
      if (fits(p.lx, p.ly, lw, side, r)) {
        chosen = { ...p, side };
        break;
      }
    }
    if (!chosen) {
      chosen = { ...placement(r, 'top', lw), side: 'top' };
      chosen.lx = Math.max(margin, Math.min(chosen.lx, docW - lw - margin));
      chosen.ly = Math.max(margin, Math.min(chosen.ly, docH - 20));
    }

    const lbl = document.createElement('div');
    lbl.className = 'sc-lbl';
    lbl.innerHTML = `<span>${label}</span>`;
    lbl.style.width = `${lw}px`;
    lbl.style.left = `${chosen.lx}px`;
    lbl.style.top = `${chosen.ly}px`;
    root.appendChild(lbl);

    const tx = chosen.lx + lw / 2;
    const ty =
      chosen.side === 'bottom'
        ? chosen.ly
        : chosen.side === 'top'
          ? chosen.ly + 14
          : chosen.ly + 8;
    addLine(tx, ty, chosen.ax, chosen.ay);
  }
}
"""

CLEAR_OVERLAY_JS = "() => document.getElementById('sc-manual-overlay-root')?.remove()"


async def apply_overlays(page: Any, overlays: list[dict[str, Any]] | None) -> None:
    if not overlays:
        return
    await page.evaluate(OVERLAY_INSTALL_JS, overlays)
    await page.wait_for_timeout(120)


async def clear_overlays(page: Any) -> None:
    await page.evaluate(CLEAR_OVERLAY_JS)
