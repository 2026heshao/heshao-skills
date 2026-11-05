#!/usr/bin/env node
/**
 * heshao-ai-video-v1 · controlled randomizer
 *
 * Picks a bounded combination from curated decks, validates compatibility,
 * records a reproducible recipe, and emits prompt blocks for image/video/cover.
 *
 * Usage:
 *   node scripts/pick.mjs --project my-film --seed 20261103-a --no-history
 *   node scripts/pick.mjs --project next --base recipes/dsh-armory-depot-20261103.json --vary hook,transition
 *   node scripts/pick.mjs --validate recipes/dsh-armory-depot-20261103.json
 *   node scripts/pick.mjs --list
 *
 * Rules:
 *   - banned cards (reference-film expressions) are never picked.
 *   - with --base, at most 2 intended axes may change; the rest are locked.
 *   - if a changed world invalidates a dependent axis, it is re-picked and
 *     reported in forcedAxes.
 *   - same project + seed + args + decks/weights/history = same picks. The seed
 *     alone is NOT a recipe id: --base, --vary and --lock all change the result,
 *     and so does any new file in the history dir (they are recorded in context).
 */
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { join, resolve, basename, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const AXES = ["world", "hook", "transition", "caption", "sound", "rhythm"];
const DECK_FILE = {
  world: "worlds", hook: "hooks", transition: "transitions",
  caption: "captions", sound: "sounds", rhythm: "rhythms",
};
const COMPAT_KEY = {
  world: null, hook: "hooks", transition: "transitions",
  caption: "captions", sound: "sounds", rhythm: "rhythms",
};

function arg(name, fallback = null) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? (process.argv[i + 1] ?? true) : fallback;
}
const flag = (name) => process.argv.includes(`--${name}`);

