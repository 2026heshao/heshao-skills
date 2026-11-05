# Changelog

## v2.1.0 — 2026-11-04

加入“交付后反馈 → 案例 → 规则”的自更新闭环，默认在每支片交付后主动回访。

- 新增 `references/feedback-loop.md`：3+1 问法（整体 0–10 / 最想保留 / 最想改 / 沉淀意愿）、success/conditional/fail/unrated 判定、硬失败清单、经验落盘、候选升级闸门（≥2 个独立项目或用户明确要求 + 人工确认 diff）、回滚与反模式。参考 aiskill.market、Claude Code `/reflect`、Addy Osmani、Warp、MindStudio、MUSE 的做法。
- 新增 `experiences/_template.md`、`experiences/INDEX.md`：单条经验 ≤20 行；只存项目/配方/分数/短引用，不存素材与个人信息；索引由脚本生成。
- 新增 `scripts/feedback.mjs`：`--prompt`（打印交付后的 3+1 回访话术）、`--new`（按 schema 建档并重建索引）、`--validate`（字段/分数/verdict/recipe + 交叉一致性校验）、`--index`、`--list`、`--candidates`。硬失败优先于分数：`hardFail=true` 只能记 `fail`；同时拒绝 `success+score<8`、`unrated+score`、`candidate` 非 success 等矛盾组合。已用临时目录跑完整状态矩阵：success/conditional/fail/hard-fail/重复文件名均符合预期，矛盾组合按预期 FAIL。
- `SKILL.md`：新增 Phase 8「交付后反馈与自更新」；开头明确“交付完成 = 成片/封面 + QA 数字 + 3+1 回访已发出”；§0 增加 L3 经验层；§5 成片 QA 增加“交付后发 3+1 回访”；§7 增加 feedback-loop / experiences / feedback.mjs；结尾一句话补“案例和规则分开沉淀”；版本升 2.1.0，description 补“交付后主动收集反馈并分层沉淀经验”。
- `references/feedback-loop.md`：新增“用户只给一句话怎么判”（很好/还行/不行/只回部分/不评），不替用户补分数。
- `references/scorecard.md`：交付后回访，成片评分写 `experiences/`，不直接改权重。
- `references/controlled-randomness.md`：权重/牌组调整必须在升级闸门之后；单次反馈不改权重；新增“一次好评直接改权重”的失败模式。
- `references/case-dsh-armory-atlas.md`：补第 11 节，说明本案例是“用户明确要求 + 人工确认”的规则升级，不是自动调权重。
- `evals/evals.json`：新增三条回访评测：7 分且用户说“别改权重”走 conditional；9 分且“以后都这样”走 success + candidate，仍要先看 diff 再改规则；交付后没回访算未完成。
- 抽签逻辑、牌组、权重、兼容矩阵未改；`originality-8-axis` 仍为历史机器标签。

### v2.1.0 续：旁白/时间轴/音效脚本补齐（同日）

把 `preview-contract.md` 与 SKILL.md 承诺过、但包里不存在的三个生成器真正做出来，并从已跑通的
promo-depot 工程移植（不是照文档重写）。全部在本机实测。

- 新增 `scripts/build_voice.py`：口播稿 json → 逐句 edge-tts + 润音链 → **样本级**句子时间轴
  `voice_timeline_<slug>.json` + `voice_<slug>.wav/.m4a`。实测 4 句 13.38s，真峰值 −3.20 dBFS 不削顶；
  `--from-cache` 复跑句子时刻完全一致（改润音链不漂移）。
- 新增 `scripts/build_timeline.py`：句子时间轴 + 镜头规格 → `timeline.js`（`window.PROMO`）、
  `timeline.json`、`narration.vtt/.srt`（整句口播，平台外挂字幕用）、`captions.vtt/.srt`（上屏关键词）。
  技能此前**完全没有字幕文件导出能力**（全包 grep `.srt|webvtt` 0 命中）。字幕两端分别向下/向上
  取整到帧边界，与 `render.mjs` 的 `ceil(t*fps)/fps` 同一口径；坏输入给可行动报错（句下标越界、
  字幕窗口反向、`sceneStart` 缺 scene）。
