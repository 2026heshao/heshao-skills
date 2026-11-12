#!/usr/bin/env node
/**
 * heshao-ai-video-v1 · 逐帧渲染 + 旁白/音效合成
 *
 * 从 references/audio-and-render.md §6 与 references/preview-contract.md §8 的契约出发，
 * 把舞台推到确定时刻再截图：renderAt(t) 是纯函数，所以成片每一帧都和网页里看到的同一
 * 时刻完全相同；播放器倍速不参与导出。声音不经过浏览器：一条旁白 + SFX 事件表，事件按
 * ceil(t*fps)/fps 量化到帧边界后用 adelay 钉住，再与旁白 amix=normalize=0 相加。
 *
 * usage:
 *   node scripts/render.mjs --preflight          # 只查工具链，开工前先跑这个
 *   node scripts/render.mjs                      # 全片：读 meta → 截帧 → 混音 → 编码
 *   node scripts/render.mjs --meta-only          # 只把 meta（含 SFX 事件表）写出来
 *   node scripts/render.mjs --frames-only        # 只截图，已存在的帧跳过
 *   node scripts/render.mjs --audio-only         # 只产 audio-check.wav + 峰值报告
 *   node scripts/render.mjs --encode-only        # 只用 meta 合成，不再开浏览器
 *   node scripts/render.mjs --from 34 --to 41 --keep   # 只截一段调试并保留 PNG
 *   node scripts/render.mjs --help                     # 只打印用法（退出码 2，不开渲）
 *
 * 常用开关：
 *   --root <dir>        工程根目录，页面与素材都相对它解析（默认当前目录）
 *   --html <file>       预览页（默认 <root>/preview.html）
 *   --out-dir <dir>     成片与 meta 目录（默认 <root>/out/final）
 *   --frames-dir <dir>  PNG 帧目录（默认 <root>/out/frames）
 *   --out <file>        成片文件名（默认 film.mp4）
 *   --edge | --ffmpeg   显式指定二进制，绕过自动探测
 *   --encoder auto|nvenc|x264   默认 auto：有 h264_nvenc 就用，失败自动降级 libx264
 *   --width/--height    视口，默认 1440/1080（4:3 舞台）
 *   --resume-anyway     帧目录已有 PNG 且输入指纹变了时，仍然复用旧帧续跑（默认拒绝）
 *
 * 未知参数一律打印用法并退出 2 —— 以前 --help 会被忽略，直接开渲整片并覆写出品。
 *
 * 只启动/结束自己拉起的 Edge（按 PID kill），不碰系统上其他浏览器进程。
 * 不用 ffprobe：元信息一律从 ffmpeg 自己的输出解析（很多精简构建不带 ffprobe）。
 */
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir, homedir } from "node:os";
import { join, resolve, isAbsolute } from "node:path";
import { pathToFileURL } from "node:url";

/* ---------------- CLI ---------------- */
const argv = process.argv.slice(2);
const has = (k) => argv.includes("--" + k);
const val = (k, d) => { const i = argv.indexOf("--" + k); return i >= 0 && !String(argv[i + 1] || "").startsWith("--") ? argv[i + 1] : d; };

/* 参数白名单：未知 flag 以前会被静默忽略 —— 实测 `--help` 不打印用法，而是按默认参数
   直接开渲 1322 帧并覆写 out/final/film.mp4。一次拼错就是 7 分钟 + 覆盖出品，
   所以未知参数必须退出，且不能进入任何渲染分支。 */
const KNOWN_FLAGS = ["preflight", "frames-only", "audio-only", "encode-only", "meta-only",
  "keep", "help", "h", "resume-anyway", "root", "html", "out-dir", "frames-dir", "out",
  "encoder", "width", "height", "from", "to", "force-stale-meta"];
const VALUE_FLAGS = new Set(["root", "html", "out-dir", "frames-dir", "out", "edge", "ffmpeg",
  "encoder", "width", "height", "from", "to"]);
