# 4:3 网页高仿真预览契约 / Preview Contract

目标：网页预览不是“大概像”，而是最终视频的唯一时间源。`renderAt(t)` 怎么显示，逐帧渲染就怎么截。
适用边界：本页数据示例来自产品口播片；故事的声音模式、计划到运行时间轴的转换和无声导出见 [动画流程 §5](ai-animation-workflow.md#5-现有脚本的能力边界)。不要用空台词伪造兼容。嵌入 MP4 时两次 rAF 与 DOM 签名不足以证明视频帧就绪；须单独实现并验证素材解码/seek/超时和像素回捞，本契约没有自动提供这些能力。

## 0. 从 recipe 到 preview

- `recipe.fixed.format` → 舞台尺寸（4:3 1440×1080 / 3:4 1080×1440 / 9:16 1080×1920）。
- `recipe.storyboard[].budget` → 每幕时长；累加得到 `scenes[].start/end`，再按旁白实测微调。
- `recipe.picks.caption` → 字幕组件（左下标签/页边注/票根/卷宗标签）。
- `recipe.picks.sound` → SFX 材质；`recipe.picks.transition` → 幕间转场。
- `recipe.prompt.image` → ImageGen 的参考图；最终文字仍由 HTML/SVG 渲染。
- `recipe.prompt.cover` → 封面构图；与正片共用 palette/type/motifs。

## 1. 舞台

```css
#stagewrap { position: relative; flex: 1; overflow: hidden; }
#stage {
  position: absolute; left: 50%; top: 50%;
  width: 1440px; height: 1080px;
  transform: translate(-50%, -50%) scale(var(--s, .7));
  transform-origin: center center;
  overflow: hidden;
}
```

```js
function fit() {
  const w = wrap.clientWidth, h = wrap.clientHeight;
  const s = Math.min(w / 1440, h / 1080);   // 4:3，不裁切
  document.documentElement.style.setProperty('--s', s);
}
```

- 舞台内部永远 1440×1080；外层只缩放。
- 不要用 `object-fit: cover`、不要从 16:9 裁切。
- 1366×768 与 1440×1080 都要测；窄窗口左右留黑是比例约束。
- 画面里只放品牌、版本、比喻/演示数据声明；画幅/分辨率/帧率等制作参数放抽屉和 README，不进画面（atlas 曾把 `4:3 · 1440×1080 / 30FPS` 印在 S01 副行和底栏）。

## 2. 时间轴数据

```js
window.PROMO = {
  dur: 44.94, fps: 30, size: [1440, 1080],
  voice: "assets/audio/voice.m4a",
  sfxDir: "assets/sfx/",
  gains: { voice: 1, sfx: 0.62 },
  scenes: [
    { id: "s00", title: "入库口", code: "INTAKE", start: 0, end: 6.05,
      hud: "01 / INTAKE",
      cues: { head1: 0.70, head2: 2.22, stamp: 4.52 } },
  ],
  captions: [[0.75, 3.28, "你还记得几件？", "几件"]],
  sfx: [{ t: 0.02, name: "shutter", g: 0.55, pan: 0 }],
};
```

- `scenes[].cues` 是绝对秒；幕内动作用 `lt = t - scene.start` 或直接绝对秒。
- `hud` 从 **01** 开始，和图版/底栏/章节共用同一个编号；不要出现图版 01–06、底栏 00–05 的错位（atlas 踩过）。
- `captions` 与 `sfx` 由 `scripts/build_timeline.py` 从旁白时间轴生成，不手写死；它同时导出
  `narration.vtt/.srt`（整句口播，给平台外挂字幕与无障碍）和 `captions.vtt/.srt`（上屏关键词）。
  上游时刻来自 `scripts/build_voice.py` 的 `voice_timeline_<slug>.json`（逐句样本级起止）。
- `sfx` 事件按 `t` 排序；渲染与预览共用同一份。

## 3. 纯函数

```js
// 舞台层共享件必须一起进签名，否则「跨幕泄漏」这一类 bug 测不出来
const roots = [scenes[ai].root, R.cap, R.hud, R.foot, R.fade, R.dim];

function renderAt(t) {
  t = clamp(t, 0, P.dur);
  const ai = activeScene(t);
  roots.forEach((e, i) => {
    const on = i === ai;
    e.style.visibility = on ? "visible" : "hidden";
    e.style.opacity = on ? 1 : 0;
  });
  renderScene(ai, t);
  renderCaptions(t);
  renderShutter(t);
  drawFx(t);
  fade.style.opacity = String(Math.max(
    1 - easeOut(inv(t, 0, .55)),
    easeOut(inv(t, P.dur - .78, P.dur - .02))
  ));
}
```

规则：

- 不读 `Date.now()`、不用 `Math.random()`、不依赖上一帧状态。
- 不写回元素的“出生坐标”；`show()` 的偏移只用于当帧。
- 不用 CSS `transition` / `@keyframes` 做正片动画；所有 opacity/transform/clip-path 由 JS 写。
- 场景容器可以 `display:none` 隐藏；不要靠累积 opacity。
- 文本内容可以每帧写，但必须由 `t` 推导（如命令逐字、计数）。
- **挂在 `#stage` 而不是 `.scene` 的共享元素必须在 `renderAt(t)` 开头复位**（调暗层、全局遮罩、颗粒层、字幕、HUD、脚注、淡入淡出），再由当前幕点亮。不复位的后果是顺序渲染会继承上一幕的状态、单帧 seek 不会 —— 两条路径必然对不上，而且只有逐帧回捞抓得到。2026-11-05 skilllocker 实测：S03 把 `.dim` 设到 0.20 后没人复位，落版被压灰 20%，代价是重渲 1322 帧。

### 验收：0→t 逐帧 vs 直接 seek

```js
window.__setTime(0);
for (let i = 0; i <= 19.9 * 30; i++) window.__setTime(i / 30);
const a = JSON.stringify(signature());   // rect + opacity + transform
window.__setTime(0); window.__setTime(19.9);
const b = JSON.stringify(signature());
console.log(a === b);
```

`signature()` 取当前可见场景的所有元素的 `getBoundingClientRect`、opacity、transform。任何跨帧累加都会在这里暴露。

## 4. 场景写法

- 每幕一个 `<section class="scene">`，构建一次，`renderScene` 只写样式/文本。
- 纸/钢/颗粒用本地纹理；字体本地 `@font-face`；不要依赖网络。
- 印章：scale 2.2→1 + 轻微纸面震动；震动用 `exp(-k·dt)·sin(ω·dt)`，由 `t` 推导。
- 卡片/标签：`clip-path: inset(0 X% 0 0)` 做打印式揭示；不要用逐字 DOM。
- 转场：百叶快门/闸门用 9 条 slat 的 `scaleY`，由 `cut = 1 - |t - scene.start| / .085` 推导。
- 接触表：每幕至少 2 个关键帧（动作前/落定后）。

## 5. 播放器

必须有：

- 播放/暂停（空格）、进度拖拽、时间码、重播；
- 0.5× / 1× / 1.5× / 2×（倍速只改 `t` 推进速率）；
- 字幕开关、静音/音量；
- 全屏；
- 章节条（6 段）；
- 抽屉：分镜/时间码/文案/差异化/规格；
- 首屏 poster（选一个钩子帧），点播放从 0 开始；
- 所有控件有键盘快捷键，且输入框聚焦时不抢占。

```js
function loop(now) {
  if (!playing) return;
  const dt = Math.min(.12, (now - last) / 1000);
  last = now;
  const prev = t;
  t = Math.min(dur, t + dt * speed);
  triggerSfx(prev, t);
  renderAt(t);
  syncVoice();
  if (t >= dur) pause(); else requestAnimationFrame(loop);
}
```

## 6. 音频

### 旁白

- 用一个 `<audio>` 元素；`playbackRate = speed`。
- 自由走 + 迟滞纠偏：`|drift| > .28s` 才 seek；`.12–.28s` 时微调 ±4%。
- 不要每帧写 `currentTime`，否则解码器反复 flush，听出沙沙/咔哒。
- 字幕开关不影响旁白；静音/音量只改增益。

### 音效

- 每个音效建 2–3 个 `Audio` 池，事件越过 `t` 时触发。
- 事件时刻按 `ceil(t*fps)/fps` 量化，和最终 ffmpeg `adelay` 一致。
- 暂停/seek 时重置 `lastSfx = t`，不要补播一堆积压事件。
- 立体声声像可以烘在 WAV 里，播放器不要二次 pan。

## 7. 缓存与资源

- CSS/JS/音频/SFX 全部带 `?v=YYYYMMDDx`。
- 改了任何资源就 bump 版本；交付时提醒 `Ctrl+F5`。
- 字体用 `font-display: block`，`__ready` 等 `document.fonts.ready` 后再置 true。
- 不要在 `document.fonts.ready` 后重画到 `t=0`，否则 poster 会被黑帧覆盖；重画 `lastT`。

## 8. 渲染模式

`preview.html?render=1`：

```css
body.render #topline, body.render #player, body.render #chapterbar,
body.render #footline, body.render #drawer, body.render #bigplay { display: none !important; }
body.render #app { width: 1440px; height: 1080px; }
body.render #stage { left: 0; top: 0; transform: none; }
```

暴露：

```js
window.__ready = true;
window.__duration = P.dur;
window.__fps = P.fps;
window.__setTime = (t) => { lastT = t; renderAt(t); };
```

截图脚本打开 `?render=1`，等 `__ready`，循环 `__setTime(i/fps)`，等两个 `requestAnimationFrame`，再 `Page.captureScreenshot`。

## 9. 预览 QA 清单

- [ ] 无 JS 错误（`window.__errors`）
- [ ] voice readyState 4；播放 1s 后 `paused=false`
- [ ] 4:3 比例 1.3333；1440/1366 不裁切
- [ ] 播放/暂停/拖拽/重播/倍速/字幕/静音/音量/全屏/章节/抽屉
- [ ] 纯函数 seek 签名一致
- [ ] 关键帧接触表：文字不溢出、不挡主体、无空镜
- [ ] 舞台层共享件（调暗 / 遮罩 / 颗粒）已在 `renderAt` 开头复位，且已列入 `signature()` 的元素清单
- [ ] 首屏 poster 不是黑帧；点播放从 0 开始
- [ ] 资源版本号已 bump