- 新增 `scripts/tts_chain.py`：从 promo-depot 的 `tts_lib.py` 剥离项目专属内容后的通用件；
  ffmpeg 改为自动探测（`PROMO_FFMPEG` → PATH → 剪映最新版目录），不再硬编码某个版本号路径。
- 新增 `scripts/build_sfx.py`：13 种材质自产音效。**修掉一个顺序耦合缺陷**：原实现共用一条全局
  RNG 流，加/删/重排材质会连带改变其后所有材质的字节（实测：同一材质在全序下 `8c2f…`、
  零前置消耗下 `caf8…`）。改为每材质独立派生 seed（blake2s，`default_rng` 不收字符串）。
  验证：全序 / 倒序 / 只跑子集，13 个 wav 逐字节一致；写盘峰值最高 −3.35 dBFS、0 削顶样本。
- `scripts/qa_mp4.py`：ffmpeg 自动探测 + `--ffmpeg`；`--ref` 的“工程根目录”改由 `--project-root`
  显式指定（原实现用 `render` 路径的上上层目录推断，脚本搬进包内后会错指到技能包自己）。
- `scripts/render.mjs`：剪映 ffmpeg 探测改为按目录名降序取最新，与 `qa_mp4.py` 同一口径（此前两边
  会选到不同构建）。
- 端到端实测：对 promo-depot 真实页面截 1348 帧（264s，0.196 s/帧）→ 混音（159 个音效事件，
  真峰值 −2.07 dBFS，与文档记载的原项目实测值一致）→ nvenc 编码 → 成片 44.93s / 1348 帧 /
  1440×1080。**与原成片同帧号比对：平均绝对差 0.000、大幅差 0.000%，体积仅差 18 字节**，
  说明移植等价而非近似。`qa_mp4.py` 全项 PASS，A/V 包络偏移 +0.0 ms。
- 文档：SKILL.md 依赖补 `scipy`、开工前 `--preflight`、Phase 4/6/7 接入新脚本；§7 文件地图补 6 个
  新脚本；`audio-and-render.md` §7 验收命令改为真实可跑的分阶段命令；`preview-contract.md` §2 把
  “由旁白时间轴脚本生成”落到具体脚本名。
- `packages/*/package.json` 版本补到 2.1.0（此前与 SKILL.md frontmatter 不一致）。

### v2.1.0 续二：配方可复现性（只加记录，不改默认熵源）

- `scripts/pick.mjs`：配方新增 `context.deckFingerprint`（decks+compatibility+weights 的 sha256 前 12 位）
  与 `context.argv`（原始参数）。此前无法回答“当时那套牌组长什么样”，牌组一改旧 seed 就悄悄不可复现。
- `--validate` 现在会提示两种不可复现情况：指纹与当前牌组不符、或该配方早于本字段没有指纹。
- 新增 `--strict-seed`：把 `--base`/`--vary`/`--lock`/history 目录纳入熵源。**默认关闭** —— 熵源是
  破坏性改动（会让所有既有 seed 换结果），所以做成显式开关而不是改默认值。
- 零漂移实测：同一组参数在改动前后（store 基线 vs 本版）跑 3 次，`picks`/`prompt`/`storyboard` 三项
  逐字段一致；新增字段仅出现在 `context`。`--strict-seed` 下同参数双跑一致、换 `--base` 结果不同。
- `evals/evals.json`：新增 id 9–12 四条回归评测（工具链探测与截图确定性、分阶段渲染与成片 QA、
  旁白→时间轴→字幕文件、音效库扩充不得改动既有材质字节）。
- 修正一处我自己的错误推论：曾判断“CHANGELOG 声称的回访评测未落地”，实际 id 7/8 已在文件中
  （store 与 AI Port 两份都已被同步改动，我误把旧状态当基准）。

### v2.1.0 续三：端到端自测（全新最小工程）与 QA 判据修正