const unknown = [];
for (let i = 0; i < argv.length; i++) {
  const a = String(argv[i]);
  if (!a.startsWith("--")) continue;
  const name = a.slice(2);
  if (!KNOWN_FLAGS.includes(name)) { unknown.push(a); continue; }
  if (VALUE_FLAGS.has(name)) i++;   // 跳过它的取值，取值本身不算 flag
}
if (has("help") || has("h") || unknown.length) {
  console.log(unknown.length
    ? `未知参数：${unknown.join(" ")}\n（未知参数不会开始渲染 —— 以前 --help 会被忽略并直接开渲整片）\n`
    : "");
  console.log(`usage: node scripts/render.mjs [--preflight | --meta-only | --frames-only | --audio-only | --encode-only | --from <s> --to <s> --keep] [--resume-anyway]\n` +
    `       --root <dir> --html preview.html --out-dir out/final --frames-dir out/frames --out film.mp4\n` +
    `       --edge <exe> --ffmpeg <exe> --encoder auto|nvenc|x264 --width 1440 --height 1080\n` +
    `默认（不带模式开关）= 全片：读 meta → 截帧 → 混音 → 编码。帧目录有旧帧且输入指纹不符时会拒绝续跑。`);
  process.exit(2);
}

const FRAMES_ONLY = has("frames-only");
const ENCODE_ONLY = has("encode-only");
const AUDIO_ONLY = has("audio-only");
const META_ONLY = has("meta-only");
const KEEP_FRAMES = has("keep") || FRAMES_ONLY;   // 单截帧默认保留，方便人工看构图
const PREFLIGHT = has("preflight");
const RESUME_ANYWAY = has("resume-anyway");

const ROOT = resolve(String(val("root", ".")));
const PAGE = isAbsolute(String(val("html", "preview.html"))) ? String(val("html")) : resolve(ROOT, String(val("html", "preview.html")));
const OUT_DIR = resolveIn(String(val("out-dir", "out/final")));
const FRAMES = resolveIn(String(val("frames-dir", "out/frames")));
const OUT = join(OUT_DIR, String(val("out", "film.mp4")));
const META = join(OUT_DIR, "meta.json");
const AUDIOTEST = join(OUT_DIR, "audio-check.wav");
const SFXTEST = join(OUT_DIR, "sfx-only.wav");
const WIDTH = Number(val("width", 1440));
const HEIGHT = Number(val("height", 1080));
const ENCODER_PREF = String(val("encoder", "auto"));