function loadJSON(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

const decks = {};
for (const [axis, file] of Object.entries(DECK_FILE)) {
  decks[axis] = loadJSON(join(ROOT, "decks", `${file}.json`)).cards;
}
const compat = loadJSON(join(ROOT, "compatibility.json"));
const weights = loadJSON(join(ROOT, "weights.json"));

/* 牌组指纹：decks + compatibility + weights 的内容摘要。
 * 没有它，配方事后无法回答“当时那套牌组长什么样”——牌组一改，旧 seed 就悄悄不可复现。
 * 只作记录与提示，不参与默认熵源，所以引入它不会改变任何既有抽签结果。 */
function fingerprintOf(obj) {
  return createHash("sha256").update(JSON.stringify(obj)).digest("hex").slice(0, 12);
}
const DECK_FINGERPRINT = fingerprintOf({
  decks: Object.fromEntries(Object.entries(DECK_FILE).map(([axis, file]) => [axis, decks[axis]])),
  compatibility: compat,
  weights,
});

function byId(axis, id) {
  return decks[axis].find((c) => c.id === id);
}
function active(axis) {
  return decks[axis].filter((c) => !c.banned);
}
function weightOf(axis, id) {
  return Math.max(0.01, Number(weights[DECK_FILE[axis]]?.[id] ?? 1));
}

/* ---------- seeded PRNG ---------- */
function hashSeed(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ---------- history ---------- */
function readHistory(dir, lastN) {
  if (!dir || !existsSync(dir)) return { worlds: [], hooks: [], files: [] };
  const files = readdirSync(dir)
    .filter((f) => f.endsWith(".json") && !f.startsWith("_"))
    .map((f) => ({ f: join(dir, f), m: statSync(join(dir, f)).mtimeMs }))
    .sort((a, b) => b.m - a.m)
    .slice(0, lastN);
  const worlds = [], hooks = [];
  for (const { f } of files) {
    try {
      const r = JSON.parse(readFileSync(f, "utf8"));
      if (r?.picks?.world) worlds.push(r.picks.world);
      if (r?.picks?.hook) hooks.push(r.picks.hook);
    } catch {}
  }
  return { worlds, hooks, files: files.map((x) => x.f) };
}

/* ---------- pick ---------- */
function pick(axis, allowedIds, rng, { explore = weights.explore ?? 0.3, exclude = [] } = {}) {
  let ids = allowedIds.filter((id) => !exclude.includes(id));
  if (!ids.length) ids = allowedIds.slice();
  const cards = ids.map((id) => byId(axis, id)).filter(Boolean).filter((c) => !c.banned);
  if (!cards.length) throw new Error(`no active ${axis} card in allowed set: ${allowedIds.join(", ")}`);
  if (cards.length === 1) return cards[0].id;
  // epsilon-greedy: explore = uniform among allowed; exploit = weight-biased
  if (rng() < explore) return cards[Math.floor(rng() * cards.length)].id;
  let total = 0;
  const acc = cards.map((c) => { total += weightOf(axis, c.id); return total; });
  const x = rng() * total;
  for (let i = 0; i < cards.length; i++) if (x <= acc[i]) return cards[i].id;
  return cards[cards.length - 1].id;
}

function allowedFor(world, axis) {
  if (axis === "world") return active("world").map((c) => c.id);
  const list = compat[world]?.[COMPAT_KEY[axis]];
  if (Array.isArray(list) && list.length) return list.filter((id) => byId(axis, id) && !byId(axis, id).banned);
  return active(axis).map((c) => c.id);
}

function validatePicks(picks, label = "recipe") {
  const errors = [];
  const world = picks.world;
  if (!world) errors.push("missing world");
  if (world && !byId("world", world)) errors.push(`unknown world: ${world}`);
  if (world && byId("world", world)?.banned) errors.push(`banned world: ${world}`);
  for (const axis of AXES) {
    if (axis === "world") continue;
    const id = picks[axis];
    const card = id ? byId(axis, id) : null;
    if (!id) { errors.push(`missing ${axis}`); continue; }
    if (!card) { errors.push(`unknown ${axis}: ${id}`); continue; }
    if (card.banned) errors.push(`banned ${axis}: ${id}`);
    const allowed = allowedFor(world, axis);
    if (!allowed.includes(id)) errors.push(`${axis} ${id} not compatible with ${world} (allowed: ${allowed.join(", ")})`);
  }
  return errors;
}

function formatOf(format) {
  if (format === "cover-3x4") return { size: "3:4 1080x1440", w: 1080, h: 1440, kind: "cover" };
  if (format === "video-9x16") return { size: "9:16 1080x1920", w: 1080, h: 1920, kind: "video" };
  if (format === "video-4x3") return { size: "4:3 1440x1080", w: 1440, h: 1080, kind: "video" };
  return { size: format, w: null, h: null, kind: "custom" };
}

function buildPrompts(picks) {
  const w = byId("world", picks.world);
  const h = byId("hook", picks.hook);
  const t = byId("transition", picks.transition);
  const c = byId("caption", picks.caption);
  const s = byId("sound", picks.sound);
  const r = byId("rhythm", picks.rhythm);
  const palette = Object.entries(w.palette).map(([k, v]) => `${k}:${v}`).join(", ");
  return {
    image: `${w.imageDirection}. Palette ${palette}. Type ${w.type.zh}/${w.type.latin}/${w.type.mono}. Motifs: ${w.motifs.join(", ")}. Composition: leave deliberate negative space for a headline; no readable text, no logos, no letters.`,
    video: `${r.name}: ${r.beats.map((b) => b.name).join(" → ")}. Motion: ${w.motion.join(", ")}. Transition: ${t.name}. Captions: ${c.name}. Sound: ${s.name}. Hook pattern: ${h.template}. Avoid the reference film's exact copy, shot order, durations, transition combination, caption animation, motifs and SFX arrangement.`,
    cover: `${w.coverDirection}. Hook: ${h.name}. Hero motif: ${w.motifs[0]}. Brand block at bottom; keep key text in the top 75% and the right 120px clear. Render all text in HTML/SVG, not in the generated image.`,
    negative: "reference film's exact copy, shot order, durations, light sweep, halftone wipe, flash white, center keyword sticker, metal title slam, riser/whoosh/shimmer, gibberish Chinese text, logos, watermarks",
  };
}

function buildStoryboard(picks) {
  const r = byId("rhythm", picks.rhythm);
  return r.beats.map((b, i) => ({ i: i + 1, name: b.name, task: b.task, budget: b.budget }));
}

/* ---------- main ---------- */
if (flag("list")) {
  for (const axis of AXES) {
    const cards = active(axis).map((c) => `${c.id}(${weightOf(axis, c.id)})`).join(", ");
    const banned = decks[axis].filter((c) => c.banned).map((c) => c.id);
    console.log(`${axis.padEnd(10)} ${cards}${banned.length ? "  | banned: " + banned.join(", ") : ""}`);
  }
  process.exit(0);
}

if (flag("validate")) {
  const file = arg("validate");
  const r = loadJSON(resolve(file));
  const errors = validatePicks(r.picks || {}, file);
  if (errors.length) {
    console.error(`FAIL ${file}`);
    for (const e of errors) console.error("  - " + e);
    process.exit(1);
  }
  console.log(`PASS ${file}`);
  const was = r?.context?.deckFingerprint;
  if (was && was !== DECK_FINGERPRINT) {
    console.log(`NOTE 配方建档时牌组指纹 ${was}，当前牌组 ${DECK_FINGERPRINT} —— 牌组已变更，用同一 seed 重跑不保证得到同样的 picks。`);
  } else if (!was) {
    console.log(`NOTE 这份配方没有记录牌组指纹（早于 v2.1.0），无法判断当前牌组能否复现它。`);
  }
  process.exit(0);
}

const project = String(arg("project", "untitled-film"));
const date = new Date().toISOString().slice(0, 10);
const seed = String(arg("seed", `${project}-${date}`));
const format = String(arg("format", "video-4x3"));
const explore = arg("explore", null) == null ? (weights.explore ?? 0.3) : Number(arg("explore"));
const allowRepeat = flag("allow-repeat");
const noHistory = flag("no-history");
const historyDir = noHistory ? null : resolve(String(arg("history", join(ROOT, "recipes"))));
const lastN = Number(arg("last", 3));
const basePath = arg("base", null);
const varyArg = arg("vary", null);
const lockArg = arg("lock", null);
const outArg = arg("out", null);
const force = flag("force");
const jsonOnly = flag("json");
const strictSeed = flag("strict-seed");

/* 熵源默认保持 v2.0.x 的口径（project|seed|format|explore），这样引入本字段不会让任何既有
 * seed 换结果。但 seed 单独确实不是配方号：换 --base/--vary/--lock 会得到不同 picks，
 * 往 history 目录多写一份配方也会（排除集变了）。需要“参数进熵”时用 --strict-seed 显式打开。 */
let seedVector = `${project}|${seed}|${format}|${explore}`;
if (strictSeed) {
  seedVector += `|base=${basePath ?? ""}|vary=${varyArg ?? ""}|lock=${lockArg ?? ""}|hist=${historyDir ?? ""}`;
}
const rng = mulberry32(hashSeed(seedVector));
const history = readHistory(historyDir, lastN);
const excludeWorlds = allowRepeat ? [] : history.worlds;
const excludeHooks = allowRepeat ? [] : history.hooks;

let base = null;
if (basePath) {
  base = loadJSON(resolve(String(basePath)));
  if (!base?.picks) throw new Error(`base recipe has no picks: ${basePath}`);
}

// --lock must be resolved BEFORE dependent axes are drawn, otherwise the axes
// are sampled against the pre-lock world and the locked world's own options
// become structurally unreachable (or the whole combination fails validation).
const locked = {};
if (lockArg) {
  for (const pair of String(lockArg).split(",")) {
    const [k, v] = pair.split("=").map((s) => s.trim());
    if (!k || !v) continue;
    if (!AXES.includes(k)) throw new Error(`unknown lock axis: ${k}`);
    if (!byId(k, v)) throw new Error(`unknown ${k} id: ${v}`);
    if (byId(k, v).banned) throw new Error(`banned ${k} id: ${v}`);
    locked[k] = v;
  }
}

// A new world can invalidate a dependent axis; re-pick it and report it.
// Locked axes are never touched: they are the user's decision, not ours.
function repairDependentAxes() {
  for (const axis of ["hook", "transition", "caption", "sound", "rhythm"]) {
    if (locked[axis]) continue;
    const allowed = allowedFor(picks.world, axis);
    if (!allowed.includes(picks[axis])) {
      picks[axis] = pick(axis, allowed, rng, { explore });
      if (!forcedAxes.includes(axis)) forcedAxes.push(axis);
    }
  }
}

const picks = {};
const newAxes = [];
const forcedAxes = [];
let varyUsed = null;

if (!base) {
  // first campaign: pick everything, but avoid recently used worlds/hooks
  const worlds = allowedFor(null, "world").filter((id) => !excludeWorlds.includes(id));
  picks.world = locked.world
    ?? pick("world", worlds.length ? worlds : allowedFor(null, "world"), rng, { explore });
  const hookIds = allowedFor(picks.world, "hook").filter((id) => !excludeHooks.includes(id));
  picks.hook = locked.hook
    ?? pick("hook", hookIds.length ? hookIds : allowedFor(picks.world, "hook"), rng, { explore });
  for (const axis of ["transition", "caption", "sound", "rhythm"]) {
    picks[axis] = locked[axis] ?? pick(axis, allowedFor(picks.world, axis), rng, { explore });
  }
  // axes locked to a value the chosen world does not allow stay broken on purpose:
  // validatePicks below reports them instead of silently overriding the user.
  repairDependentAxes();
  newAxes.push(...AXES);
} else {
  Object.assign(picks, base.picks);
  const vary = varyArg
    ? String(varyArg).split(",").map((s) => s.trim()).filter(Boolean)
    : ["hook"];
  if (vary.length > 2) {
    console.error("FAIL: at most 2 axes may vary when --base is used");
    process.exit(1);
  }
  for (const axis of vary) {
    if (!AXES.includes(axis)) {
      console.error(`FAIL: unknown vary axis: ${axis}`);
      process.exit(1);
    }
  }
  varyUsed = vary;

  // world first, so dependent axes can be validated
  if (vary.includes("world") && !locked.world) {
    const worlds = allowedFor(null, "world").filter((id) => !excludeWorlds.includes(id) && id !== picks.world);
    picks.world = pick("world", worlds.length ? worlds : allowedFor(null, "world").filter((id) => id !== picks.world), rng, { explore });
    newAxes.push("world");
  }

  for (const axis of vary) {
    if (axis === "world") continue;
    if (locked[axis]) continue;              // an explicit lock wins over --vary
    const allowed = allowedFor(picks.world, axis);
    const exclude = allowed.includes(picks[axis]) && allowed.length > 1 ? [picks[axis]] : [];
    picks[axis] = pick(axis, allowed, rng, { explore, exclude });
    newAxes.push(axis);
  }

  // locked axes override whatever base + vary produced, then dependents are repaired
  for (const [axis, id] of Object.entries(locked)) {
    if (picks[axis] === id) continue;
    picks[axis] = id;
    if (!newAxes.includes(axis)) newAxes.push(axis);
  }

  repairDependentAxes();
}

const errors = validatePicks(picks);
if (errors.length) {
  console.error("FAIL: picked combination is invalid");
  for (const e of errors) console.error("  - " + e);
  process.exit(1);
}

const world = byId("world", picks.world);
const rhythm = byId("rhythm", picks.rhythm);
const formatInfo = formatOf(format);
const durationTarget = Math.round(rhythm.beats.reduce((a, b) => a + b.budget, 0) * 100) / 100;

const recipe = {
  version: 2,
  project,
  seed,
  created: date,
  format,
  picks,
  fixed: {
    format: formatInfo.size,
    kind: formatInfo.kind,
    fps: formatInfo.kind === "cover" ? null : 30,
    durationTarget: formatInfo.kind === "cover" ? null : durationTarget,
    qa: ["fact-table", "originality-8-axis", "pure-seek", "stereo-peak", "av-offset"],
  },
  newAxes,
  forcedAxes,
  compatibility: true,
  context: {
    base: basePath ? String(basePath) : null,
    vary: varyUsed,
    excludeWorlds,
    excludeHooks,
    locked,
    historyWindow: lastN,
    explore,
    strictSeed,
    deckFingerprint: DECK_FINGERPRINT,
    argv: process.argv.slice(2),
  },
  prompt: buildPrompts(picks),
  storyboard: formatInfo.kind === "cover" ? [] : buildStoryboard(picks),
  score: { hook: 0, thumbnail: 0, fact: 0, rhythm: 0, originality: 0, audio: 0 },
  notes: "",
};

const safeProject = String(project).replace(/[^a-zA-Z0-9\u4e00-\u9fa5._-]+/g, "-");
const safeSeed = String(seed).replace(/[^a-zA-Z0-9._-]+/g, "-");
// the default seed already begins with the project name, so concatenating both
// produced doubled names like "dsh-armory-atlas-dsh-armory-atlas-2026-11-04.json"
const recipeName = safeSeed.startsWith(`${safeProject}-`) ? safeSeed : `${safeProject}-${safeSeed}`;
let out = outArg ? resolve(String(outArg)) : join(ROOT, "recipes", `${recipeName}.json`);
if (existsSync(out) && !force) {
  const stem = out.replace(/\.json$/, "");
  let n = 2;
  while (existsSync(`${stem}-${n}.json`)) n++;
  out = `${stem}-${n}.json`;
}
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(recipe, null, 2) + "\n", "utf8");

if (jsonOnly) {
  console.log(JSON.stringify(recipe, null, 2));
} else {
  console.log(`project      ${project}`);
  console.log(`seed         ${seed}  (needs same project+args+decks/history to reproduce)`);
  console.log(`decks        fingerprint ${DECK_FINGERPRINT}${strictSeed ? "  [strict-seed: 参数已进熵源]" : ""}`);
  console.log(`world        ${world.name} (${picks.world})`);
  console.log(`hook         ${byId("hook", picks.hook).name} (${picks.hook})`);
  console.log(`transition   ${byId("transition", picks.transition).name} (${picks.transition})`);
  console.log(`caption      ${byId("caption", picks.caption).name} (${picks.caption})`);
  console.log(`sound        ${byId("sound", picks.sound).name} (${picks.sound})`);
  console.log(`rhythm       ${rhythm.name} (${picks.rhythm})  ~${durationTarget}s`);
  console.log(`newAxes      ${newAxes.join(", ") || "none"}`);
  console.log(`forcedAxes   ${forcedAxes.join(", ") || "none"}`);
  console.log(`compatible   yes`);
  console.log(`recipe       ${out}`);
}
