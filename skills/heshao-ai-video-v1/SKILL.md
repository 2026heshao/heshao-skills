---
name: heshao-ai-video-v1
version: 2.8.0
description: 原创产品宣传片与 AI 动画故事双路线工作流。用于产品宣传片、参考片改编方法、二维/三维/MG 动画、角色故事、无旁白或纯无声动画、分镜/动态预演、4:3 可交互网页预览与确认后 MP4 交付。产品路线先做产品画像，再选本地牌组/联网试用卡/手写校验的受控配方；故事路线先定故事或表演意图、角色基准、动作与镜头，不强套产品事实表、抽牌、口播占比或 CTA。提供动作设计、一致性、平台能力查证、逐镜验收和最小返工方法，内置 Seedance 2.0 提示词子技能。素材分六类来源（代码绘制/自制/图库/公有领域/AI 生成/付费）并强制授权台账：每条素材记来源、许可、日期与哈希，视频素材须抽帧成图片序列才算帧精确，同图跨镜复用与影视截图当素材会被闸门拦下。也用于“不要每次抽卡”“牌组不适合这个产品”“动画怎么保持一致/怎么接镜头”“素材从哪来、能不能商用”。Use for original product promos, AI animation stories, silent animation, storyboards/animatics, controlled recipes, asset sourcing and license tracking, HTML previews and verified delivery. 不承诺新模型或外部视频素材已接入现有逐帧渲染器。
---

# Heshao AI Video v2 — 产品宣传片与动画故事

## When to Use

给软件 / 插件 / 工具 / Agent 做产品片，或制作二维 / 三维 / MG、角色故事、无旁白 / 无声动画；
用户要参考方法做原创片、分镜预演、4:3 网页确认、成片验收或受控随机时使用。
先按 §1 选产品或故事路线；不用于纯剪辑转码、静态海报或完全复制参考片。

## Prerequisites

Node 22+ · Python 3.12+ · ffmpeg（`h264_nvenc` 或 `libx264`）· Edge/Chrome · numpy · scipy · Pillow ·
TTS 用 `edge-tts`（在线服务）。ffmpeg / Edge 常常不在 PATH（本机只有剪映自带那份），
探测顺序：`PROMO_FFMPEG` / `PROMO_EDGE` → PATH → 常见安装目录 → `--ffmpeg` / `--edge` 显式指定。
开工前先跑 `node scripts/render.mjs --preflight`：缺什么直接说清楚，不要跑到一半才崩。
它还会体检 Python 侧（`PROMO_PYTHON` → `python` / `python3` / `py`）、打印 Node 版本与
numpy / scipy / Pillow / edge-tts 的版本；缺包时直接给出该解释器下的 `pip install` 命令，
缺任一项退出码为 1，不会等跑到 Phase 4 才抛裸 `ModuleNotFoundError`。

## Workflow

先按 §1 选影片类型。产品：Phase 0 拆参考 → 0.5 产品画像 → 1 配方/事实 → 2 文案/分镜/预演 →
3 网页预览 → 4 音频 → 5 QA/确认 → 6 MP4 → 7 成片 QA → 8 回访，详见 §2。
故事：简报/结局 → 视觉基准 → 事件/动作/动态预演 → 镜头试做 → 验收续接 → 时间轴/预览确认 → 成片/回访，详见 [动画流程](references/ai-animation-workflow.md)。

## Output

共同交付：MP4、同视觉基准的 3:4 封面、接触表、元数据、SHA-256、交付说明（规格/QA/重出方法/限制）与 3+1 回访。
产品另交 `narration.vtt/.srt`、`captions.vtt/.srt` 及旁白/纯音效分轨；故事按实际对白、字幕和声音需要交付，不为无声故事伪造台词、字幕或音轨。

## Resources

见 §7；动画先读 [制作与故事路线](references/ai-animation-workflow.md)，动作/平台资料按需加载；工程参考见 §8。

这是一套**原创宣传片与动画故事工作流**，不是固定皮肤，也不是“把参考片换个颜色”。

核心立场：

> **借方法，不借表达。** 可以借“强钩子、快节奏、高信息密度、强卡点、关键词字幕、动作音效”；不可以借原句、分镜顺序、幕长组合、转场组合、字幕动效、视觉母题和音效排列。

默认交付：**4:3 网页高仿真预览** → 用户确认 → **1440×1080 / 30fps MP4**。用户没有明确确认预览前，不渲染 MP4。

**交付完成 = 成片/封面 + 实际 QA 结果 + 3+1 回访已发出。** 回访不阻塞交付，用户不评就记 `unrated`；不适用和未验证分别记录。