function resolveIn(p) { return isAbsolute(p) ? p : resolve(ROOT, p); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---------------- 工具链探测 ---------------- */
/* 技能包默认假设 ffmpeg / Edge 在 PATH 上，但本机它们都不在 PATH —— 缺一步就会在
   截了几百帧之后才崩。所以开工前先解析清楚，解析不到就立刻报，并把可指的路径说明白。 */
const EDGE_CANDIDATES = [
  process.env.PROMO_EDGE,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
].filter(Boolean);

function ffCandidates() {
  const list = [process.env.PROMO_FFMPEG, "ffmpeg"];
  // 剪映自带一个可用的 ffmpeg（含 h264_nvenc），版本号会变，所以按目录名降序取最新的
  const jy = join(homedir(), "AppData", "Local", "JianyingPro", "apps");
  if (existsSync(jy)) {
    for (const d of readdirSync(jy).sort().reverse()) {
      const p = join(jy, d, "ffmpeg.exe");
      if (existsSync(p)) list.push(p);
    }
  }
  list.push(join(homedir(), "AppData", "Local", "Microsoft", "WinGet", "Links", "ffmpeg.exe"));
  return list.filter(Boolean);
}

function which(cmd) {
  const r = spawnSync(process.platform === "win32" ? "where" : "which", [cmd], { encoding: "utf8" });
  return r.status === 0 ? r.stdout.split(/\r?\n/).map((s) => s.trim()).find(Boolean) : null;
}

function resolveFFmpeg() {
  for (const c of ffCandidates()) {
    if (c !== "ffmpeg" && !existsSync(c)) continue;
    const probe = spawnSync(c === "ffmpeg" ? "ffmpeg" : c, ["-hide_banner", "-encoders"], { encoding: "utf8" });
    if (probe.status === 0) return { bin: c === "ffmpeg" ? "ffmpeg" : c, encoders: probe.stdout || "" };
  }
  return null;
}

function resolveBrowser() {
  for (const c of EDGE_CANDIDATES) if (existsSync(c)) return c;
  return which("msedge") || which("chrome") || null;
}

const FF_INFO = resolveFFmpeg();
const FF = FF_INFO ? FF_INFO.bin : null;
const BROWSER = resolveBrowser();

function toolchainReport() {
  const lines = [];
  lines.push(`浏览器  ${BROWSER || "❌ 未找到 —— 用 --edge <msedge.exe/chrome.exe 路径> 或设 PROMO_EDGE"}`);
  lines.push(`ffmpeg  ${FF || "❌ 未找到 —— 用 --ffmpeg <路径> 或设 PROMO_FFMPEG（系统 PATH 里也没有）"}`);
  if (FF) {
    const v = (/ffmpeg version (\S+)/.exec(spawnSync(FF, ["-version"], { encoding: "utf8" }).stdout || "") || [])[1] || "?";
    const nvenc = /\bh264_nvenc\b/.test(FF_INFO.encoders);
    const x264 = /\blibx264\b/.test(FF_INFO.encoders);
    lines.push(`        版本 ${v}  编码器 h264_nvenc=${nvenc ? "有" : "无"} libx264=${x264 ? "有" : "无"} aac=${/\baac\b/.test(FF_INFO.encoders) ? "有" : "无"}`);
    if (!nvenc && !x264) lines.push("        ❌ 两个 H.264 编码器都没有，无法出成片");
  }
  lines.push(`页面    ${existsSync(PAGE) ? PAGE : "❌ 找不到 " + PAGE}`);
  lines.push(`根目录  ${ROOT}`);
  lines.push(`帧目录  ${FRAMES}`);
  lines.push(`成片    ${OUT}`);
  return lines;
}

if (PREFLIGHT) {
  console.log("render.mjs preflight");
  for (const l of toolchainReport()) console.log("  " + l);
  const toolsOk = Boolean(BROWSER && FF);
  const pageOk = existsSync(PAGE);
  const rootExplicit = argv.includes("--root") || argv.includes("--html");
  if (toolsOk && !pageOk && !rootExplicit) {
    console.log("\n⚠ 工具链齐备；技能目录本身不是项目根，缺少 preview.html。");
    console.log("   用 --root <项目目录> 指向具体片子，例如：node scripts/render.mjs --root ../promo-xxx --preflight");
    process.exit(0);
  }
  if (!toolsOk) {
    console.log("\n❌ 工具链不全：先补浏览器/ffmpeg，再用 --root 指向项目。");
    process.exit(1);
  }
  if (!pageOk) {
    console.log(`\n❌ 页面缺失：${PAGE}。检查 --root/--html，或先做 4:3 预览。`);
    process.exit(1);
  }
  console.log("\n✅ 工具链与页面都齐备，可以开工");
  process.exit(0);
}

function needBin(kind, found) {
  if (found) return found;
  console.error(`❌ 找不到${kind}。已尝试 PATH、常见安装目录与 PROMO_${kind === "浏览器" ? "EDGE" : "FFMPEG"}。`);
  console.error(`   请显式传入，例如：node scripts/render.mjs --${kind === "浏览器" ? "edge" : "ffmpeg"} "C:\\path\\to\\bin"`);
  console.error("   （或先跑 node scripts/render.mjs --preflight 查看完整探测结果）");
  process.exit(2);
}

const ff = (args, label) => {
  const r = spawnSync(FF, args, { encoding: "utf8", maxBuffer: 1 << 28 });
  if (r.status !== 0) throw new Error(`${label} 失败（${r.status}）\n${String(r.stderr || "").slice(-2000)}`);
  return r.stderr;
};

/* ---------------- headless 浏览器会话 ---------------- */
async function withPage(fn) {
  const profile = await mkdtemp(join(tmpdir(), "promo-render-"));
  const port = 9200 + Math.floor(Math.random() * 400);
  const browser = spawn(BROWSER, [
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
    "--no-default-browser-check", "--disable-extensions", "--force-device-scale-factor=1",
    "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
    `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    `--window-size=${WIDTH},${HEIGHT}`, "about:blank",
  ], { stdio: "ignore" });

  let ws, killed = false;
  const kill = async () => {
    if (killed) return; killed = true;
    try { ws && ws.close(); } catch {}
    try { browser.kill("SIGTERM"); } catch {}
    await sleep(200);
    try { browser.kill("SIGKILL"); } catch {}
  };

  try {
    let pg;
    for (let i = 0; i < 200; i++) {
      try {
        const r = await fetch(`http://127.0.0.1:${port}/json/list`);
        if (r.ok) { pg = (await r.json()).find((x) => x.type === "page"); if (pg) break; }
      } catch {}
      await sleep(100);
    }
    if (!pg) throw new Error("浏览器调试端口没起来（Edge/Chrome 可能被安全策略拦了）");

    ws = new WebSocket(pg.webSocketDebuggerUrl);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
    let id = 0; const pending = new Map();
    ws.onmessage = (raw) => {
      const m = JSON.parse(raw.data);
      if (m.id && pending.has(m.id)) {
        const p = pending.get(m.id); pending.delete(m.id);
        m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result);
      }
    };
    const send = (method, params = {}) => new Promise((res, rej) => {
      const mid = ++id; pending.set(mid, { res, rej });
      ws.send(JSON.stringify({ id: mid, method, params }));
    });
    // Runtime.evaluate 的语法/运行时错误走 exceptionDetails 而不是协议 error，必须一起查
    const ev = async (expression) => {
      const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) {
        throw new Error("页面异常：" + String(r.exceptionDetails.exception?.description || JSON.stringify(r.exceptionDetails)).slice(0, 400));
      }
      return r.result;
    };

    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
    await send("Page.navigate", { url: pathToFileURL(PAGE).href + "?render=1" });

    let ready = false;
    for (let i = 0; i < 400; i++) {
      const r = await ev("window.__ready === true").catch(() => null);
      if (r && r.value) { ready = true; break; }
      await sleep(100);
    }
    if (!ready) {
      const errs = await ev("JSON.stringify(window.__errors||[])").catch(() => null);
      throw new Error(`页面没进入 __ready（预览契约要求 ?render=1 暴露 __ready/__duration/__fps/__setTime）${errs?.value ? " 页面错误: " + errs.value : ""}`);
    }
    return await fn({ send, ev });
  } finally {
    await kill();
    await rm(profile, { recursive: true, force: true }).catch(() => {});
  }
}

