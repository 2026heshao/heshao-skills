#!/usr/bin/env node
/**
 * heshao-ai-video-v1 · registry doctor
 *
 * Read-only guard for the deck layer. Adding or banning a card touches four
 * places at once (decks/*.json, compatibility.json, weights.json, the prose in
 * SKILL.md + references/visual-worlds.md). Nothing fails loudly when one of them
 * is missed: pick.mjs silently frees an unknown world, an unlisted card simply
 * becomes unreachable, and the docs drift by one. This script turns those quiet
 * states into a non-zero exit code.
 *
 *   node scripts/doctor.mjs          # FAIL on structural breakage
 *   node scripts/doctor.mjs --soft   # report everything as WARN only
 */
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const AXES = ["world", "hook", "transition", "caption", "sound", "rhythm"];
const DECK_FILE = {
  world: "worlds", hook: "hooks", transition: "transitions",
  caption: "captions", sound: "sounds", rhythm: "rhythms",
};
// compatibility.json groups axes under plural keys that do not always match the axis name
const COMPAT_KEY = {
  hook: "hooks", transition: "transitions", caption: "captions",
  sound: "sounds", rhythm: "rhythms",
};

const soft = process.argv.includes("--soft");
const loadJSON = (p) => JSON.parse(readFileSync(p, "utf8"));

const decks = {};
for (const [axis, file] of Object.entries(DECK_FILE)) {
  decks[axis] = loadJSON(join(ROOT, "decks", `${file}.json`)).cards;
}
const compat = loadJSON(join(ROOT, "compatibility.json"));
const weights = loadJSON(join(ROOT, "weights.json"));

const idsOf = (axis) => decks[axis].map((c) => c.id);
const bannedOf = (axis) => decks[axis].filter((c) => c.banned).map((c) => c.id);
const activeOf = (axis) => idsOf(axis).filter((id) => !bannedOf(axis).includes(id));
const isBanned = (axis, id) => bannedOf(axis).includes(id);

const fails = [];
const warns = [];
const add = (list, msg) => list.push(msg);

/* 1. every active world needs its own compatibility entry */
for (const id of activeOf("world")) {
  if (!compat[id]) {
    add(fails, `world "${id}" 在 compatibility.json 中没有条目 —— pick.mjs 的 allowedFor() 会静默放开整副牌组，兼容矩阵形同不存在`);
  }
}

/* 2. compatibility must not reference ids that no longer exist in the decks */
for (const [world, groups] of Object.entries(compat)) {
  if (!idsOf("world").includes(world)) {
    add(fails, `compatibility.json 有孤儿世界 "${world}"（decks/worlds.json 里不存在）`);
    continue;
  }
  for (const [key, list] of Object.entries(groups)) {
    const axis = Object.keys(COMPAT_KEY).find((a) => COMPAT_KEY[a] === key);
    if (!axis) { add(warns, `compat.${world} 出现未知分组 "${key}"`); continue; }
    if (!Array.isArray(list)) { add(fails, `compat.${world}.${key} 不是数组`); continue; }
    for (const id of list) {
      if (!idsOf(axis).includes(id)) {
        add(fails, `悬空引用：compat.${world}.${key} → "${id}" 不在 decks/${DECK_FILE[axis]}.json`);
      } else if (isBanned(axis, id)) {
        add(fails, `compat.${world}.${key} 允许了 banned 卡 "${id}"（banned 卡只该用于对照审计）`);
      }
    }
  }
}

/* 3. an active card that no world allows is unreachable forever */
for (const axis of AXES) {
  if (axis === "world") continue;
  const key = COMPAT_KEY[axis];
  const reachable = new Set(Object.values(compat).flatMap((g) => g[key] || []));
  const stranded = activeOf(axis).filter((id) => !reachable.has(id));
  if (stranded.length) {
    add(fails, `axis "${axis}" 的这些卡任何世界都不允许，永远抽不到：${stranded.join(", ")}`);
  }
}