上述依赖是现有产品渲染工具链，不代表故事必须使用 TTS。只做规划不要求安装全套；进入工程前运行 `node scripts/render.mjs --preflight`，按 [动画流程的工具边界](references/ai-animation-workflow.md#5-现有脚本的能力边界) 判断当前路线是否可用，不能把体检通过当成新媒体/无声导出已支持。

---

## 0. 产品路线：先判产品，再选熵源，最后抽配方

v2 把“每次抽卡”改成**受控随机**：

- **L0 宪法**：产品事实、品牌、画幅、时长、QA、禁用表达——永不随机。
- **L1 牌组**：world / hook / transition / caption / sound / rhythm——只在 `decks/*.json` 的预审卡片里选。
- **L1.5 试用卡**：`decks/proposals/*.json`。当本地牌组承载不了产品的核心动作时（Phase 0.5 判出来），联网找到的新表达先落在这层——不给 `--deck` 就不可见、随机不可达、也不进 `deckFingerprint`，转正才并入 L1。它存在的前提是“先看清产品再决定熵源”，不是“抽不出来就上网瞎找”。
- **L2 种子**：seed 决定具体组合与微扰动；同 `project` + 同 seed + 同参数（`--base`/`--vary`/`--lock`/`--explore`）+ 同 decks/weights/history = 同结果。**seed 单独不是配方号**：换 `--base` 或往 `recipes/` 里多写一份配方，都会改变结果，这些前提都记在 `recipe.context` 里（`argv` 原文 + `deckFingerprint` 牌组指纹）。想让参数真的进熵源，用 `--strict-seed` 显式打开；默认不开，以保证既有 seed 的结果不变。
- **L3 经验**：每次交付后的用户反馈写进 `experiences/`；单次只做案例，重复出现或用户明确要求才升级为规则，规则改动必须人工确认。

**产品配方是该路线的唯一创作事实源。** 文案、分镜、预览、封面、MP4 从 `recipes/<project>-<seed>.json` 派生；故事用工程内的故事计划和批准素材，不为抽牌器伪造产品画像。

```bash
# 第一次：在牌组内抽一套完整配方
node scripts/pick.mjs --project my-film --seed 20261103-a --no-history

# 下一支：基于上一支配方，最多改 2 个轴
node scripts/pick.mjs --project next --base recipes/dsh-armory-depot-20261103.json --vary hook,transition --seed 20261103-b

# 只换世界；不兼容的轴自动重抽，记入 forcedAxes
node scripts/pick.mjs --project next --base recipes/dsh-armory-depot-20261103.json --vary world

# 校验 / 查看牌组
node scripts/pick.mjs --validate recipes/dsh-armory-depot-20261103.json
node scripts/pick.mjs --list
```

规则：

- 有 `--base` 时最多改 **2 个轴**；其余锁定。改 world 后，不兼容的 transition/caption/sound 自动重抽，写进 `forcedAxes`。
- 用户点名世界时用 `--lock world=...`（也可锁任意轴，如 `--lock sound=celestial`）：锁定在抽依赖轴**之前**生效，被锁的轴永不被改写，其余不兼容轴重抽并记入 `forcedAxes`，锁定项记在 `context.locked`。若你锁了一个世界根本不允许的组合，会直接 FAIL 而不是偷偷替换你的选择。
- 默认排除最近 3 份 recipe 的 world/hook；`--no-history` 关闭，`--allow-repeat` 允许重复。
- `banned: true` 的卡（参考片的暖光扫、半调、闪白、中下贴纸、riser/whoosh、四个地方钩子）默认永不选；它们只做对照与审计。
- `--explore 0.3` 是 epsilon-greedy：30% 均匀探索，70% 按权重。想更稳用 0，想探索用 0.5–0.8。
- 图片只随机 2 个轴：构图、光位/材质；文字、版式、品牌、安全区交给代码。封面从同一份 recipe 派生，不另起世界。
- 配方落盘时写入 `deckFingerprint`（decks + compatibility + weights 的摘要）。之后 `--validate` 若发现牌组已变，会明确提示「同 seed 重跑不保证同样的 picks」，而不是让你以为还能复现。牌组一改，旧配方的可复现性就到期了 —— 这是事实，不是 bug，只有记下来才可查。

评分与回填：`references/scorecard.md`。牌组/权重/兼容矩阵的维护：`references/controlled-randomness.md`。

---

## 1. 先判断任务类型

在影片简报记录 `filmType`，它不是新增 CLI 参数：

| 类型 | 判据 | 下一步 |
|---|---|---|
| `product_promo` | 介绍真实产品或引导使用，哪怕主角是卡通角色 | 以下 §0、§2 产品流程，画像/事实/配方继续生效 |
| `animation_story` | 角色故事、动画表演或情绪表达，不以证明产品功能为目的 | 先读 [动画流程](references/ai-animation-workflow.md)，执行 S0–S6，不走产品抽牌 |

**故事路线优先级**：产品专用的旁白占比/空白阈值、句数、固定幕长、关键词字幕、CTA、`fit` 与产品配方不适用；按故事事件节奏、真实台词/无声模式执行，详情留工程内，共享经验可用 `recipe=manual`。原创性、授权、确定性、预览确认和真实 QA 不放宽。没有参考片不伪造九轴对比。

每镜再选 `productionMethod=code/ai/hybrid/stock/footage/recorded`，不要改写产品的 `fit.verdict=local/trial/handmade`。前三个是**制作方式**，后三个是**素材来源**（图库图 / 实拍或录屏片段 / 自制拍摄）；选路判据、素材规格与授权台账见 [素材来源](references/asset-sourcing.md) §3。二维、三维、MG 按动作任务选方法，不默认整图推拉等于角色动画。

纯剪辑/转码和静态海报不套此流程；完全照搬参考片须先说明原创性问题。
**先确认**：目的、画幅、时长、帧率、语言、参考资产、声音模式；产品路线另查真实版本。已有答案不重复问，默认规格可用但执行前须核对工具能力。

---

## 2. 产品工作流（0–8，含 0.5；故事走 §1 指定的 S0–S6）

### Phase 0 — 拆参考片，只留下方法

先清点参考目录：成片 MP4、工程文件、旁白、时间轴、音效、字体、渲染脚本。

- 有 MP4：抽帧看镜头、转场、字幕、音效落点。
- 没有 MP4 但有完整工程：用 HTML/JS、narration、timeline、SFX 事件表重建；**明确告诉用户“成片 MP4 缺失，本次按工程拆解”**，不要假装看过原片。
- 没有播放数据：不要说“这是播放最好的风格”，说“按这支参考片的结构与方法判断”。

输出一张**拆解表**，至少六列：

| 维度 | 要记录什么 |
|---|---|
| 视觉 | 底色、主色、字体、材质、光、构图、记忆点 |
| 文案 | 钩子类型、卖点顺序、句式长度、CTA |
| 节奏 | 每幕时长、镜头任务、hold、快慢曲线 |
| 转场 | 硬切 / 运镜 / 光扫 / 遮罩 / 闪白，具体组合 |
| 字幕 | 位置、出现方式、关键词策略 |
| 声音 | 旁白声线、BGM、音效名单、密度、卡点 |

然后写两列：**可抽象**（强钩子、一个视觉世界、真实操作、关键词字幕、动作音效）和**禁止复制**（原句、分镜序列、幕长、转场、字幕动效、视觉母题、音效排列）。

模板与 filled example：`references/deconstruction.md`。

### Phase 0.5 — 产品画像与选路（先看清产品，再决定去哪儿抽卡）

**抽卡之前先看产品。** `pick.mjs` 不看你的产品：`bestFor` 只是给人看的字段，抽签逻辑里 0 处引用。所以“牌组贴不贴这个产品”必须在这一步判出来，判完把结论写进配方的 `fit`。

先出**产品画像卡**（四行，来自真实勘察，不联网也该做得出来）：

| 项 | 写什么 |
|---|---|
| 核心动作 | 用户对产品做的那一件事，动词原形（装 / 召回 / 清点 / 编排…） |
| 观众痛点 | 一句人话，不是功能名 |
| 可见证据 | 界面上真能截到、能读出的东西（决定什么能上屏） |
| 记忆点候选 | 一个具体物件或场面 |

再判**适配**：把「核心动作」对着各世界的 `motion` 与 `motifs` 逐个比（`node scripts/pick.mjs --list` 看牌面）。三问的第 3 问是闸门——**这个世界为什么只适合这个产品？** 注意区分两种情况，只有一种该加卡：

- 只是 `bestFor` 里没写你这个品类，但 `motion` 能承载核心动作 → **算适配**，别加卡。（atlas 的 `bestFor` 与 depot 重叠在“工具库/技能管理”，照样过闸，靠的是镜头语法换了而不是名字新。）
- `motion` 里没有任何动作能表达核心动作 → **不适配**。例：产品核心是“两人同时改一份东西、改动即时互见”，而现有世界的 motion 全是**单机**动作（conveyor、stamp impact、drawer、folder pull、radar sweep、sky rotate），没有一个能表达“共在”。

然后选路线，结论写进 `fit.verdict`：

| 路线 | 什么时候用 | 命令 |
|---|---|---|
| A `local` | 本地牌组够用（默认） | `node scripts/pick.mjs --project p --seed s` |
| B `trial` | 确实缺表达，且缺口能一句话说清 | 联网检索候选表达 → 照 `decks/proposals/_TEMPLATE.world.json` 写一张**试用卡**（必带 `source.urls` + `source.evidence` + 自带 `compat`）→ `node scripts/pick.mjs --lock world=<新id> --deck decks/proposals/<新id>.json` → `node scripts/doctor.mjs` |
| C `handmade` | 你已经知道要哪组组合，随机只是噪声 | 抄 `recipes/_template.json` 手填 `picks` → `node scripts/pick.mjs --validate <配方>` |

试用卡**不进正式牌组**：不给 `--deck` 就看不见、随机也抽不到（实测 80 组 0 命中），`deckFingerprint` 不变，所以它不污染任何既有配方的可复现性。转正条件是「本片跑通 QA + 第 2 个独立项目再次需要」，五步见 `references/product-fit-and-routing.md` §5。

**本阶段联网找新表达卡，不拿搜索结果充当产品事实。** 动画制作方法和当前平台能力也可查官方资料；上屏数字仍指回代码 / README / package.json / 测试，搜来的宣传说法不上屏。

如果三问全答不上，不往牌组硬塞“氛围世界”：确实是无产品证明诉求的动画故事/表演，按 §1 转故事路线；仍声称介绍真实产品但缺事实时先补证据。纯实拍概念素材可考虑其它可用视频工具，不能假装完成了产品适配。

### Phase 1 — 抽配方，再找产品真相与新世界

先按 Phase 0.5 选好的路线抽配方（A 本地 / B 试用卡 / C 手写校验），确认 `world / hook / transition / caption / sound / rhythm`，并把 `fit.verdict` 与 `fit.reason` 落进配方。用户已经指定世界时用 `--lock world=...`，不要为了随机而随机。

**事实表先于文案。** 每个上屏数字、按钮、状态、命令、版本号都要有出处：代码行、README、package.json、测试。没有出处的数字不上屏；演示数据必须角标标注。

然后从产品名 / 核心动作 / 用户痛点里找一个**新的视觉世界**。一句话概念必须能同时回答：

1. 观众第一眼看到什么？
2. 产品在画面里以什么方式被“使用”？
3. 这个世界为什么只适合这个产品？

如果产品动作能落到一件**实物**上（抽屉、卡片、标签、印章、星标、票据），优先实物，不要默认做全屏 UI 面板。实物要能用真实的图层、阴影、透视和材质感承载文字；文字仍由代码叠加，不交给图片生成。案例：`references/case-dsh-armory-vault.md`。

不要复用参考片的视觉母题，也不要复用你上一支片子的皮肤。一个片子只建立一套世界。可选配方与推导方法：`references/visual-worlds.md`；机器可读版本是 `decks/worlds.json`。

产出一张**差异化矩阵**（9 个轴：钩子、叙事顺序、镜头语法、幕长、转场、字幕系统、视觉母题、声音排列、CTA）。任意 3 个轴仍然高度相似，就重做。详见 `references/originality-gates.md`。

### Phase 2 — 文案、分镜、节奏表

先写**旁白**，再写**字幕关键词**，最后写**分镜**。不要先画画面再硬配字。分镜按 recipe 的 `rhythm` 展开；`storyboard[].budget` 是预算，可 ±10%，但不要重排幕序。

- 10–15 句短句；一句只做一件事；每句 8–24 个汉字为宜。
- 结构：钩子 → 命名 / 承诺 → 证据 / 操作 → 反转 / 广度 → 行动。
- 钩子不要复刻参考片。参考片用“四个地方”，你可以用“你还记得几件？”；参考片用“一条命令装好”，你可以用“装得明白，也用得回来”。
- 字幕只留关键词，不逐句复读；关键词块可以独立于正文。
- CTA 要具体，但不要照抄参考片的动词与句式。
- 口播文本要为 TTS 做归一化：`MCP` → `M C P`，`DSH` → `D S H`，`sha256` → `sha 二五六`；避免 TTS 把缩写读成英文整词。

分镜表至少包含：时间、幕名、时长、旁白、画面动作、字幕关键词、转场、音效落点。45 秒默认 5–6 幕；每幕一个动作链，不要平均用力。模板与 6 幕示例：`references/story-rhythm.md`。
动画镜头再按 [制作流程 §4](references/ai-animation-workflow.md#4-产品路线怎样借用这些方法) 补关键姿态和低成本动态预演，沿用配方与旁白时间源，不另造一套幕序。

### Phase 3 — 4:3 网页高仿真预览

**先做网页，不要直接渲染 MP4。** 网页是低成本试错与确认构图的工具，也是最终逐帧渲染的唯一时间源。AI 视频素材需先过 [接入边界](references/ai-animation-workflow.md#5-现有脚本的能力边界)，不能把两次 rAF 当作视频已解码到目标帧。

硬要求：

- 舞台固定 1440×1080（4:3），按窗口等比缩放，不裁切；
- `renderAt(t)` 是纯函数：同一 `t` 必须得到同一帧，不能有跨帧累加；
- 不写 CSS `transition` / `@keyframes` 来做正片动画；所有动画由 `renderAt` 逐帧写样式；
- 播放器：播放/暂停、进度拖拽、重播、全屏、0.5×/1×/1.5×/2×、字幕开关、静音/音量、章节跳转；
- 抽屉：分镜/时间码/文案/差异化/规格；
- 首屏用一张钩子帧做 poster，点播放从 0 开始；
- **非代码素材先登记再上屏**：每条素材进 `assets/asset-manifest.json`（来源、许可、日期、哈希），过 `scripts/check_assets.py`。视频素材用 `scripts/frames_from_video.py` 抽成 PNG 序列（自动规整 fps、4:3 裁切、查断号、对账帧数）走帧精确路径，单张静图配代码动效；**不直接嵌 MP4**——长 GOP 素材实测会掉到 −52 帧。规则见 [素材来源](references/asset-sourcing.md) §5–§6。
- 图片一律 `await img.decode()`，序列索引 `Math.min(count-1, Math.floor(t*fps))` 夹取；`window.__ready` 只代表脚本声明就绪，不代表素材可用（实测晚到 1.5s 的素材丢了前 17 帧）。
- 所有 CSS/JS/音频/SFX 加 `?v=` 版本号，避免改了文件浏览器还在跑旧版。

数据契约、播放器、纯函数写法、音频同步、缓存与 QA：`references/preview-contract.md`。

### Phase 4 — 旁白、音效与混音

- 旁白逐句 TTS（Edge TTS 可用），每句可单独调 rate / pitch / gap；旁白是全片唯一对齐全源。
- 先缓存原始 mp3，再统一过润音链；改链时用 `--from-cache` 重润，保证时间轴不漂移。
- 不要默认“有底噪”。先量：静音段是否数字零、语音帧 4–8k 能量、最大瞬态跳变、削顶。用户说“有杂音”时再按句量 20ms 帧的 p10/p5，先找离群句；单句气口优先换 TTS take（标点/停顿变体），不要整片降噪或门限。
- 齿音/高频气息：`5.2kHz -1.5dB` + `6.8kHz` 8 阶低通是一个保守起点；不要为了降噪把 5k 以下也压暗。
- 底拍如果要保留，用纯低频 thump；不要带 700–4500Hz 的噪声点击，否则在旁白下像杂音。
- 音效优先自产（numpy 合成），不要直接复用参考片的音效名单与卡点排列。
- **出表即测高频**：`build_sfx.py` 打印每个材质的 4.5k 以上占比，>0.30 当场标 ⚠ 并给母带链（4.8k 低通 + 7k -7dB + 限幅 -14 dBFS）。2026-11-05 实测 13 个材质里 8 个占比 0.40–0.59、峰值 -1.4～-6.2 dBFS，压在旁白下面就是用户口中的“杂音”——修音效，不要整片降噪旁白。
- 以上三步都有脚本，不要手算秒数：`scripts/build_voice.py`（口播稿 → 逐句 TTS + 润音链 + 样本级句子时间轴）、`scripts/build_sfx.py`（13 种材质，每个材质独立随机流，改一个不会动到其它）、`scripts/build_timeline.py`（句子时间轴 + 镜头规格 → `timeline.js` 与 VTT/SRT）。完整命令：`references/audio-and-render.md` §7。
- 混音留余量；AAC 编码可能让峰值高于源 WAV，必须解码后按立体声逐声道复验。

完整链、噪声诊断与 ffmpeg 参数：`references/audio-and-render.md`。

### Phase 5 — 预览 QA 与确认门

在给用户看之前，自己先过（两条有机器检查，不要靠记性）：

```bash
python -m unittest discover -s scripts/tests -p "test_*.py"                  # 闸门自身必须先全绿
node scripts/check_engine_discipline.mjs --engine <项目>/assets/engine.js   # 舞台层复位 + 签名覆盖
python scripts/pacing_report.py --timeline <项目>/assets/timeline.json      # 1× 节奏闸门
python scripts/check_assets.py --manifest <项目>/assets/asset-manifest.json --commercial  # 素材台账（纯代码绘制则跳过并记 N/A）
```

测试不全绿不许进确认门，也不许出片 —— 否则这些闸门等于没人跑的装饰。

- 无 JS 错误；字体加载完成；voice readyState 正常；
- 1440×1080 与 1366×768 窗口都不裁切；4:3 比例实测 1.3333；
- 播放、暂停、拖拽、重播、倍速、字幕、静音、音量、全屏、章节、抽屉都能用；
- **纯函数 seek**：从 0 逐帧推到 t，再直接 seek 到 t，比较所有可见元素的 rect/opacity/transform；必须一致；
- 关键帧接触表检查构图、文字不溢出、字幕不挡主体、音效不压旁白。

把预览、原创文案、分镜/节奏表、差异化说明一起交给用户。**用户明确认可预览与差异化说明后，才进入 MP4。**

### Phase 6 — 渲染 MP4

从 `recipe.fixed.format` 读取画幅；默认：1440×1080 / 30fps / H.264 High / CRF 19 / AAC 192k / 48kHz。

- headless Edge + CDP 打开 `preview.html?render=1`，按 `i/fps` 调 `__setTime`，逐帧 PNG；
- 每帧等两个 `requestAnimationFrame` 再截；
- 已存在的帧跳过，支持断点续跑；但 `out/frames/_stamp.json` 记输入指纹（页面 + assets 哈希 + 视口），指纹变了就拒绝复用旧帧，要强行复用需显式 `--resume-anyway`——实测有过中断进程留下 388 帧、下个进程静默混批的情况；
- 未知参数一律打印用法并退出 2，不进入渲染分支（以前 `--help` 被忽略，直接开渲整片并覆写出品）；
- 音频不经过浏览器：用旁白 + SFX 事件表在 ffmpeg 里 `adelay` 钉帧、`amix=normalize=0`，事件时刻按 `ceil(t*fps)/fps` 量化；
- 不要用 `-shortest`（旁白比成片短会截画面）；用 `apad` + `-t 帧数/fps`；
- 先探真峰值，再给全片统一母线 trim；不要只压旁白或只压音效；
- 落版先保 CTA：最后一句旁白结束前不要收光圈/淡出，命令完整可读 ≥1.2s；
- 制作参数（画幅/分辨率/帧率）只放抽屉与交付说明，不进画面；画面脚注放品牌、版本、比喻声明；
- 编码后清理 PNG 帧目录，保留 `meta.json`、`audio-check.wav`、接触表。

命令与坑：`references/audio-and-render.md`。

`scripts/render.mjs` 已随包附带，不再依赖别的项目。开工前先 `node scripts/render.mjs --preflight`；分阶段跑 `--frames-only`（先看构图）→ `--audio-only`（先听混音）→ `--encode-only`（再出片）。没有 NVENC 会自动降级 libx264。

### Phase 7 — 成片 QA 与交付

至少检查；含动画镜头时另过 [动作与连续性验收](references/animation-motion-and-qc.md)，正常速度观看不能被接触表替代：

- 画幅、帧率、编码、帧数、容器时长；
- 音频时长覆盖整片、峰值 ≤ 0 dBFS、逐声道 0 削顶；
- 音画包络偏移 ≤ 1 帧；
- 10 个左右关键帧“成片解码帧 vs 现截帧”的平均差与大幅差；采样时刻取**每幕落定后 ≥0.3s**，不要踩在换幕起点 —— 百叶快门与片尾淡出那几十毫秒本来就是黑帧，采到只会得到一个真确但无意义的报警。“画面为空”的判据看**结构**（亮度标准差与亮像素占比），不看平均亮度：atlas / tower / blueprint / depot 都是 `#05–#08` 暗底，有内容的落定帧 mean 只有 5~7。
- 接触表；文件大小与 SHA-256；
- 交付 README：成片链接、规格、QA 结果、重出命令、已知限制。
- 产物落盘后把路径回填到 recipe 的 `deliverables`：**必须声明 `projectRoot`**（技能包外的影片工程根目录），其余路径一律相对它。技能包不存素材，也不要把交付物写进技能包。
- 用了外部素材的工程，`assets/asset-manifest.json` 随工程一起保留：它是授权台账，不是可选附件。交付说明里写清素材来源与许可，别让对方事后猜。

`scripts/qa_mp4.py` 是一份可直接改路径使用的成片 QA 脚本。它和 render.mjs 用同一套 ffmpeg 探测（`PROMO_FFMPEG` → PATH → 剪映自带），不再要求 ffmpeg 必须在 PATH 上。加 `--ref` 做逐帧回捞时必须带 `--project-root <影片工程目录>`，否则重截会在错误的目录里找页面。

### Phase 8 — 交付后反馈与自更新（默认执行）

成片和封面交付后，不要停在“文件给你了”。直接运行 `node scripts/feedback.mjs --prompt`，把输出发出去（或按同样措辞发一条消息）。问 3+1 个问题：

1. 整体 0–10 分（≥8 很好 / 6–7 可用 / <6 不行）；
2. 最想保留的一点（钩子 / 节奏 / 视觉 / 文案 / 声音 / 封面 / 工程）；
3. 最想改的一点（能指到秒数或某一幕最好）；
4. 这次经验怎么沉淀：仅本次 / 可复用 / 可直接改规则。

判定与落盘：

- ≥8 + 无硬失败 + 可复用 → `success`，写复用清单，`promotion: candidate`；
- 6–7.9 → `conditional`，写适用条件，不升级规则；
- <6 或任一硬失败 → `fail`，写根因 + 已验证修法；
- 没回 / 不评 → `unrated`，只留元数据，不追问。

```bash
node scripts/feedback.mjs --new --project <slug> --recipe <path>   --score <0-10> --tags "视觉,音频" --summary "..." --quote "..." --generalizable
node scripts/feedback.mjs --validate
node scripts/feedback.mjs --index
```

**单次反馈不许改规则、权重、牌组。** `candidate` 需要 2 个独立项目重复，或用户明确要求（记 `promotionBasis: "explicit-request"`，此时 `conditional`/`fail` 也能合法记 candidate）；先把 diff 给用户看，确认后才改 `SKILL.md` / `references/` / `decks/` / `weights.json`，并 bump 版本 + 写 changelog。不要问七项评分卡，不要拿“没问题”当好评。

完整问法、判定表、硬失败清单与升级闸门：`references/feedback-loop.md`。

---

## 3. 产品设计模式（按需迁移，不是故事路线的强制模板）

故事动画的动作、停顿、对白/无声与镜头验收按 [动作与 QA](references/animation-motion-and-qc.md)，不套本节的口播阈值或 CTA。

### 3.1 钩子

| 类型 | 句式 | 适合 |
|---|---|---|
| 提问 | “你还记得几件？” | 用户有“装了很多但失控”的痛点 |
| 损失 | “装完就再没被叫过” | 工具体积/上下文成本 |
| 反差 | “四个地方，现在只剩一个入口” | 入口分散 |
| 倒计时 | “三秒，找到上周装的那个” | 搜索/召回 |
| 物件 | 一件物品从画面穿过 | 有强符号的产品 |

选一个参考片**没有用过**的钩子。不要把参考片的钩子换个名词。

### 3.2 叙事骨架

- **盘点 / 审计**：有什么 → 谁没用 → 怎么调用 → 怎么搬走。
- **装配**：四块部件 → 合体 → 运转 → 落版。
- **救援**：混乱现场 → 找到问题 → 修复 → 恢复秩序。
- **对比**：旧流程 vs 新流程，但不要做成功能清单。
- **一天**：早上找工具 → 中午装错 → 晚上复盘。
- **星图救援**：失联 → 星图 → 来路 → 暗星 → 牵引 → 落版。适合“能力很多、叫不出”的工具库；星图只做看法，不是产品功能。
- **档案抽屉**：没亮过 → 一个抽屉 → 钉星标 → 搜/叫出名字 → 落版。适合“装过但找不回”的技能/工具库；抽屉、标签、星标是实物道具，不是 UI 面板。案例：`references/case-dsh-armory-vault.md`。

### 3.3 节奏

- 默认 **41s（5×8.2s）**；45s 只给信息层确实更厚的片子；5–6 幕；单幕 5–9 秒。
- **1× 就必须是舒服的速度**：出片前量旁白占时比 ≥0.80、每幕最长空白 ≤0.35s（落版除 CTA hold 外 ≤1.0s）；不达标就压 `gap_after`（0.16–0.22）与幕间 `pad`，不许靠拉长镜头凑时长，也不许默认“用户会开倍速”。
- 密度曲线：中密 → 蓄力 → 高密 → 峰值 → 高密 → 收束。
- 一句旁白配一个动作；一个动作只占一个视觉焦点。
- 关键信息落定后 hold ≥ 0.8s；硬切前后留 0.2–0.3s 呼吸。
- 不要为了凑时长整体拉慢镜头；用呼吸、转场压缩和信息层补时间。

### 3.4 字幕

- 关键词，不是逐句。
- 位置要么中下，要么左下/左上；一旦选定，全片不要漂移。
- 出现方式：打印式揭示、遮罩、打字、盖章——选一种，和视觉世界一致。
- 关键词块可以独立成色块，不要和正文抢同一行。

### 3.5 声音

- 旁白是主轴；音效只托动作，不铺满。
- 底拍要么没有，要么纯低频；不要用高频 click 当“节奏”。
- 转场音不要用参考片的 riser / whoosh / shimmer 组合；换一套材质（机械、纸张、继电器、伺服、扫描）。
- 混音目标：旁白清晰、音效可辨、峰值留 1–3 dB 余量。
- **不要默认铺一条持续房间底噪。** 底噪不是“电影感”的同义词；用户说“配音有杂音”时，先量句间：旁白句间是否数字零、混音句间是否有持续低频/高频。持续底噪优先整条删，再谈压缩/门限。单句气口与持续底噪是两类问题：前者换 TTS take（见 §6），后者删床。案例：`references/case-dsh-armory-vault.md` §6。

---

## 4. 现有产品工程契约（短版）

故事仍需统一时间轴与确定性画面；无旁白、纯无声和视频素材的适配不能从本例推断为已实现，先读 [工具能力边界](references/ai-animation-workflow.md#5-现有脚本的能力边界)。

```js
window.PROMO = {
  dur: 44.94, fps: 30, size: [1440, 1080],
  voice: "assets/audio/voice.m4a",
  sfxDir: "assets/sfx/",
  gains: { voice: 1, sfx: 0.62 },
  scenes: [{ id, title, code, start, end, hud, cues: { ... } }],
  captions: [[start, end, "字幕", "关键词"]],
  sfx: [{ t, name, g, pan }],
};
```

- `scenes[].cues` 用绝对秒；幕内动作全部相对幕起点。
- `captions` 与 `sfx` 由旁白时间轴生成，不手写死。
- `renderAt(t)` 里不读 `Date.now()`、不用 `Math.random()`、不写回元素状态。
- 挂在 `#stage` 的共享元素（调暗 / 遮罩 / 颗粒 / 字幕 / HUD / 脚注 / 淡入淡出）必须在 `renderAt(t)` 开头复位，并全部列入 `signature()`；否则顺序渲染继承上一幕的状态、单帧 seek 不继承，只有逐帧回捞抓得到。
- `?render=1`：隐藏 UI、停掉音频、固定 1440×1080、暴露 `__ready / __duration / __fps / __setTime(t)`。
- 播放器与导出共用同一份 `timeline.js`；倍速只改 `t` 的推进速率。

细节与代码：`references/preview-contract.md`。

---

## 5. QA 闸门

以下是产品全量清单。故事沿用适用的画面/交互/确定性/成片技术检查，并执行 [故事验收](references/animation-motion-and-qc.md)；语音节奏、产品 fit、无声片音频等不适用项分别记 N/A 与理由。未实现或没测过的功能记未验证/阻塞，不能记 N/A 或 PASS。

**预览**

- [ ] 无 JS 错误
- [ ] 4:3 比例 1.3333，1440/1366 窗口不裁切
- [ ] 播放 / 拖拽 / 重播 / 倍速 / 字幕 / 静音 / 音量 / 全屏 / 章节 / 抽屉
- [ ] 纯函数 seek：0→t 逐帧 vs 直接 seek，元素签名一致
- [ ] 关键帧无文字溢出、无遮挡、无空镜
- [ ] `check_engine_discipline.mjs` 通过（舞台层复位 + 签名覆盖）
- [ ] `pacing_report.py` 通过（1× 不需要倍速）
- [ ] `scripts/tests` 全绿（用例数与耗时写进交付说明）
- [ ] 舞台层共享件已在 `renderAt` 开头复位，且已进 `signature()` 清单
- [ ] 节奏闸门：旁白占时比 ≥0.80、每幕最长空白 ≤0.35s（落版除 CTA hold 外 ≤1.0s）
- [ ] 用了非代码素材时 `check_assets.py` 通过（来源可溯 / 许可在白名单 / 商用一致 / 哈希可核 / 无跨镜重复）；纯代码绘制记 N/A 并说明素材全部由代码生成

**成片**

- [ ] 画幅 / 帧率 / 编码 / 帧数 / 时长
- [ ] 音频覆盖整片、峰值 ≤ 0、逐声道 0 削顶
- [ ] 音画偏移 ≤ 1 帧
- [ ] 10 帧回捞对比通过
- [ ] 配方 `fit.verdict` 不再是 TBD；判 `trial` 时 `research.trialDecks` 有记录且文件还在
- [ ] `scripts/tests` 全绿（出片前再跑一次，防止中途改脚本）
- [ ] 接触表、SHA-256、交付说明
- [ ] 交付后按 Phase 8 发 3+1 回访；不等回复，不阻塞交付

**常见假阳性**：ffmpeg `-ac 1` 的立体声下混会用 0.707 系数，可能制造“假削顶”。检查削顶时必须解码立体声逐声道，不能只看单声道下混。

---

## 6. 十二个常见坑

1. **把参考片的“方法”当成“风格”**：换色、换字、换贴纸不算原创；产品九轴至少 7 项明显不同（任意 3 项同/近就重做）。故事按 [原创性计数](references/ai-animation-workflow.md#2-所有路线共用的边界) 排除共同缺失项，不凑七项、不伪造比较，仍禁止复制关键表达。
2. **先画画面再配字**：会导致功能被硬塞、事实不准。先事实表，再文案，再分镜。
3. **把不存在的字段放上屏**：Skill 卡只有装于/来源/分类，就不要放“上次调用”；零调用属于工具账本。每个字段先找出处。
4. **CSS 动画混进正片**：`renderAt` 与 CSS transition 打架，seek 会花。正片动画全部由 JS 逐帧写样式。
5. **音频每帧写 currentTime**：会听出沙沙/咔哒。用“自由走 + 迟滞纠偏”（±0.15s 不动，±0.30s 才 seek）。
6. **AAC 峰值只看源 WAV**：编码后可能过冲。必须解码 MP4 按立体声复验。
7. **缓存**：改了 CSS/JS/音频不加版本号，预览会跑旧文件；所有资源带 `?v=`，交付时提醒强制刷新。
8. **把视觉比喻写成产品功能**：产品里没有“星图”，口播却说“把能力连成一张星图”，观众会期待一个不存在的功能。第一次出现必须用“比作/像/是看法”，中段交回真实界面，落版/封面加脚注。
9. **用整片降噪掩盖单句气口**：先按句量 p10/p5，找离群句；单句气口先换 TTS take（标点变体），再考虑低通/门限。`afftdn` 对这类气口通常无效，整片门限会切字尾。
10. **把持续房间底噪当“氛围”**：28s 的棕噪 + 45/90Hz 在句间 -42 dBFS，用户会听成“配音有杂音”；旁白本身量下来是数字零。先删持续底噪、再压机械音效，不要先给旁白加降噪。案例：`references/case-dsh-armory-vault.md` §6。
11. **先抽卡再看产品**：`pick.mjs` 不看产品（`bestFor` 不参与抽签），只能给一组方法自洽但可能贴错产品的配方。产品先按 Phase 0.5 比核心动作与 `motion`/`motifs`，确实缺表达才出试用卡。三问全答不上时回到 §1：产品片先补事实，纯动画故事/表演走 S0–S6，不硬抽也不一概拒绝。
12. **素材当氛围板，忘了留痕**：图库图、录屏、AI 场景板一进来就要登记 manifest——许可只覆盖图片本身，不覆盖图里的**人脸、商标和他人作品**；影视截图抽帧不因"注明出处"就获得授权；同一张底图跨镜复用会被判视觉贫乏。抓不到来源的素材宁可不做这个镜头。见 [素材来源](references/asset-sourcing.md) §2 / §9。

---

## 7. 参考文件

**AI 素材生成子技能**：`subskills/seedance-20/SKILL.md`（Seedance 2.0，MIT，v6.7.0，2026-11-12 整包并入）。
需要该模型的二维/三维动画、角色表演、实拍级镜头、空镜、转场或首尾帧素材时进入，按其 Load Map 读取二级技能；其他模型按官方入口查证，不混用参数。
它只负责提示词与素材分支，**不替代**已选产品/故事路线的预览确认、合成与验收；原子技能的导演、参考和重试规则不另抄一份。付费生成前确认 provider、素材、动作与额度，未确认不发起。

- [references/ai-animation-workflow.md](references/ai-animation-workflow.md) — 影片类型/制作方法、故事 S0–S6、产品动画接入、声音模式、现有工具不支持的边界。
- [references/animation-motion-and-qc.md](references/animation-motion-and-qc.md) — 动作卡、动画原理、二维/三维差异、接触/连续性、镜头验收与最小返工。
- [references/ai-animation-sources.md](references/ai-animation-sources.md) — 15 个来源页面、平台差异、证据层级；使用具体模型前核实，不充当已实测声明。
- [references/asset-sourcing.md](references/asset-sourcing.md) — 素材来源六类与授权实况（Pexels / Unsplash / Pixabay 逐条红线，核对 2026-11-13）、选路决策树、素材规格（≥1080px、4:3 裁切余量）、三种进工程形态与确定性、`asset-manifest.json` 契约与许可白名单、与原创性九轴的分层口径、授权红线。
- `references/deconstruction.md` — 参考片拆解表、可借/禁借清单、filled example。
- `references/product-fit-and-routing.md` — Phase 0.5：产品画像卡、适配三问怎么判、A/B/C 三条抽卡路线、试用卡 schema 与转正五步、联网证据要求。
- `references/originality-gates.md` — 9 轴雷同自检、改写策略、失败案例。
- `references/story-rhythm.md` — 钩子类型、6 幕骨架、45 秒预算、字幕/CTA 规则。
- `references/visual-worlds.md` — 13 套视觉世界配方（夜班盘点台 / 蓝图检修 / 塔台调度 / 档案卷宗 / 实验台 / 野战手册 / 星图台 / 多屏展陈墙 / 明暗双场 / 发布会舞台 / 文档台 / 像素闯关 / 宣纸手卷）。后 6 套与 3 张转场、3 张字幕、2 张节奏卡由 2026-11-06 从 `D:\Motiontemplates`（MotionGit 公开模板）拆方法增补，卡内 `source` / `borrowed` / `notCopied` 记明出处与边界。
- `references/preview-contract.md` — 4:3 舞台、播放器、纯函数、音频同步、缓存。
- `references/audio-and-render.md` — TTS 润音链、降噪诊断、SFX 合成、ffmpeg 渲染、QA 坑。
- `references/facts-and-copy.md` — 事实表模板、演示数据标注、口播归一化、文案反例。
- `references/controlled-randomness.md` — v2 牌组、兼容矩阵、权重、seed、加卡/调权重规则。
- `references/scorecard.md` — 盲评 7 项、淘汰线、性能回填。
- `references/case-dsh-armory-atlas.md` — 2026-11-04 能力星图案例：参考片选择、比喻合同、单句气口、编号/落版/封面修复与验收数字。
- `references/case-dsh-armory-vault.md` — 2026-11-10 暗夜军械库案例：从“科技风被否”到电影感实物世界的**来源渠道**、AI 场景板、黄铜/深青配色、实物道具、七句/27.89s、持续底噪修复与验收数字；世界未注册进 decks，避免改牌组指纹。
- `references/feedback-loop.md` — 交付后 3+1 问法、success/conditional/fail/unrated 判定、经验落盘、规则升级闸门与回滚。
- `experiences/` — 每次交付的反馈账本（`_template.md` + `INDEX.md`）；只存项目/配方/分数/短引用，不存素材与个人信息。
- `scripts/feedback.mjs` — 经验条目新建、schema 校验、索引重建、候选列表。
- `scripts/render.mjs` — 通用逐帧渲染/混音/编码；在项目根跑，或用 `--root <项目>` 指定；先跑 `--preflight` 查工具链（Node 版本、浏览器、ffmpeg 编码器、Python 与 numpy/scipy/Pillow/edge-tts）。
- `scripts/build_voice.py` — 口播稿 json → 逐句 TTS + 润音链 → 样本级句子时间轴 `voice_timeline_<slug>.json` 与 `voice_<slug>.wav/.m4a`；`--from-cache` 只重润不改时长。
- `scripts/build_timeline.py` — 句子时间轴 + 镜头规格 → `timeline.js`（`window.PROMO`）、`narration.vtt/.srt`（整句口播，给平台外挂字幕）、`captions.vtt/.srt`（上屏关键词）。
- `scripts/build_sfx.py` — 13 种材质自产音效（numpy，无参考片音源）；每个材质独立随机流，改/加/重排材质不会影响其它材质字节。
- `scripts/tts_chain.py` — 润音链通用件（解码/裁静/EQ/压缩/淡入淡出/真峰值限幅/样本级拼装），被 `build_voice.py` 调用。
- `scripts/check_engine_discipline.mjs` — 舞台层纪律机器检查：挂在 `#stage` 且被幕渲染器写过的元素必须每帧复位、必须进 `signature()`；另带 good/bad 两个 fixture 证明它能变红。
- `scripts/pacing_report.py` — 节奏闸门：开场 lead / 幕首 lead / 句间空白 / 跨幕空场 / 片尾空场 / 旁白占时比 六项分别判 PASS/FAIL，阈值可用参数覆盖。
- `scripts/check_assets.py` — 素材台账闸门：来源可溯（非自制必须 `source.url`、必须有 `retrievedAt`）、许可在白名单内且与商用声明一致、署名文本齐备、`sha256` 与实际内容一致、同一素材跨镜复用拦截、序列 `frameCount` 与磁盘帧数一致、`derivedFrom` 可解析；`--stamp` 回填哈希，`--commercial` 按商用片判定，`--allow-license` / `--allow-reuse` 为显式放行口。
- `scripts/frames_from_video.py` — 视频 → PNG 序列，绕开「嵌 MP4 不帧精确」：按工程 fps 规整、`cover`/`contain`/`none` 画幅处理、序号连续性校验（断号退出 1）、实际帧数与期望帧数对账、`--emit-manifest` 吐台账片段。已有帧时拒绝覆盖，需 `--overwrite` 防混批。
- `scripts/fetch_asset.py` — 素材落地闸门：按**明确 URL** 下载，或按 `--file` 把已下载的本地文件复制进工程（零网络依赖，Pexels 停发新 key 时的主路径），自动算哈希、写台账、立刻过闸门。四道拦截：非 http/https、>200MB、magic bytes 判容器（防盗链页常伪装成 `image/jpeg`）、同内容重复登记。**不做爬站抓图**——Pexels ToS 禁系统性采集，Unsplash API 禁转存，各通道现状见 [素材来源](references/asset-sourcing.md) §2.2。
- `scripts/tests/` — 11 个文件、138 用例（`python -m unittest discover -s scripts/tests -p "test_*.py"`）：参数白名单与帧指纹、meta 指纹、账本判定、timeline resolver、sfx 可复现与高频点名、qa_mp4 自检、preflight 体检、素材台账闸门、抽帧序号与对账、素材下载与去重、两个闸门自身。
- `scripts/doctor.mjs` — 注册表体检：active world 是否都有兼容条目、悬空引用、永不可达的卡、权重缺项、文档世界数；**轴数口径**（SKILL 声明 = gates 表行 = 配方 `fixed.qa` = pick.mjs 标签）；**deliverables 路径根**；**试用卡完整性**（compat / 撞 id / `source.urls` + `evidence`）；**选路留痕**（`fit` / `research` 一致性与试用引用可解析）。不一致退出码 1。加卡/禁卡、改配方字段、动 proposals 后必跑；`--root <dir>` 可对别的目录树跑（坏例自测用）。
- `decks/*.json` — world / hook / transition / caption / sound / rhythm 牌组（含 banned 对照卡）。
- `decks/proposals/_TEMPLATE.world.json` — 试用卡模板（L1.5）：联网找来的新表达先落在这里，必带 `compat` 与 `source` 证据，不给 `--deck` 就不可见不可达。
- `compatibility.json` — world × 其余轴的合法组合。
- `weights.json` — 权重与 explore 比例。
- `recipes/_template.json`、`recipes/dsh-armory-depot-20261103.json` — 配方模板与 seed 配方。模板即字段契约：`fixed.qa` 用 `originality-9-axis`，交付后 `deliverables` 写 `projectRoot` + 相对路径。
- `scripts/pick.mjs` — seeded 抽牌器、兼容性校验、prompt 块、storyboard 输出；`--deck decks/proposals/<id>.json` 注入试用卡（不给就不可见），`--allow-trial` 才让试用卡进随机池，`--fingerprint` 打印当前牌组指纹（手写配方要盖它），配方自动留 `fit` / `research` 空位与 `context.trialDecks` 记录。
- `scripts/qa_mp4.py` — 成片规格/音频/接触表/逐帧回捞 QA（改路径即用）。
- `evals/evals.json` — 真实任务测试提示。

## 8. 参考实现

如果工作区里有之前做过的片子（例如 `promo-depot/`、`promo-atlas/`、`promo-vault/`），可以把它当作**工程实现参考**：看 `assets/engine.js` 的纯函数、`assets/player.js` 的播放器、`scripts/render.mjs` 的逐帧导出、`scripts/qa_mp4.py` 的验收。`promo-vault/` 还演示了“AI 场景板 + 实物道具 + 无 UI 面板”的写法；不要复制它的暗夜军械库皮肤与文案——只复用工程管线和检查方法。

一句话：**先分产品与故事，再选合适的动画方法；产品从真实功能出发，故事从事件与表演出发，共用原创性、预览确认与实际验收，把有来源的方法和真正跑过的能力分开。**