/* ---------------- 1. meta：时长 / fps / 音频口径 / SFX 事件表 ---------------- */
async function readMeta({ ev }) {
  const M = JSON.parse((await ev(`JSON.stringify({
    total: window.__duration, fps: window.__fps,
    audio: { voice: window.PROMO.voice, sfxDir: window.PROMO.sfxDir, gains: window.PROMO.gains },
    sfx: window.PROMO.sfx || [],
    size: [${WIDTH}, ${HEIGHT}]
  })`)).value);
  if (!M.total || !M.fps) throw new Error("页面没给出 __duration/__fps");
  M.sfx.sort((a, b) => a.t - b.t);
  return M;
}

async function writeMeta(M) {
  await mkdir(OUT_DIR, { recursive: true });
  // 把输入指纹一起写进 meta：--encode-only / --audio-only 只读 meta.json，
  // 没有它就会出现「timeline.js 改了、事件表还是旧的」的静默错混音。
  M.srcFingerprint = inputFingerprint();
  await writeFile(META, JSON.stringify(M, null, 2));
}

/* ---------------- 2. 逐帧截图 ---------------- */
/* 输入指纹：页面本身 + assets 下 js/css/json 的内容 + 其余素材（PNG/WAV）的 size+mtime + 视口。
   「已存在的帧跳过」是断点续跑，但没有指纹就会把两个代码版本的帧混进同一部片子 ——
   实测本轮确实复用了被中断进程留下的 388 帧，且完全无提示。 */
function inputFingerprint() {
  const h = createHash("sha256");
  let page = "";
  try { page = readFileSync(PAGE, "utf8"); } catch (e) { page = "<no-page>"; }
  h.update(page);
  h.update(`\nviewport=${WIDTH}x${HEIGHT}`);
  const walk = (dir) => {
    let ents = [];
    try { ents = readdirSync(dir, { withFileTypes: true }); } catch (e) { return; }
    for (const ent of ents) {
      const p = join(dir, ent.name);
      if (ent.isDirectory()) { walk(p); continue; }
      const st = statSync(p);
      if (/\.(js|css|json|html|vtt|srt|md)$/i.test(ent.name)) h.update(`\nF ${p}` + readFileSync(p));
      else h.update(`\nM ${p} ${st.size} ${Math.round(st.mtimeMs)}`);
    }
  };
  walk(join(ROOT, "assets"));
  return h.digest("hex").slice(0, 16);
}