- 不复用 depot 任何资产，从零跑通 `narration.json → build_voice → build_sfx → build_timeline → preview.html → render.mjs → qa_mp4.py`：13.12s / 394 帧 / 1440×1080@30 / 峰值 −3.20 dBFS / RMS −17.9 / **A/V 偏移 +0.0ms** / 逐声道 0 削顶。
- 纯函数契约在新页面上验证：顺序推进 201 帧得到的 f00200 与直接跳到同一时刻的 PNG **sha256 相同**；`--ref` 逐帧回捞比对平均差约 2.0/255、大幅差 0.0%。
- 口播归一化验证生效：上屏保留 `MCP` / `DSH` / `AI`，送 TTS 变为 `M C P` / `D S H` / `A I`。
- `scripts/qa_mp4.py`：**修正「画面为空」判据**。旧判据 `mean > 8` 会把暗色世界（atlas `#05070f`、tower `#050b16`、blueprint、depot 均属暗底）的正常落定帧误杀——实测有内容的帧 mean 仅 5.0~7.4，但 stddev 8.4~21.9、亮像素 0.43%~1.27%；而快门闭合的真·空帧是 mean 2.8 / stddev 3.2 / 亮像素 0.05%。改为判结构：`stddev < 6 且 亮像素占比 < 0.3%` 才算空帧。
  三方向自证：暗色 e2e 落定帧 PASS；故意采换幕起点 6.9s 仍 FAIL（判据没被改钝）；亮色 depot 全片 11 个时刻仍 PASS（无回归）。
- `SKILL.md` Phase 7 补采样规则：取每幕落定后 ≥0.3s，避免把百叶快门/片尾淡出的天然黑帧当成缺陷。
- 自测中发现并修掉的是**测试夹具自身的 bug**（`#slats` / `#fade` 用 id 选择器而 `el()` 只加 class，导致快门与淡出从未生效），非技能脚本问题；该错误一度让我把「6.9s 全黑」误解释成快门遮挡，实为该刻尚未画出内容。

## v2.0.2 — 2026-11-04

把 dsh-armory 能力星图（atlas）的实战复盘写进技能，并统一 9 轴口径。

- 新增 `references/case-dsh-armory-atlas.md`：六支参考片的选择理由与借/禁清单、星图台配方与风险、实际 6 幕时长、比喻合同、单句 TTS 气口定位与换 take、编号/落版/上屏制作参数/封面碰撞修复、预览与成片 QA 数字、复现命令。
- `SKILL.md`：Phase 1 差异化矩阵补“幕长”并统一为 9 轴；Phase 4 增加“按句量 p10/p5，单句气口优先换 take”；Phase 6 增加“落版先保 CTA”和“制作参数不进画面”；§3.2 增加星图救援骨架；§6 增加“把视觉比喻写成产品功能”“用整片降噪掩盖单句气口”两坑；§7 增加案例与 `scripts/render.mjs` 入口；§8 增加 atlas 参考实现。
- `references/originality-gates.md`：八轴矩阵改为九轴矩阵，CTA 正式入表；注明 `originality-8-axis` 为历史兼容标签，实际按 9 轴执行。
- `references/audio-and-render.md`：补“单句气口异常（atlas 实测）”：第 10 句 p10 −56.9 / p5 −62.6，换标点 take 后 −64.7 / −69.0；`afftdn` 与整片门限均不理想。
- `references/facts-and-copy.md`：新增“比喻合同”：第一次出现用“比作/看法”，中段交回真实界面，落版/封面加脚注；产品里搜不到的名词不能写成功能。
- `references/visual-worlds.md`：星图台补比喻合同；风险说明补 atlas 的 9 轴过闸方式。
- `references/story-rhythm.md`：新增“星图救援型”六幕变体；落版 CTA 单独要求 ≥1.2s，最后一句旁白结束前不收光圈/淡出。
- `references/preview-contract.md`：HUD 编号改为从 01 开始并与图版/底栏同源；制作参数不进画面，只放抽屉/README。
- `recipes/dsh-armory-atlas-20261104a.json`：写入实拍 6 幕、46.98s 与配方漂移说明；`recipes/dsh-armory-atlas-atlas-20261104a.json` 标记 DEPRECATED（修复前重复命名产物，不是本片配方）。
- `scripts/render.mjs`：`--preflight` 在技能根目录不再把“缺少 preview.html”误报成“工具链不全”；未显式指定 `--root`/`--html` 时提示用 `--root` 并返回 0，显式指定仍缺页面才返回 1。
- `scripts/render.mjs` 现随包存在（通用 `--root/--html/--out` 参数）；v2.0.1 记录的“脚本缺失”不再成立。在技能根目录跑 `--preflight` 会报缺少 `preview.html`，属正常——用 `--root <项目>` 指向具体片子。抽签逻辑、牌组、权重、兼容矩阵未改，机器字段 `originality-8-axis` 保持兼容。

