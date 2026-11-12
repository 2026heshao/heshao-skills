#!/usr/bin/env node
/**
 * 舞台层纪律检查器 —— 把 SKILL.md §4「共享元素每帧复位」从文档约定变成机器检查。
 *
 * 背景（2026-11-05 skilllocker 实测）：S03 把挂在 #stage 的 .dim 调暗层设到 0.20 后没人复位，
 * 顺序渲染时 S04 继承了这个状态，落版被压灰 20%；而单帧 seek 只跑当前幕、不会继承，
 * 于是"预览看着对、成片是错的"。这类 bug 原本只有逐帧回捞抓得到，代价是重渲 1322 帧。
 *
 * 判据（刻意收窄，避免把静态家具误报成泄漏）：
 *   只看 `R.<key> = box(stage, …)` / `el(…, stage)` 这类登记在 R 上的舞台层共享元素；
 *   且必须"被某个幕渲染器写过"才要求复位。由 overlay 函数（renderAt 每帧直接调用的那些）
 *   重写的，视为已复位。
 *   另外：凡被写过的舞台层元素都必须出现在 signature() 的 roots 里，否则 seek 测试看不见它。
 *
 * 用法：
 *   node scripts/check_engine_discipline.mjs --engine <项目>/assets/engine.js [--quiet]
 * 退出码：0 通过；1 有违规；2 用法/文件错误。
 */
import { readFileSync, existsSync } from "node:fs";

const argv = process.argv.slice(2);
const val = (k, d) => { const i = argv.indexOf("--" + k); return i >= 0 ? argv[i + 1] : d; };
const has = (k) => argv.includes("--" + k);
const QUIET = has("quiet");

const ENGINE_PATH = val("engine", "");
if (!ENGINE_PATH) {
  console.error("usage: node check_engine_discipline.mjs --engine <path/to/engine.js> [--quiet]");
  process.exit(2);
}
if (!existsSync(ENGINE_PATH)) { console.error(`❌ 找不到 engine.js：${ENGINE_PATH}`); process.exit(2); }
const src = readFileSync(ENGINE_PATH, "utf8");

/* ---------- 括号配对取函数体 ---------- */
function bodiesByName() {
  const out = {};
  const rx = /function\s+([A-Za-z_$][\w$]*)\s*\(/g;
  let m;
  while ((m = rx.exec(src))) {
    const open = src.indexOf("{", m.index);
    if (open < 0) continue;
    let depth = 0, end = -1;
    for (let j = open; j < src.length; j++) {
      if (src[j] === "{") depth++;
      else if (src[j] === "}") { depth--; if (depth === 0) { end = j; break; } }
    }
    if (end > 0 && !out[m[1]]) out[m[1]] = src.slice(open, end + 1);
  }
  return out;
}
const FN = bodiesByName();

/* ---------- 1. 舞台层共享元素：只认 R.<key> ---------- */
const shared = new Set();
let m;
const rxR = /\bR\.(\w+)\s*=\s*(?:box|el)\([^)]*\bstage\b/g;
while ((m = rxR.exec(src))) shared.add(m[1]);
if (!shared.size) {
  if (!QUIET) console.log("未发现登记在 R 上的 #stage 共享元素（无需检查）。");
  process.exit(0);
}

/* ---------- 2. 幕渲染器 与 overlay 函数 ---------- */
const renderAt = FN.renderAt;
if (!renderAt) { console.error("❌ 找不到 renderAt 函数 —— 无法验证复位纪律。"); process.exit(1); }

const sceneFns = new Set();
const rxList = /RENDERERS\s*=\s*\[([^\]]*)\]/g;
let lm;
while ((lm = rxList.exec(src))) {
  for (const t of lm[1].split(",")) {
    const id = t.trim().match(/^([A-Za-z_$][\w$]*)$/);
    if (id) sceneFns.add(id[1]);
  }
}
// 命名约定兜底：renderS00 / renderS01 … 也算幕渲染器（内联匿名函数不算，真实工程都用命名函数）
for (const n of Object.keys(FN)) if (/^renderS\d+/.test(n)) sceneFns.add(n);
const overlayFns = new Set();
const rxCalls = /([A-Za-z_$][\w$]*)\s*\(/g;
let cm;
while ((cm = rxCalls.exec(renderAt))) {
  const n = cm[1];
  if (FN[n] && !sceneFns.has(n) && n !== "renderAt") overlayFns.add(n);
}

const sceneBody = [...sceneFns].map((n) => FN[n] || "").join("\n");
const overlayBody = [...overlayFns].map((n) => FN[n] || "").join("\n");

/* ---------- 3. signature roots ---------- */
const sigBody = FN.signature || "";
// 整段扫 R.<key>：数组字面量里常有 scenes[ai] 这种带 ] 的表达式，按括号截断会漏读
const sigKeys = new Set([...sigBody.matchAll(/\bR\.(\w+)\b/g)].map((x) => x[1]));

/* ---------- 4. 判定 ---------- */
const violations = [];
const okList = [];
const cutAt = renderAt.search(/RENDERERS\s*\[/);
const resetZone = cutAt >= 0 ? renderAt.slice(0, cutAt) : renderAt;

for (const key of shared) {
  const writtenInScene = new RegExp(`R\\.${key}\\.style\\.`).test(sceneBody);
  const rewrittenInOverlay = new RegExp(`R\\.${key}\\.style\\.`).test(overlayBody);
  const reset = new RegExp(`R\\.${key}\\.style\\.(?:opacity|transform|clipPath|visibility)\\s*=\\s*(?:"0"|'0'|0|"hidden"|'hidden'|"")`).test(resetZone);

  if (writtenInScene && !(reset || rewrittenInOverlay)) {
    violations.push(`${key}：挂在 #stage 上、被幕渲染器写过，但 renderAt 在调用 RENDERERS 之前没复位 —— 上一幕的状态会漏进下一幕`);
  }
  if ((writtenInScene || rewrittenInOverlay) && !sigKeys.has(key)) {
    violations.push(`${key}：被写过却没进 signature() 的 roots —— seek 纯函数测试看不见它，这类泄漏抓不到`);
  }
  if (writtenInScene && (reset || rewrittenInOverlay) && sigKeys.has(key)) okList.push(`${key}(复位+签名)`);
  else if (rewrittenInOverlay && sigKeys.has(key) && !writtenInScene) okList.push(`${key}(每帧重写+签名)`);
}

if (violations.length) {
  console.error(`❌ 舞台层纪律未通过（${ENGINE_PATH}）：`);
  for (const v of violations) console.error("   · " + v);
  console.error("   修法：在 renderAt(t) 开头把该元素写回初值，并加进 signature() 的 roots 数组。");
  process.exit(1);
}
if (!QUIET) {
  console.log(`✅ 舞台层纪律通过：共享元素 ${[...shared].join(", ")}；已核 ${okList.join(", ") || "（无被写过的元素）"}`);
}
process.exit(0);