/* 帧目录守卫：放在开浏览器之前 —— 既省一次启动，也能被无浏览器单测覆盖。 */
function guardFramesDir() {
  const STAMP = join(FRAMES, "_stamp.json");
  const fp = inputFingerprint();
  let heldPng = 0;
  try { heldPng = readdirSync(FRAMES).filter((f) => /^f\d{5}\.png$/.test(f)).length; } catch (e) { heldPng = 0; }
  if (existsSync(STAMP) && heldPng > 0) {
    let old = null;
    try { old = JSON.parse(readFileSync(STAMP, "utf8")); } catch (e) { old = null; }
    if (old && old.fp && old.fp !== fp && !RESUME_ANYWAY) {
      console.error(`
❌ 帧目录里已有 ${heldPng} 帧，但输入指纹变了（旧 ${old.fp} / 新 ${fp}）。
` +
        `   继续跑会把旧代码版本的帧混进这部片子，而且不会有任何提示。
` +
        `   二选一：删掉 ${FRAMES} 重截；或确认要复用旧帧时加 --resume-anyway。`);
      process.exit(1);
    }
    if (old && old.fp && old.fp !== fp) console.log(`  ⚠ --resume-anyway：复用 ${heldPng} 帧，尽管输入指纹已从 ${old.fp} 变为 ${fp}`);
  }
  try { mkdirSync(FRAMES, { recursive: true }); } catch (e) { }
  writeFileSync(STAMP, JSON.stringify({ fp, page: PAGE, viewport: [WIDTH, HEIGHT], at: new Date().toISOString() }, null, 2));
  return fp;
}