/* 4. weights must cover every active card, else it silently defaults to 1 */
for (const axis of AXES) {
  const file = DECK_FILE[axis];
  const missing = activeOf(axis).filter((id) => weights[file]?.[id] == null);
  if (missing.length) {
    add(warns, `weights.${file} 未覆盖：${missing.join(", ")}（会以默认权重 1 参与抽取）`);
  }
  const unknown = Object.keys(weights[file] || {}).filter((id) => !idsOf(axis).includes(id));
  if (unknown.length) add(fails, `weights.${file} 有牌组里不存在的键：${unknown.join(", ")}`);
}

/* 5. the prose world count must match the deck */
const skillPath = join(ROOT, "SKILL.md");
if (existsSync(skillPath)) {
  const text = readFileSync(skillPath, "utf8");
  const m = text.match(/(\d+)\s*套视觉世界配方/);
  if (!m) {
    add(warns, "SKILL.md 找不到「N 套视觉世界配方」这行，无法核对世界数");
  } else if (Number(m[1]) !== activeOf("world").length) {
    add(fails, `SKILL.md 写的是 ${m[1]} 套世界，decks/worlds.json 实际有 ${activeOf("world").length} 个 active 世界`);
  }
  for (const id of activeOf("world")) {
    const card = decks.world.find((c) => c.id === id);
    const zh = card?.name;
    if (zh && !text.includes(zh) && !(existsSync(join(ROOT, "references", "visual-worlds.md")) && readFileSync(join(ROOT, "references", "visual-worlds.md"), "utf8").includes(zh))) {
      add(warns, `世界 "${id}"（${zh}）在 SKILL.md 与 visual-worlds.md 中都没提到`);
    }
  }
}

/* 6. recipes must still validate against the current matrix */
const recipeDir = join(ROOT, "recipes");
if (existsSync(recipeDir)) {
  for (const f of readdirSync(recipeDir).filter((n) => n.endsWith(".json") && !n.startsWith("_"))) {
    const r = loadJSON(join(recipeDir, f));
    const p = r?.picks;
    if (!p) { add(warns, `recipes/${f} 没有 picks，跳过`); continue; }
    if (isBanned("world", p.world)) { add(fails, `recipes/${f} 用了 banned world ${p.world}`); continue; }
    for (const axis of AXES) {
      if (axis === "world") continue;
      if (isBanned(axis, p[axis])) add(fails, `recipes/${f} 用了 banned ${axis}: ${p[axis]}`);
      const allowed = compat[p.world]?.[COMPAT_KEY[axis]];
      if (Array.isArray(allowed) && allowed.length && !allowed.includes(p[axis])) {
        add(warns, `recipes/${f} 的 ${axis} "${p[axis]}" 不在 ${p.world} 当前允许表里（牌组可能已收紧，旧配方不回改）`);
      }
    }
  }
}

const n = (s) => `${s} 张`;
console.log("registry doctor — heshao-ai-video-v1");
for (const axis of AXES) {
  console.log(`  ${axis.padEnd(10)} active ${n(activeOf(axis).length)}  banned ${n(bannedOf(axis).length)}`);
}
console.log(`  worlds in compatibility: ${Object.keys(compat).length}`);

if (warns.length) {
  console.log(`\nWARN (${warns.length})`);
  for (const w of warns) console.log("  - " + w);
}
if (fails.length) {
  console.log(`\nFAIL (${fails.length})`);
  for (const f of fails) console.log("  - " + f);
  if (!soft) {
    console.log("\n结论：牌组注册表不一致，先修完再抽配方。");
    process.exit(1);
  }
  console.log("\n结论：--soft 模式，不作为失败。");
  process.exit(0);
}
console.log("\nPASS：注册表一致（牌组 / 兼容矩阵 / 权重 / 文档计数 / 既有配方）");
