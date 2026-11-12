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
 * It also guards two things that drifted silently in the past:
 *   - 原创性轴数口径（SKILL.md 声明 / originality-gates 表行 / 配方 qa 标签 /
 *     pick.mjs 生成标签 四处必须相等；历史的 originality-8-axis 会被判 FAIL）
 *   - 配方 deliverables 的路径根（产物在技能包外的影片工程里，必须声明
 *     projectRoot，且不许写绝对路径 —— 否则换机器就是一条悬空链接）
 * 以及 v2.2.0 的新层：
 *   - decks/proposals/ 试用卡（联网第二熵源）：必须自带 compat 与来源证据，
 *     不许与正式卡撞 id
 *   - 配方的 Phase 0.5 选路留痕（fit / research）：用了哪条熵源、为什么，得能查
 *
 *   node scripts/doctor.mjs          # FAIL on structural breakage
 *   node scripts/doctor.mjs --soft   # report everything as WARN only
 *   node scripts/doctor.mjs --root <dir>   # 体检别的目录树（用于坏例自测）
 */
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

function argVal(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : null;
}
const ROOT = resolve(argVal("root") ?? dirname(dirname(fileURLToPath(import.meta.url))));
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

/* 5b. 牌组清单文档里的张数必须等于实测，且宪法得写出 L1.5 这层 */
{
  const crPath = join(ROOT, "references", "controlled-randomness.md");
  const fileToAxis = Object.fromEntries(Object.entries(DECK_FILE).map(([axis, file]) => [file, axis]));
  if (existsSync(crPath)) {
    const g = readFileSync(crPath, "utf8");
    for (const m of g.matchAll(/^\s*(\w+)\.json\s+(\d+)\s*[个种]([^\n]*)/gm)) {
      const [, base, count, rest] = m;
      const axis = fileToAxis[base];
      if (!axis) continue;
      if (Number(count) !== activeOf(axis).length) {
        add(fails, `controlled-randomness.md 的牌组清单写 "${base}.json ${count} 个/种"，decks/${base}.json 实际 active ${activeOf(axis).length} 张`);
      }
      const bm = rest.match(/（\+\s*(\d+)\s*张/);
      if (bm && Number(bm[1]) !== bannedOf(axis).length) {
        add(fails, `controlled-randomness.md 写 "${base}.json 禁用 ${bm[1]} 张"，实际 banned ${bannedOf(axis).length} 张`);
      }
    }
  }
  if (existsSync(skillPath)) {
    const t = readFileSync(skillPath, "utf8");
    /* 断言要指到具体锚点：只查 "L1.5" 这种子串，删掉一条 bullet 还剩一条，闸门会假绿 */
    if (!/\*\*L1\.5 试用卡\*\*/.test(t)) add(fails, "SKILL.md §0 的分层里没有「**L1.5 试用卡**」—— 代码实现了但宪法没这一层，下一个人只会看到 7 个世界然后硬抽");
    if (!/### Phase 0\.5 —/.test(t)) add(fails, "SKILL.md 没有「### Phase 0.5 —」这个阶段：「先看产品再选熵源」没落进流程");
    if (!/decks\/proposals/.test(t)) add(fails, "SKILL.md 没提 decks/proposals/，试用卡机制对使用者不可见");
    if (!/product-fit-and-routing/.test(t)) add(fails, "SKILL.md §7 没索引 references/product-fit-and-routing.md");
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

/* 7. 原创性轴数口径：一处声明，四处必须相等 */
{
  const declared = { count: null, listed: null };
  if (existsSync(skillPath)) {
    const m = readFileSync(skillPath, "utf8").match(/（\s*(\d+)\s*个轴：([^）]+)）/);
    if (m) {
      declared.count = Number(m[1]);
      declared.listed = m[2].split(/[、,]/).filter((s) => s.trim()).length;
    }
  }
  if (declared.count == null) {
    add(warns, "SKILL.md 找不到「（N 个轴：…）」这句，无法核对原创性轴数口径");
  } else {
    if (declared.listed !== declared.count) {
      add(fails, `SKILL.md 声明 ${declared.count} 个轴，但括号里只列了 ${declared.listed} 个 —— 口径自相矛盾`);
    }
    const gatesPath = join(ROOT, "references", "originality-gates.md");
    if (existsSync(gatesPath)) {
      const g = readFileSync(gatesPath, "utf8");
      const sec = g.split(/^##\s/m).find((s) => /轴矩阵/.test(s.slice(0, 40))) || "";
      const rows = [...sec.matchAll(/^\|\s*(\d+)\s*\|/gm)].map((x) => Number(x[1]));
      if (!rows.length) {
        add(warns, "references/originality-gates.md 的矩阵表读不到行号，无法核对轴数");
      } else if (rows.length !== declared.count || rows[rows.length - 1] !== declared.count) {
        add(fails, `originality-gates.md 矩阵表有 ${rows.length} 行（末行 ${rows[rows.length - 1]}），SKILL.md 声明 ${declared.count} 个轴`);
      }
    }
    const pickPath = join(ROOT, "scripts", "pick.mjs");
    if (existsSync(pickPath)) {
      const labels = [...readFileSync(pickPath, "utf8").matchAll(/originality-(\d+)-axis/g)].map((x) => Number(x[1]));
      for (const n of labels) {
        if (n !== declared.count) {
          add(fails, `pick.mjs 生成的配方标签是 originality-${n}-axis，与声明的 ${declared.count} 轴不符（生成器比旧配方更危险：它会污染之后每一支片子）`);
        }
      }
      if (!labels.length) add(warns, "pick.mjs 里找不到 originality-N-axis 标签，口径核对落空");
    }
    if (existsSync(recipeDir)) {
      for (const f of readdirSync(recipeDir).filter((n) => n.endsWith(".json") && !n.startsWith("_"))) {
        const qa = loadJSON(join(recipeDir, f))?.fixed?.qa || [];
        for (const label of qa.filter((s) => /^originality-\d+-axis$/.test(String(s)))) {
          const n = Number(label.match(/\d+/)[0]);
          if (n !== declared.count) {
            add(fails, `recipes/${f} 的 fixed.qa 仍是 "${label}"（${n} 轴），当前口径 ${declared.count} 轴 —— 旧标签别留给下一个人猜`);
          }
        }
      }
    }
  }
}

/* 8. deliverables 必须说清相对哪个工程根：产物在技能包外，不写根等于悬空链接 */
{
  const META_KEYS = new Set(["projectRoot", "pathRule", "verified", "note", "notes"]);
  if (existsSync(recipeDir)) {
    for (const f of readdirSync(recipeDir).filter((n) => n.endsWith(".json") && !n.startsWith("_"))) {
      const d = loadJSON(join(recipeDir, f))?.deliverables;
      if (!d || typeof d !== "object") continue;
      const artifacts = Object.entries(d).filter(([k, v]) => !META_KEYS.has(k) && typeof v === "string" && v.trim());
      if (!artifacts.length) continue;
      const rootName = typeof d.projectRoot === "string" ? d.projectRoot.trim() : "";
      if (!rootName) {
        add(fails, `recipes/${f} 的 deliverables 列了 ${artifacts.length} 个产物却没声明 projectRoot —— 这些是技能包外影片工程的相对路径，没根就没法解析（换机器即失效）`);
        continue;
      }
      if (!d.pathRule) add(warns, `recipes/${f} 的 deliverables 没写 pathRule（一句话说明路径相对谁解析即可）`);
      for (const [key, val] of artifacts) {
        if (/^([a-zA-Z]:[\\/]|[\\/])/.test(val)) {
          add(fails, `recipes/${f} 的 deliverables.${key} 是绝对路径 "${val}"：改机器/改用户名就失效，应相对 projectRoot "${rootName}"`);
        }
        if (val.startsWith(`${rootName}/`) || val.startsWith(`${rootName}\\`)) {
          add(fails, `recipes/${f} 的 deliverables.${key} 把 projectRoot 重复拼进路径了（"${val}"），路径应相对 projectRoot`);
        }
        if (existsSync(join(ROOT, val))) {
          add(fails, `recipes/${f} 的 deliverables.${key} 落在技能包内（${val}）—— 成片/素材不进技能包，应放影片工程目录`);
        }
      }
    }
  }
}

/* 9. 试用卡（decks/proposals/）：联网这条第二熵源的落地容器，必须自带证据与兼容矩阵 */
const proposals = {};
{
  const dir = join(ROOT, "decks", "proposals");
  if (existsSync(dir)) {
    for (const f of readdirSync(dir).filter((n) => n.endsWith(".json") && !n.startsWith("_"))) {
      const tag = `decks/proposals/${f}`;
      let o;
      try { o = loadJSON(join(dir, f)); } catch (e) { add(fails, `${tag} 解析失败：${e.message}`); continue; }
      const axis = o.kind || "world";
      if (!AXES.includes(axis)) { add(fails, `${tag}: kind "${axis}" 不是合法轴`); continue; }
      if (!o.id || !o.card) { add(fails, `${tag}: 缺 id 或 card`); continue; }
      if (o.id !== o.card.id) add(fails, `${tag}: id "${o.id}" 与 card.id "${o.card.id}" 不一致`);
      if (idsOf(axis).includes(o.id)) {
        add(fails, `${tag}: "${o.id}" 与正式牌组同名 —— 试用期卡不许覆盖或蹭正式卡，要共用就走进 references/product-fit-and-routing.md §5 的转正五步`);
      }
      if (proposals[`${axis}:${o.id}`]) add(fails, `${tag}: 与 ${proposals[`${axis}:${o.id}`].file} 撞 id`);
      if (o.card.banned) add(fails, `${tag}: 试用卡不能标 banned（banned 只用于对照审计）`);
      if (axis === "world") {
        if (!o.compat) {
          add(fails, `${tag}: 试用世界没带 compat —— pick.mjs 的 allowedFor() 会静默放开整副牌组，兼容矩阵形同不存在`);
        } else {
          for (const [key, list] of Object.entries(o.compat)) {
            if (key.startsWith("_")) continue;
            const depAxis = Object.keys(COMPAT_KEY).find((a) => COMPAT_KEY[a] === key);
            if (!depAxis) { add(fails, `${tag}: compat 出现未知分组 "${key}"`); continue; }
            if (!Array.isArray(list) || !list.length) { add(fails, `${tag}: compat.${key} 必须是非空数组`); continue; }
            for (const id of list) {
              const card = decks[depAxis].find((c) => c.id === id) || proposals[`${depAxis}:${id}`]?.card;
              if (!card) add(fails, `${tag}: compat.${key} 引用了牌组里不存在的 "${id}"`);
              else if (card.banned) add(fails, `${tag}: compat.${key} 允许了 banned 卡 "${id}"`);
            }
          }
        }
      }
      if (!o.source?.urls?.length) add(fails, `${tag}: 缺 source.urls —— 联网检索每次结果都不同，没有来源这张卡日后无法审计，也没法判断是不是重复搜过`);
      if (!o.source?.evidence) add(fails, `${tag}: 缺 source.evidence（原文摘要或截图路径）—— 只留 URL 等于什么都没留，页面会改会删`);
      if (!o.trialFor) add(warns, `${tag}: 没写 trialFor，等于对所有项目开放，绕过了试用期范围`);
      if (!o.whyLocalDeckFailed) add(warns, `${tag}: 没写为什么本地牌组承载不了这个产品（Phase 0.5 的判定理由）`);
      if (!o.promoteWhen) add(warns, `${tag}: 没写转正条件，这张卡会一直赖在 proposals 里`);
      proposals[`${axis}:${o.id}`] = { file: tag, compat: o.compat, card: o.card, trialFor: o.trialFor };
    }
  }
}

/* 10. 选路留痕：配方要能被后人读出"当时为什么这么抽" */
{
  const VERDICTS = ["local", "trial", "handmade", "TBD"];
  if (existsSync(recipeDir)) for (const f of readdirSync(recipeDir).filter((n) => n.endsWith(".json") && !n.startsWith("_"))) {
    const r = loadJSON(join(recipeDir, f));
    const p = r?.picks;
    if (!p) continue;
    /* 10a. picks 里引用了试用卡，就必须有对应的试用卡文件与记录 */
    const trialRefs = AXES.filter((a) => p[a] && !idsOf(a).includes(p[a]) && proposals[`${a}:${p[a]}`]);
    const dangling = AXES.filter((a) => p[a] && !idsOf(a).includes(p[a]) && !proposals[`${a}:${p[a]}`]);
    for (const a of dangling) {
      add(fails, `recipes/${f} 的 ${a} "${p[a]}" 既不在正式牌组也不在 decks/proposals/ —— 这支配方现在无法复现，试用卡文件被删了？`);
    }
    if (trialRefs.length) {
      const listed = (r?.research?.trialDecks || []).map(String);
      for (const a of trialRefs) {
        const file = proposals[`${a}:${p[a]}`].file;
        if (!listed.includes(file)) {
          add(fails, `recipes/${f} 用了试用卡 ${file}，但 research.trialDecks 没记它（抽的时候请用 --deck，配方会自动记）`);
        }
        const need = proposals[`${a}:${p[a]}`].trialFor;
        if (need && r?.project && need !== r.project) {
          add(warns, `recipes/${f} 用了声明给项目 "${need}" 的试用卡，本项目是 "${r.project}" —— 试用期卡跨项目复用前应先转正`);
        }
      }
      if (r?.fit && r.fit.verdict === "local") {
        add(fails, `recipes/${f} 的 fit.verdict 写 local，但 picks 里有试用卡 —— 判定与实际用的熵源不一致`);
      }
    }
    /* 10b. fit 字段本身 */
    const fit = r?.fit;
    if (!fit) {
      add(warns, `recipes/${f} 没有 fit 字段（v2.2.0 之前的老配方，或 Phase 0.5 还没落判）—— 交付前补上：verdict / reason / productActions`);
      continue;
    }
    if (!VERDICTS.includes(fit.verdict)) {
      add(fails, `recipes/${f} 的 fit.verdict "${fit.verdict}" 非法，只能是 local / trial / handmade（TBD 表示还没判）`);
    } else if (fit.verdict === "TBD") {
      add(warns, `recipes/${f} 的 Phase 0.5 判定还没填（fit.verdict 仍是 TBD）；交付前判成 local / trial / handmade`);
    } else if (!fit.reason) {
      add(fails, `recipes/${f} 的 fit 判成了 ${fit.verdict} 却没写 reason —— 判定要留一句可查的理由，不然下个人只能猜`);
    }
    if (fit.verdict === "trial" && !r?.research?.trialDecks?.length) {
      add(fails, `recipes/${f} 判为 trial 却没有 research.trialDecks —— 联网这条熵源必须留下试用卡文件，否则这支配方不可复现`);
    }
    if (fit.verdict === "local" && r?.research?.used === true && !r?.research?.trialDecks?.length) {
      add(warns, `recipes/${f} 判为 local 却记 research.used=true 且没有试用卡：确认是不是把「调研产品」和「找新表达卡」混在了一次检索里`);
    }
    if (Array.isArray(fit.rejectedCards)) {
      for (const rc of fit.rejectedCards) {
        if (!rc?.id || !rc?.why) add(fails, `recipes/${f} 的 fit.rejectedCards 有条目缺 id/why —— 拒掉一张卡要写下为什么`);
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
console.log(`  trial cards (decks/proposals): ${Object.keys(proposals).length} 张${Object.keys(proposals).length ? " → " + Object.keys(proposals).join(", ") : "（联网第二熵源当前没有存货）"}`);

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
console.log("\nPASS：注册表一致（牌组 / 兼容矩阵 / 权重 / 文档计数 / 既有配方 / 轴数口径 / 产物路径根 / 试用卡 / 选路留痕）");
