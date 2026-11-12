/* 坏例：故意复刻 2026-11-05 的落版压灰 bug —— 检查器必须变红。
   1) S03 设了 R.dim，renderAt 在调用幕渲染器之前不复位；
   2) signature() 的 roots 里没有 R.dim，seek 测试看不见它。 */
(function () {
  'use strict';
  const stage = document.getElementById('stage');
  const R = {};
  function box(parent, cls, x, y, w, h) { const e = document.createElement('div'); parent.appendChild(e); return e; }
  function el(t, cls, parent, txt) { const e = document.createElement(t); if (parent) parent.appendChild(e); return e; }

  R.dim = box(stage, 'dim');
  R.cap = box(stage, null, 0, 0, 10, 10);
  R.hud = el('div', null, stage, '');
  R.foot = el('div', null, stage, '');
  R.fade = box(stage, null, 0, 0, 10, 10);

  function renderCaptions(t) { R.cap.style.opacity = '0'; }
  function renderHud(t) { R.hud.style.opacity = '0'; }
  function renderFoot(t) { R.foot.style.opacity = '0'; }
  function renderFade(t) { R.fade.style.opacity = '1'; }
  function renderS0(t) { R.dim.style.opacity = '0.2'; }
  const RENDERERS = [renderS0];

  function renderAt(t) {
    const ai = 0;
    RENDERERS[ai](t);                    // 没有先复位 R.dim —— bug 就在这
    renderCaptions(t); renderHud(t); renderFoot(t); renderFade(t);
  }

  function signature() {
    const roots = [R.cap, R.hud, R.foot, R.fade];   // 漏了 R.dim
    return roots.map(e => e.style.opacity).join('|');
  }
  window.ENGINE = { renderAt, signature };
})();
