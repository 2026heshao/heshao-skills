/* 好例：舞台层共享件在调用幕渲染器之前复位，且都进了 signature()。 */
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
    R.dim.style.opacity = "0";           // 关键：调用幕渲染器之前复位
    RENDERERS[ai](t);
    renderCaptions(t); renderHud(t); renderFoot(t); renderFade(t);
  }

  function signature() {
    const roots = [R.cap, R.hud, R.foot, R.fade, R.dim];
    return roots.map(e => e.style.opacity).join('|');
  }
  window.ENGINE = { renderAt, signature };
})();