async function grab(M) {
  return withPage(async ({ send, ev }) => {
    const live = await readMeta({ ev });
    if (Math.abs(live.total - M.total) > 0.01) console.warn(`  ⚠ meta 里 total=${M.total} 与页面 ${live.total} 不一致，按页面的来`);
    const fps = live.fps;
    M.total = live.total; M.audio = live.audio; M.sfx = live.sfx;

    const from = Number(val("from", 0));
    const to = Number(val("to", M.total));
    const i0 = Math.max(0, Math.round(from * fps));
    const i1 = Math.min(Math.round(M.total * fps), Math.round(to * fps));
    console.log(`截图帧 ${i0} … ${i1}（共 ${i1 - i0} 帧）  ${M.total.toFixed(2)}s @${fps}fps`);

    const t0 = Date.now();
    let done = 0, skipped = 0;
    for (let i = i0; i < i1; i++) {
      const file = join(FRAMES, `f${String(i).padStart(5, "0")}.png`);
      if (existsSync(file)) { skipped++; continue; }
      // 先把舞台推到确定时刻，再等两个 rAF 让合成器真正画完，才截图
      await ev(`(async () => {
        window.__setTime(${i} / ${fps});
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        return 1;
      })()`);
      const shot = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
      await writeFile(file, Buffer.from(shot.data, "base64"));
      done++;
      if (done % 60 === 0) {
        const el = (Date.now() - t0) / 1000, per = el / done;
        console.log(`  ${done}/${i1 - i0}  ${per.toFixed(2)} s/帧  已用 ${el.toFixed(0)}s  预计剩余 ${((i1 - i0 - done) * per).toFixed(0)}s`);
      }
    }
    console.log(`截图完成：新截 ${done} 帧，跳过已存在 ${skipped} 帧，用时 ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    return M;
  });
}

/* ---------------- 3. 音频图 ---------------- */
/* WebAudio StereoPanner 对 stereo 输入的矩阵（W3C 规范），需要时可用：
     pan<=0 → L'=L,            R'=sin(a)·L + (1-sin(a))·R
     pan>=0 → L'=(1-sin(a))·L + sin(a)·R,   R'=R          a=|pan|·π/2
   约定是声像烘在音效 WAV 里（见 references/preview-contract.md §6），这里默认不再二次 pan。 */
function panExpr(p) {
  const s = Math.sin(Math.abs(p || 0) * Math.PI / 2);
  if (!s) return null;
  const f = (v) => v.toFixed(4);
  const m = p < 0 ? { l: [1, 0], r: [s, 1 - s] } : { l: [1 - s, s], r: [0, 1] };
  const ch = (c) => [[c[0], "c0"], [c[1], "c1"]].filter(([k]) => k > 0.0001)
    .map(([k, n]) => (k === 1 ? n : `${f(k)}*${n}`)).join("+");
  return `pan=stereo|c0=${ch(m.l)}|c1=${ch(m.r)}`;
}

/* idx：旁白是第几个 -i。整片合成时 0 是帧序列（旁白=1），只处理音频时旁白就是 0；
   必须参数化，否则输入索引整体偏一位，ffmpeg 会报 filtergraph 绑定错误。 */
function audioGraph(M, { idx = 1, master = 1, post = "", voiceMul = 1, panEvents = false } = {}) {
  const g = M.audio.gains || {};
  const gv = (g.voice ?? 1) * voiceMul, gs = g.sfx ?? 0.62;
  const voice = resolveIn(M.audio.voice);
  const sfxDir = resolveIn(M.audio.sfxDir || "assets/sfx");
  if (!existsSync(voice)) throw new Error(`缺旁白文件：${voice}`);
  const args = ["-i", voice];
  const parts = [`[${idx}:a]volume=${gv.toFixed(4)},aformat=sample_rates=48000:channel_layouts=stereo[voc]`];
  const missing = [];
  M.sfx.forEach((e, i) => {
    const inp = idx + i + 1;
    const file = join(sfxDir, e.name.endsWith(".wav") ? e.name : e.name + ".wav");
    if (!existsSync(file)) { missing.push(`${e.t}s ${e.name}`); return; }
    args.push("-i", file);
    /* 网页里音效是在 rAF tick 跨过 ev.t 的那一帧触发，听感时刻被量化到帧边界。
       这里跟着量化，成片才和预览一帧不差；直接用 t 会早 0–33ms。 */
    const ms = Math.max(0, Math.round(Math.ceil(e.t * M.fps) / M.fps * 1000));
    const vol = ((e.g == null ? 1 : e.g) * gs).toFixed(4);
    const pan = panEvents ? panExpr(e.pan) : null;
    parts.push(`[${inp}:a]adelay=${ms}|${ms},volume=${vol},aformat=sample_rates=48000:channel_layouts=stereo${pan ? "," + pan : ""}[s${i}]`);
  });
  if (missing.length) throw new Error(`缺 ${missing.length} 个音效文件：${missing.slice(0, 6).join("、")}${missing.length > 6 ? " …" : ""}`);
  const mix = ["[voc]", ...M.sfx.map((_, i) => `[s${i}]`)].join("");
  const trim = master === 1 ? "" : `,volume=${master.toFixed(4)}`;
  // 不用 -shortest：旁白比成片短会把画面截短。用 apad 补静音 + -t 帧数/fps。
  parts.push(`${mix}amix=inputs=${M.sfx.length + 1}:duration=longest:normalize=0${trim},apad${post}[aout]`);
  return { inputs: args, filter: parts.join(";"), nSfx: M.sfx.length, gv, gs, master };
}

/* ---------------- 4. 读取成片信息（只用 ffmpeg） ---------------- */
function mediaInfo(file) {
  // `ffmpeg -i 文件` 不带输出会以退出码 1 结束，这里要的是 stderr 里的元信息，不能走严格退出码判断
  const s = spawnSync(FF, ["-hide_banner", "-i", file], { encoding: "utf8", maxBuffer: 1 << 28 }).stderr || "";
  const dur = /Duration: (\d+):(\d+):([\d.]+)/.exec(s);
  const v = /Video: (\w+)[^\n]*?, (\d{2,5}x\d{2,5})[^\n]*?, ([\d.]+) fps/.exec(s);
  return {
    seconds: dur ? +(dur[1] * 3600 + +dur[2] * 60 + +dur[3]).toFixed(3) : null,
    video: v ? `${v[1].trim()} ${v[2]} @${v[3]}fps` : "?",
  };
}

function loudness(file, label) {
  // astats 的块顺序/前缀在不同构建里不一样，所以不猜格式：把所有 Peak/RMS 行抓出来取最大值
  const st = ff(["-hide_banner", "-i", file, "-map", "0:a",
    "-af", "astats=measure_perchannel=Peak_level+RMS_level:measure_overall=Peak_level+RMS_level+Number_of_samples",
    "-f", "null", "-"], label + " 音频统计");
  const nums = (key) => [...st.matchAll(new RegExp(`${key}: (-?[\\d.]+|-?inf)`, "g"))]
    .map((m) => Number(m[1])).filter(Number.isFinite);
  const peaks = nums("Peak level dB"), rms = nums("RMS level dB");
  const peak = peaks.length ? Math.max(...peaks) : null;
  console.log(`  ${label} 峰值 ${peak == null ? "?" : peak.toFixed(2)} dBFS（各读数 ${peaks.map((p) => p.toFixed(1)).join(" / ") || "?"}）  RMS ${rms.map((p) => p.toFixed(1)).join(" / ") || "?"} dBFS`);
  if (peak != null && peak > -0.1) console.log(`  ⚠ 峰值 ${peak.toFixed(2)} dBFS 逼近/超过 0 dBFS，会削顶 —— 降 gains.sfx 或给混音加 alimiter`);
  return { peak, rms: rms.length ? Math.max(...rms) : null };
}

function countFrames(file) {
  // 精简构建的进度行可能没有 frame=，用 framecrc 每个包一行来数
  const out = spawnSync(FF, ["-hide_banner", "-loglevel", "error", "-i", file,
    "-map", "0:v", "-c", "copy", "-f", "framecrc", "-"],
    { encoding: "utf8", maxBuffer: 1 << 28 }).stdout || "";
  const f = out.match(/^\d+,/gm);
  return f ? f.length : null;
}

/* ---------------- 4.5 母线余量 ----------------
 * amix=normalize=0 是纯相加：旁白单独有余量，但音效叠加、同一秒内多个事件互相叠加时，
 * 浮点求会后转 s16 就削顶。做法：先用固定小增益把真峰值量出来（探测阶段绝不削顶），
 * 再按目标峰值折算一个全片统一的母线 trim —— 只整体平移，不改旁白/音效相对比例。
 * 系数写回 meta.json，成片可复现。 */
const PROBE_TRIM = 0.25;                    // 20·log10(0.25) ≈ -12.04 dB
const TARGET_PEAK_DB = -1.0;

function mixPeak(M, durSec) {
  const A = audioGraph(M, { idx: 0, master: PROBE_TRIM, post: ",astats=measure_perchannel=none:measure_overall=Peak_level+RMS_level" });
  const st = ff(["-hide_banner", ...A.inputs, "-filter_complex", A.filter,
    "-map", "[aout]", "-t", durSec, "-f", "null", "-"], "真峰值探测");
  const p = [...st.matchAll(/Peak level dB: (-?[\d.]+)/g)].map((m) => Number(m[1]));
  if (!p.length) throw new Error("真峰值探测没拿到 Peak level，检查这个 ffmpeg 构建的 astats 是否可用");
  return Math.max(...p) - 20 * Math.log10(PROBE_TRIM);
}

async function prepareAudio(M) {
  const durSec = (Math.round(M.total * M.fps) / M.fps).toFixed(4);
  const raw = mixPeak(M, durSec);
  const master = raw > TARGET_PEAK_DB
    ? Math.floor(Math.pow(10, (TARGET_PEAK_DB - raw) / 20) * 10000) / 10000
    : 1;
  console.log(`混音真峰值 ${raw.toFixed(2)} dBFS → 母线 trim ×${master.toFixed(4)}（目标峰值 ${TARGET_PEAK_DB} dBFS）`);
  M.master = master;
  await writeMeta(M);
  return master;
}

function mixToFile(M, file, opts, dur, label) {
  const A = audioGraph(M, opts);
  ff(["-hide_banner", "-loglevel", "error", "-y", ...A.inputs,
    "-filter_complex", A.filter, "-map", "[aout]", "-t", dur,
    "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", file], label);
  const info = mediaInfo(file);
  console.log(`  ${label} 时长 ${info.seconds}s（成片应为 ${dur}s）→ ${file}`);
  loudness(file, label);
  return { ...A, ...info };
}

async function encodeAudio(M) {
  await mkdir(OUT_DIR, { recursive: true });
  const n = Math.round(M.total * M.fps);
  const dur = (n / M.fps).toFixed(4);
  console.log(`音频试做：旁白×${((M.audio.gains || {}).voice ?? 1)} + ${M.sfx.length} 个音效×${(M.audio.gains || {}).sfx ?? 0.62}  母线×${M.master ?? 1}`);
  const mix = mixToFile(M, AUDIOTEST, { idx: 0, master: M.master ?? 1 }, dur, "混音");
  // 旁白静音那一条只用来核对音效落点/左右偏向，不进成片
  const solo = mixToFile(M, SFXTEST, { idx: 0, master: M.master ?? 1, voiceMul: 0 }, dur, "纯音效");
  return { ...mix, sfxOnly: solo };
}

function videoArgs(encoder) {
  return encoder === "nvenc"
    ? ["-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq", "-rc", "vbr", "-cq", "19", "-b:v", "0", "-maxrate", "40M", "-bufsize", "80M"]
    : ["-c:v", "libx264", "-preset", "slow", "-crf", "18"];
}

async function encode(M) {
  await mkdir(OUT_DIR, { recursive: true });
  const n = Math.round(M.total * M.fps);
  const last = join(FRAMES, `f${String(n - 1).padStart(5, "0")}.png`);
  if (!existsSync(last)) throw new Error(`缺帧：${last}（先跑 --frames-only，或确认 --frames-dir/--from/--to 指对了范围）`);
  const A = audioGraph(M, { master: M.master ?? 1 });
  const dur = (n / M.fps).toFixed(4);

  const hasNvenc = ENCODER_PREF === "nvenc" || (ENCODER_PREF === "auto" && /\bh264_nvenc\b/.test(FF_INFO.encoders));
  const order = hasNvenc && ENCODER_PREF !== "x264" ? ["nvenc", "x264"] : ["x264"];
  let used = null, lastErr = null;
  for (const enc of order) {
    console.log(`编码（${enc}）：${n} 帧 @${M.fps}  母线×${A.master}  →  ${OUT}`);
    const args = [
      "-hide_banner", "-loglevel", "error", "-y",
      "-framerate", String(M.fps), "-i", join(FRAMES, "f%05d.png"),
      ...A.inputs,
      "-filter_complex", A.filter,
      "-map", "0:v", "-map", "[aout]",
      ...videoArgs(enc),
      "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2",
      "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
      "-t", dur, "-movflags", "+faststart",
      OUT,
    ];
    try { ff(args, "编码"); used = enc; break; }
    catch (e) { lastErr = e; console.warn(`  ${enc} 编码失败，准备降级重试：${String(e.message).split("\n")[0]}`); }
  }
  if (!used) throw lastErr;

  const info = mediaInfo(OUT);
  console.log(`  时长 ${info.seconds}s（应为 ${dur}s）  画面 ${info.video}`);
  loudness(OUT, "成片");
  const got = countFrames(OUT);
  console.log(`  视频帧数 ${got}（应为 ${n}）${got === n ? " ✅" : " ⚠"}`);

  M.render = {
    encoder: used, browser: BROWSER, ffmpeg: FF, frames: got, expectedFrames: n,
    peakDb: loudness(OUT, "成片复核").peak, size: [WIDTH, HEIGHT],
  };
  await writeMeta(M);

  if (!KEEP_FRAMES) {
    await rm(FRAMES, { recursive: true, force: true });
    console.log(`  已清理 PNG 帧目录 ${FRAMES}`);
  } else {
    console.log(`  保留 PNG 帧目录 ${FRAMES}`);
  }
  return { ...info, frames: got, encoder: used };
}

function loadMetaFromFile() {
  if (!existsSync(META)) return null;
  try {
    const M = JSON.parse(readFileSync(META, "utf8"));
    if (!M.total || !M.fps || !M.audio || !Array.isArray(M.sfx)) throw new Error("字段不全");
    const now = inputFingerprint();
    if (M.srcFingerprint && M.srcFingerprint !== now && !has("force-stale-meta")) {
      console.error(`\n❌ meta.json 的输入指纹（${M.srcFingerprint}）与当前页面/素材（${now}）不一致。` +
        `\n   --encode-only / --audio-only 会照旧事件表混音 —— 字幕、音效落点都可能对不上新画面。\n` +
        `   二选一：先跑一次 --meta-only（或整片）刷新 meta；确认要用旧 meta 时加 --force-stale-meta。`);
      process.exit(1);
    }
    if (M.srcFingerprint && M.srcFingerprint !== now) console.log(`  ⚠ --force-stale-meta：用旧 meta 混音（${M.srcFingerprint}）`);
    console.log(`用 ${META}：total=${M.total}s fps=${M.fps} 音效 ${M.sfx.length} 个`);
    return M;
  } catch (e) {
    console.log(`meta.json 不可用（${e.message}），改为打开页面读取`);
    return null;
  }
}

/* ---------------- 入口 ---------------- */
needBin("浏览器", BROWSER);
needBin("ffmpeg", FF);
if (!existsSync(PAGE)) { console.error(`❌ 页面不存在：${PAGE}\n   用 --root <工程目录> 或 --html <preview.html>`); process.exit(2); }
console.log(`工具链：${BROWSER}  |  ${FF}`);

/* 帧目录守卫放在开浏览器之前：指纹不符就当场拒绝，既不浪费时间，也能被无浏览器单测覆盖。 */
if (!ENCODE_ONLY && !AUDIO_ONLY && !META_ONLY) guardFramesDir();

const fromFile = (ENCODE_ONLY || AUDIO_ONLY) ? loadMetaFromFile() : null;
let M = fromFile;

if (!M) M = await withPage(async ({ ev }) => readMeta({ ev }));

if (META_ONLY) {
  await writeMeta(M);
  console.log(`meta 已写入 ${META}`);
} else if (AUDIO_ONLY || ENCODE_ONLY) {
  await prepareAudio(M);
  await encodeAudio(M);
  if (ENCODE_ONLY) await encode(M);
} else {
  M = await grab(M);
  await writeMeta(M);
  if (!FRAMES_ONLY) {
    await prepareAudio(M);
    await encodeAudio(M);
    await encode(M);
  } else {
    console.log(`只截帧模式：未合成。meta 已写入 ${META}`);
  }
}
