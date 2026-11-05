#!/usr/bin/env node
/**
 * heshao-ai-video-v1 · 交付反馈 / 经验账本
 *
 * 只做三件事：按统一 schema 新建一条经验、校验、重建索引。
 * 不自动改 SKILL.md / references / decks / weights —— 规则升级必须人工确认。
 *
 * usage:
 *   node scripts/feedback.mjs --new --project dsh-armory-atlas \
 *     --recipe recipes/dsh-armory-atlas-20261104a.json \
 *     --score 8.5 --tags "视觉,音频" \
 *     --summary "星图比喻合同 + 单句气口换 take" \
 *     --quote "这版可以，星图是看法这句说清楚了" --generalizable
 *
 *   node scripts/feedback.mjs --prompt   # 打印交付后的 3+1 回访话术
 *   node scripts/feedback.mjs --validate
 *   node scripts/feedback.mjs --index
 *   node scripts/feedback.mjs --list
 *   node scripts/feedback.mjs --candidates
 *
 * 可选：--root <dir> 指定技能根目录（默认脚本上一级），方便自测。
 */
import { existsSync, readFileSync, readdirSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const argv = process.argv.slice(2);
const has = (k) => argv.includes("--" + k);
const val = (k, d = "") => {
  const i = argv.indexOf("--" + k);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : d;
};
const ROOT = resolve(val("root", SCRIPT_ROOT));
const EXP = join(ROOT, "experiences");
const INDEX = join(EXP, "INDEX.md");
const VERDICTS = ["success", "conditional", "fail", "unrated"];
const PROMOTIONS = ["none", "candidate", "promoted", "reverted"];
const REQUIRED = ["date", "project", "recipe", "score", "verdict", "hardFail",
  "tags", "generalizable", "promotion", "summary", "userQuote"];

const now = new Date();
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
const slug = (s) => String(s).trim().replace(/[\\/:*?"<>|\s]+/g, "-").replace(/^-+|-+$/g, "") || "film";

function fail(msg) {
  console.error("FAIL: " + msg);
  process.exit(1);
}

function ensureDir() {
  mkdirSync(EXP, { recursive: true });
}

function parseEntry(file) {
  const text = readFileSync(file, "utf8");
  const m = text.match(/```json\s*([\s\S]*?)```/);
  if (!m) return { text, data: null, error: "缺少 ```json 数据块" };
  try {
    return { text, data: JSON.parse(m[1]) };
  } catch (e) {
    return { text, data: null, error: "JSON 解析失败：" + e.message };
  }
}

function entries() {
  ensureDir();
  return readdirSync(EXP)
    .filter((f) => /^\d{4}-\d{2}-\d{2}-.*\.md$/.test(f))
    .sort()
    .map((f) => ({ file: f, ...parseEntry(join(EXP, f)) }));
}

function validateOne(file, data) {
  const errs = [];
  if (!data) return ["JSON 数据块缺失"];
  for (const k of REQUIRED) if (!(k in data)) errs.push(`缺字段 ${k}`);
  if (data.date && !/^\d{4}-\d{2}-\d{2}$/.test(data.date)) errs.push("date 必须是 YYYY-MM-DD");
  if (data.score !== null && (typeof data.score !== "number" || data.score < 0 || data.score > 10)) {
    errs.push("score 必须是 0–10 或 null");
  }
  if (!VERDICTS.includes(data.verdict)) errs.push("verdict 非法");
  if (typeof data.hardFail !== "boolean") errs.push("hardFail 必须是布尔");
  if (!Array.isArray(data.tags)) errs.push("tags 必须是数组");
  if (typeof data.generalizable !== "boolean") errs.push("generalizable 必须是布尔");
  if (!PROMOTIONS.includes(data.promotion)) errs.push("promotion 非法");
  if (typeof data.summary !== "string") errs.push("summary 必须是字符串");
  if (typeof data.userQuote !== "string") errs.push("userQuote 必须是字符串");
  if (data.recipe && data.recipe !== "manual" && !existsSync(join(ROOT, data.recipe))) {
    errs.push(`recipe 不存在：${data.recipe}`);
  }
  if (data.duration !== null && data.duration !== undefined &&
      (typeof data.duration !== "number" || data.duration <= 0)) {
    errs.push("duration 必须是正数或 null");
  }
  if (data.changes !== undefined && !Array.isArray(data.changes)) errs.push("changes 必须是数组");
  if (data.reverted !== undefined && typeof data.reverted !== "boolean") errs.push("reverted 必须是布尔");
  // 交叉一致性：硬失败优先于分数，避免把 9 分 + 削顶记成 success
  if (data.hardFail && data.verdict !== "fail") errs.push("hardFail=true 时 verdict 必须是 fail");
  if (data.verdict === "success" && data.score !== null && data.score < 8) {
    errs.push("success 需要 score ≥8 或无分数");
  }
  if (data.verdict === "conditional" && data.score !== null && (data.score < 6 || data.score >= 8)) {
    errs.push("conditional 需要 6≤score<8 或无分数");
  }
  if (data.verdict === "fail" && !data.hardFail && data.score !== null && data.score >= 6) {
    errs.push("fail 需要 hard-fail 或 score<6");
  }
  if (data.verdict === "unrated" && data.score !== null) errs.push("unrated 不应带 score");
  if (data.promotion === "candidate" && !(data.verdict === "success" && data.generalizable)) {
    errs.push("candidate 需要 success + generalizable");
  }
  return errs;
}

function writeIndex() {
  const rows = entries().filter((e) => e.data).sort((a, b) => (a.data.date < b.data.date ? 1 : -1));
  const lines = [
    "# 经验索引 / Experience Index",
    "",
    "> 由 `node scripts/feedback.mjs --index` 生成，不要手改。",
    "> 单次反馈只写案例；`candidate` 需 2 个独立项目或用户明确要求，并经人工确认 diff 后才能升级为规则。",
    "> 规则升级后：同步 bump `SKILL.md` 版本 + 写 `CHANGELOG.md`，并在本表把 `candidate` 改为 `promoted`。",
    "",
    "| 日期 | 项目 | 评分 | 结论 | 标签 | 沉淀 | 文件 |",
    "|---|---|---:|---|---|---|---|",
  ];
  if (!rows.length) {
    lines.push("| — | — | — | — | — | — | — |");
  } else {
    for (const e of rows) {
      const d = e.data;
      lines.push(`| ${d.date} | ${d.project} | ${d.score ?? "—"} | ${d.verdict}${d.hardFail ? " · hard-fail" : ""} | ${(d.tags || []).join(" / ")} | ${d.promotion} | [${e.file}](${e.file}) |`);
    }
  }
  lines.push("");
  writeFileSync(INDEX, lines.join("\n"), "utf8");
  console.log("INDEX ->", INDEX);
}

function newEntry() {
  const project = val("project");
  if (!project) fail("--new 需要 --project");
  const recipe = val("recipe", "manual");
  const rawScore = val("score", "");
  const score = rawScore === "" ? null : Number(rawScore);
  if (score !== null && (!Number.isFinite(score) || score < 0 || score > 10)) fail("--score 必须是 0–10");
  const hardFail = has("hard-fail");
  let verdict = val("verdict");
  if (hardFail) {
    if (verdict && verdict !== "fail") fail("--hard-fail 时只能记 fail");
    verdict = "fail";
  }
  if (!verdict) verdict = score === null ? "unrated" : score >= 8 ? "success" : score >= 6 ? "conditional" : "fail";
  if (!VERDICTS.includes(verdict)) fail("--verdict 非法");
  const generalizable = has("generalizable");
  let promotion = val("promotion");
  if (!promotion) promotion = verdict === "success" && generalizable ? "candidate" : "none";
  if (!PROMOTIONS.includes(promotion)) fail("--promotion 非法");
  const rawDuration = val("duration", "");
  const duration = rawDuration === "" ? null : Number(rawDuration);
  if (duration !== null && (!Number.isFinite(duration) || duration <= 0)) fail("--duration 必须是正数");
  const tags = val("tags").split(",").map((s) => s.trim()).filter(Boolean);
  const data = {
    date: today,
    project,
    recipe,
    format: val("format", ""),
    duration,
    score,
    verdict,
    hardFail,
    tags,
    generalizable,
    promotion,
    summary: val("summary"),
    userQuote: val("quote"),
    changes: [],
    reverted: false,
  };
  const errs = validateOne("", data);
  if (errs.length) fail(errs.join("；"));

  ensureDir();
  let file = `${today}-${slug(project)}.md`;
  let n = 2;
  while (existsSync(join(EXP, file)) && !has("force")) {
    file = `${today}-${slug(project)}-${n++}.md`;
  }
  const body = `# ${today} · ${project}

\`\`\`json
${JSON.stringify(data, null, 2)}
\`\`\`

## 这次做对了什么

- 

## 下次怎么复用

- 

## 如果重做

- 
`;
  writeFileSync(join(EXP, file), body, "utf8");
  console.log("NEW ->", join(EXP, file));
  writeIndex();
  console.log("下一步：填完三节正文，跑 --validate。");
}

function promptText() {
  console.log(`成片和验收结果在上面。如果方便，给我三个反馈：
1）整体 0–10 分（≥8 很好 / 6–7 可用 / <6 不行）；
2）最想保留的一点（钩子 / 节奏 / 视觉 / 文案 / 声音 / 封面 / 工程）；
3）最想改的一点（能指到秒数或某一幕最好）。
这次经验想怎么沉淀：仅本次 / 可复用 / 可直接改规则。不想评也行，我标记 unrated。`);
}

function validateAll() {
  const list = entries();
  if (!list.length) {
    console.log("没有经验文件（experiences/*.md），跳过。");
    return;
  }
  let bad = 0;
  for (const e of list) {
    const errs = e.error ? [e.error] : validateOne(e.file, e.data);
    if (errs.length) {
      bad++;
      console.log(`  ✗ ${e.file}  ${errs.join("；")}`);
    } else {
      console.log(`  ✓ ${e.file}`);
    }
  }
  if (bad) fail(`${bad} 个文件不合格`);
  console.log("PASS：经验账本一致");
}

function list() {
  const rows = entries().filter((e) => e.data).sort((a, b) => (a.data.date < b.data.date ? 1 : -1));
  if (!rows.length) return console.log("（空）");
  console.log("date        project                  score  verdict      promotion  tags");
  for (const e of rows) {
    const d = e.data;
    console.log(`${d.date}  ${String(d.project).padEnd(22)}  ${String(d.score ?? "—").padEnd(5)}  ${String(d.verdict).padEnd(11)}  ${String(d.promotion).padEnd(9)}  ${(d.tags || []).join(",")}`);
  }
}

function candidates() {
  const rows = entries().filter((e) => e.data && e.data.promotion === "candidate");
  if (!rows.length) return console.log("没有待升级的 candidate。");
  for (const e of rows) {
    console.log(`\n${e.data.date} · ${e.data.project} · ${e.data.score ?? "—"}`);
    console.log(`  ${e.data.summary}`);
    console.log(`  ${e.file}`);
  }
  console.log("\n升级前：至少 2 个独立项目重复，或用户明确要求；先给用户看 diff，再改规则并 bump 版本。");
}

if (has("new")) newEntry();
else if (has("prompt")) promptText();
else if (has("validate")) validateAll();
else if (has("index")) writeIndex();
else if (has("list")) list();
else if (has("candidates")) candidates();
else {
  console.log(`feedback.mjs · 经验账本

  --new --project <name> [--recipe <path>] [--score 0-10]
        [--verdict success|conditional|fail|unrated] [--hard-fail]
        [--tags a,b] [--summary "..."] [--quote "..."] [--generalizable]
        [--promotion none|candidate|promoted|reverted] [--force]
  --prompt       打印交付后的 3+1 回访话术
  --validate     校验 experiences/*.md
  --index        重建 experiences/INDEX.md
  --list         列出全部经验
  --candidates   列出待升级的规则候选

只写案例，不自动改规则。`);
}