## v2.0.1 — 2026-11-04

修「文档教的路径在代码里是坏的」，并补齐 atlas 世界的文档缺口。

- `scripts/pick.mjs`：`--lock` 提前到依赖轴抽取之前。此前 `--lock world=X` 先按旧世界抽 transition/caption/sound/rhythm 再改世界，实测 20 个 seed **80% 直接 exit 1**，剩下 20% 的分布也是偏的（新世界的部分合法卡结构上抽不到）。现在锁定后由 `repairDependentAxes()` 重抽依赖轴并记入 `forcedAxes`；锁定项写入 `context.locked`。
- `scripts/pick.mjs`：依赖轴修复逻辑从「仅 `--base` 分支」提取为函数，两条路径共用。
- `scripts/pick.mjs`：修默认文件名重复 project 的缺陷（默认 seed 本身以 project 开头，拼接后得到 `dsh-armory-atlas-dsh-armory-atlas-2026-11-04.json`）。
- `scripts/pick.mjs`：头部注释与运行输出不再宣称「同 seed 即同结果」——改为「同 project + seed + 参数 + decks/weights/history 才同结果」。
- `references/visual-worlds.md`：补第 7 节「星图台 / Star Atlas」（此前 `decks/worlds.json` 已有 atlas 卡，散文配方缺失）。
- 无回归：不带 `--lock` 的抽取路径，picks 与 prompt 逐字节等于 v2.0.0（唯一差异是新增的 `context.locked: {}` 字段）。
- 已知未修：`store/` 仍被 `.gitignore` 忽略，技能包无版本控制；`scripts/render.mjs` 被 `audio-and-render.md` 与 `qa_mp4.py` 默认参数引用但不存在。

## v2.0.0 — 2026-11-03

从“参考片工作流”升级为“受控随机系统”。

- 新增 `decks/`：worlds / hooks / transitions / captions / sounds / rhythms，含参考片表达对照卡（`banned: true`）。
- 新增 `compatibility.json`：world × hook/transition/caption/sound/rhythm 的合法组合。
- 新增 `weights.json`：权重 + epsilon-greedy explore。
- 新增 `scripts/pick.mjs`：seeded 抽牌、最多 2 个新轴、history 排除、兼容性校验、prompt/storyboard 输出。
- 新增 `recipes/`：模板 + `dsh-armory-depot-20261103` seed 配方。
- 新增 `references/controlled-randomness.md`：三层模型、加卡/调权重、项目循环。
- 新增 `references/scorecard.md`：盲评 7 项、淘汰线、性能回填。
- `SKILL.md`：新增 v2 抽配方段落；Phase 1/2/6 接入 recipe；参考文件地图更新。
- `references/visual-worlds.md` / `originality-gates.md` / `story-rhythm.md`：补机器可读牌组与系统层防线。

## v1.0.0 — 2026-11-03

- 参考片拆解、原创性闸门、故事/节奏、视觉世界、4:3 预览契约、音频与渲染、事实与文案。
- `scripts/qa_mp4.py` 成片 QA。
- `evals/evals.json` 测试提示。
