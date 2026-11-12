# Changelog

## v2.7.1 — 2026-11-12

实测「完全无声成片」导出链路时发现两处缺陷，修掉并补回归测试。不改渲染契约、不动牌组/权重/配方，也没让无声片子走混音链路。

### 修复

- `scripts/qa_mp4.py`：无音轨 MP4 在峰值判定处崩 `TypeError`（`peak` 为 `None` 却参与 `:.2f` 格式化），整份报告只剩堆栈。新增 `is_silent()` / `audio_checks()` / `report()`：无音频流或 0 秒音轨时，音频三项合并打印 `N/A`，画面/容器/帧数照常判定；有音频流但 astats 没给峰值时判失败并写明"未测得"。`info()` 顺带把无音频流的显示从 `?` 改成 `无音轨`（原来无法区分"没有音轨"和"解析失败"）。
- `scripts/render.mjs`：`window.PROMO.voice` 为空时，混音输入退化成工程目录，只报 `Error opening input file <工程目录>`，看着像路径写错。新增 `requireBaseTrack()`，直接说明"本工程没有基础音轨"并指回 `references/ai-animation-workflow.md §5` 的无声选路，退出码仍为 1。
- `scripts/tests/test_qa_mp4.py`：新增 6 个用例——无音频流记 N/A、0 秒音轨记 N/A、正常片仍判 PASS、削顶与热峰值算失败、音频短于成片算失败、有音频流但峰值未测得算失败且不抛异常。

### 无声导出实测

- 最小确定性工程 2.00s / 60 帧 / 30fps / 1440×1080：`--frames-only` → `ffmpeg -framerate 30 -i f%05d.png -c:v h264_nvenc -pix_fmt yuv420p -an`（本机 ffmpeg 19.6.0，只有 `h264_nvenc`，无 `libx264`）。
- 成片 105,746 B；`ffmpeg -i` 只有 `Stream #0:0 Video`，无 Audio 流；回捞 60/60 帧，逐帧 MAD 0.974–1.367（均值 1.042），MAD>2.0 的帧 0。
- 修补后 `qa_mp4.py` 对该成片输出 `PASS`（音频项 N/A）；`render.mjs --audio-only` 退出 1 并给出上文可读理由。

### 边界（不要外推）

- 仍**没有一键无声导出命令**：取帧之后编码那一步要自己调 ffmpeg，命令与验收口径见 `references/ai-animation-workflow.md §5`。
- 未覆盖：大素材（视频/字体/大图）加载时序、`libx264` 回退路径、带音轨但纯静音的工程、真实影片工程（≥20s、多镜头、重素材）。
- 实测用的是合成最小工程，验证的是导出链路，不代表动画质量。

### 验证

- `python -m pytest scripts/tests -q`：61 用例通过（16.03s，原 55 + 新增 6）。
- `node scripts/render.mjs --preflight`：本机 Node 22.22.2 / Edge / ffmpeg 19.6.0 / Python 3.12 四包齐备。
- `node scripts/doctor.mjs`：PASS，9 个旧配方缺 `fit` 的历史 WARN 不变。

## v2.7.0 — 2026-11-12

用户先要求联网研究、补充前确认，随后明确选择“同时纳入纯动画故事”。本版补方法与路由，不新增模型后端或视频素材渲染实现。

### 新增

- 双路线：`product_promo` 保留产品画像、事实表与受控配方；`animation_story` 支持二维/三维/MG、角色故事、无旁白与纯无声规划，不强套口播占比、产品证据或 CTA。
- `references/ai-animation-workflow.md`：制作方式选路、故事 S0–S6、动态分镜、参考职责、接受片段续接、声音模式、统一时间轴与现有工具边界。
- `references/animation-motion-and-qc.md`：动作卡、预备/主动作/收势、时长/间距、刚性与弹性边界、接触/漂移/连续性验收、最小返工。
- `references/ai-animation-sources.md`：15 个官方/专业来源页面，区分动画原理、平台能力与整合建议；Runway/Firefly/Veo/万相仅按已核实入口解释，不承诺当前所有模型的统一参数。
- `evals/evals.json` 新增 17–25 共 9 个行为用例：卡通产品片、无声故事、对白留白、机械装配、拒绝失败末态、平台/预算边界、视频解码时序、真实确认与反馈，以及无声/无字幕/无 CTA 故事的原创性计数。

### 衔接与边界

- 主入口按需加载动画资料；产品节奏、预览、音频、产品适配、原创性和反馈参考文件补路线适用范围，避免旧规则误伤故事。
- 故事共同缺失的表达记 N/A，不计同/异、不硬凑七个差异轴；可比项任意三轴同/近仍重做，直接复制关键表达不因计数少放行。产品九轴与机器标签不变。
- 核对现有 `feedback.mjs` 已支持 `recipe=manual`，故事共享经验无需伪造产品配方或改 schema；详细素材与 QA 留在影片工程。
- 明确 `filmType` / `productionMethod` 是规划字段，不是现有 CLI 参数；故事计划不伪装成产品 recipe 或已支持的运行 schema。
- 明确现有完整渲染依赖实际基础音轨、纯零峰值探测存在限制、两次 rAF 不保证 MP4 帧解码完成。无声成片或视频素材接入仍须在具体工程适配与验证，本次未做生成或成片端到端实测。
- 不改 scripts、牌组、权重、兼容矩阵、既有配方及 Seedance 子包；不付费生成、不安装模型、不自动提交或发布。

### 验证与复核

- 原有 pytest 回归 55 项通过（最终自动轴运行 16.70 秒）；注册表 doctor PASS，保留 9 个旧配方缺 fit 的历史 WARN。
- 33 个本地 Markdown 链接/锚点通过；校验器用不存在文件与不存在锚点自证能报错。主入口 486 行，保护范围逐文件 SHA-256 与改前快照一致。
- `recipe=manual` 在临时副本的 new/validate/index 实跑通过，没有写入真实反馈账本。
- 第二轮 9 个场景的核心路由/授权/真实性边界未见违背；按全部预期细节计为 6 项完整、3 项未展开工程细节，后者用 3 个明确阶段的探针补测通过。仅为文字行为评估，不记作生成成功率或成片端到端验证。
- 双轴：自动 95、独立 LLM 97、等权总分 96。审查发现的故事原创性计数冲突已修复并复审关闭；历史案例本机绝对路径告警保留，相对链接正则误报另有复现说明。分数仅针对本次方法/路由增量，不代表整包零问题。

## v2.6.1 — 2026-11-12

`--preflight` 从"只查浏览器/ffmpeg/页面"扩成完整工具链体检，给拿到技能包的其他人用。

### 新增

- `scripts/render.mjs --preflight` 增加：Node 版本（需 22+，逐帧渲染用内置 WebSocket）、Python 解释器（`PROMO_PYTHON` → `python` / `python3` / `py`）、Python 版本（需 3.10+）与 numpy / scipy / Pillow / edge-tts 四个包的版本。
- 缺包时直接打印该解释器下的 `pip install` 命令；缺 `edge-tts` 额外提示需要联网。缺任一项退出码 1，不再出现"preflight 说齐备、跑到 Phase 4 才抛 ModuleNotFoundError"。
- ffmpeg 两个 H.264 编码器都没有时，preflight 现在直接判失败（以前只打印一行警告仍退出 0）。
- 新增 `scripts/tests/test_preflight.py`（3 用例）：报告完整性、缺 Python 必须非零退出、`PROMO_PYTHON` 指错时回退到 python/python3。

### 验证

- `node scripts/render.mjs --preflight`：本机输出 Node 24.19.0 / Python 3.12.6 / numpy 2.4.4 / scipy 1.18.1 / Pillow 12.2.0 / edge-tts 7.3.1，页面缺失走"技能目录不是项目根"提示并退出 0。
- 反向自测（证明闸门会变红）：清空 `PATH` + `PROMO_PYTHON` 指向不存在路径 → `Python ❌`、退出 1；`PROMO_PYTHON` 指向空 venv → 四个包全 ❌ 并给出 pip 命令、退出 1。
- `python -m unittest discover -s scripts/tests -p "test_*.py"`：55 用例全绿（19.9s）。

## v2.6.0 — 2026-11-12

把两条并行演进的线合并成一条：store 侧的 v2.3–v2.5（案例、13 套世界、渲染与音频修复、Seedance 子技能）并入仓库侧未发布的 v2.2.0「产品画像 / 试用卡」工作。牌组、权重、兼容矩阵与既有配方的 `picks` 未改，`deckFingerprint` 保持 `084c84003bdc`。

### 并入（产品画像线，原基于 v2.1.0）

- `SKILL.md` 新增 **Phase 0.5 产品画像与选路**：四行画像卡（核心动作 / 观众痛点 / 可见证据 / 记忆点候选）→ 适配三问 → A `local` / B `trial` / C `handmade` 三条路线；判完把 `fit.verdict` 写进配方。三问全答不上时明确判「本 skill 不适用」，转到其他视频 skill。
- §0 分层加 **L1.5 试用卡**：`decks/proposals/*.json` 只在显式 `--deck` 时可见，不进 `deckFingerprint`，转正才并入 L1。
- 新增 `references/product-fit-and-routing.md`（画像卡与 filled example、适配判据、三条路线命令、联网证据红线、转正五步、反模式）。
- `scripts/pick.mjs`：`--deck`（可逗号并列）、`--allow-trial`、`--fingerprint`；配方自动写 `fit` / `research` 留痕与 `context.trialDecks`。
- `scripts/doctor.mjs`：新增轴数口径、`deliverables` 路径根、试用卡完整性、选路留痕四组闸门。
- `evals/evals.json` 新增 14–16（错配不硬抽、拒绝随手加卡、C 路线手填 + `--validate`）；配方模板与三份历史配方补 `fit`。
- §5 成片 QA 加「`fit.verdict` 不再是 TBD；`trial` 时 `research.trialDecks` 有记录」；§6 补第 11 个坑「先抽卡再看产品」。

### 并入（Seedance 2.0 子技能，v2.5.0）

- `subskills/seedance-20/`：Seedance 2.0 技能包整包移入（MIT，作者 Iamemily2050，v6.7.0，207 个文件，29 个二级技能）。`SKILL.md` §7 写明入口、边界（只出提示词与素材，不替代网页舞台与逐帧渲染）与付费生成前的确认要求。原独立注册链接已移除。

### 修正（合并时暴露的口径漂移）

- `references/controlled-randomness.md` 牌组清单从旧估值改为实测：world 7→13、transition 6→9、caption 5→8、rhythm 5→7。
- 9 份 v2.3/2.4 期间新增的配方 `fixed.qa` 从 `originality-8-axis` 统一为 `originality-9-axis`（与 v2.1.1 口径一致）。
- `recipes/dsh-armory-supply-20261105-b.json` 的 `deliverables` 补 `projectRoot` 与 `pathRule`，路径改为可解析的相对路径。

### 验证

- `node scripts/doctor.mjs`：PASS（牌组 / 兼容矩阵 / 权重 / 文档计数 / 既有配方 / 轴数口径 / 产物路径根 / 试用卡 / 选路留痕）。剩 9 条 WARN：v2.3/2.4 期间的历史配方没有 `fit` 判定，未凭猜测补写，留待各自复盘时回填。
- `python -m unittest discover -s scripts/tests -p "test_*.py"`：52 用例全绿（11.4s）。
- `node scripts/pick.mjs --validate`：12 份配方全部退出码 0；`feedback.mjs --validate` PASS。
- Seedance 子包内部相对链接 705 条，0 断链。

## v2.5.0 — 2026-11-12

用户要求把 seedance-20 收成本 skill 的子技能，以后只调用 heshao-ai-video-v1。整包并入，不改渲染管线、牌组与既有配方。

### 新增

- `subskills/seedance-20/`：Seedance 2.0 技能包整包移入（MIT，作者 Iamemily2050，版本 6.7.0，207 个文件 / 5.2 MB，含 29 个二级技能）。原 `.qoder\skills\seedance-20` 独立注册链接已移除，技能列表只保留本 skill 入口。
- `SKILL.md` §7：新增「AI 素材生成子技能」入口与边界——只在需要 AI 生成实拍镜头、空镜、转场、首尾帧时进入；只出提示词与素材片段，不替代网页舞台与逐帧渲染；付费生成前先确认 provider / 素材 / 动作 / 额度。
- `SKILL.md` description：补「AI 生成实拍级镜头、空镜、转场、首尾帧」触发词。

### 验证

- seedance-20 内部相对链接 705 条，0 断链（搬移前后同口径）。
- `node scripts/doctor.mjs` 仍 PASS；牌组、兼容矩阵、权重、配方指纹未变。
- 技能列表已确认不再出现独立的 seedance-20 条目。

### 回滚

原包完整备份在 `D:\skilllocker\store\_backup\seedance-20-6.7.0-20261112.zip`；还原后重建 `.qoder\skills\seedance-20` 符号链接即可。

## v2.4.0 — 2026-11-10

用户明确要求把“暗夜军械库”这次的设计思路与来源渠道写进 skill。新增案例与三条可迁移规则；**不改牌组/权重/兼容矩阵**，旧配方指纹不变。

### 新增（案例）

- `references/case-dsh-armory-vault.md`：dsh-armory v2.5.1 暗夜军械库完整复盘。内容包括：
  - **来源渠道总表**：用户 brief 与否决原话、参考片（Titanic / Kling AI 品牌片）、产品事实（README/package/docs）、同产品旧片（depot/atlas/signal/supply）、Qoder ImageGen 五张场景板、电影摄影语汇、Edge TTS + numpy SFX、skill 工程与 QA；
  - **产品功能 → 实物道具**映射：抽屉=技能看板位置、星标=收藏、呼号单=搜索、没亮的标签=零调用账本、命令=落版；
  - 视觉配方（`#03070a` / `#0b2526` / `#d8ae6a` / `#f1e8d8`、Noto Sans SC 900 + GeistMono、五张 1024×768 AI 板、旧纸/黄铜/星标/呼号单）；
  - 七句旁白、五幕 27.89s、九轴差异、验收数字、复现路径与边界；
  - 失败迭代：v1 科技风被否、深色 UI 标签、贴纸星标、金色 UI 铭牌、命令晚 4s、持续底噪。

### 新增（可迁移规则）

- `SKILL.md` Phase 1：产品动作能落到实物（抽屉/卡片/标签/印章/星标/票据）时，优先实物，不要默认全屏 UI 面板；文字仍由代码叠加。
- `SKILL.md` §3.2：新增叙事骨架「档案抽屉」：没亮过 → 一个抽屉 → 钉星标 → 搜/叫出名字 → 落版。
- `SKILL.md` §3.5 / §6：新增第 10 个常见坑「把持续房间底噪当氛围」。用户说“配音有杂音”时，先量旁白本身与混音句间；旁白句间数字零、混音句间有 -42 dBFS 的 45/90Hz 嗡声，说明噪声来自底噪/音效，不是 TTS。持续底噪优先整条删，不要先给旁白加降噪。
- `references/audio-and-render.md` §3：新增「持续底噪 vs 单句气口（vault 实测）」：单句气口换 TTS take；持续底噪删床；两类问题不要用同一种整片降噪。

### 文档

- `SKILL.md` §7 登记 `references/case-dsh-armory-vault.md`；§8 参考实现加入 `promo-vault/`（AI 场景板 + 实物道具 + 无 UI 面板）。
- 版本 `2.3.0 → 2.4.0`。

### 验收数字（本案例）

- 27.89s / 1440×1080 / 30fps / 837 帧（MP4 未渲染）；5 幕 / 7 句 / 23 个音效事件（7 sub + 16 动作音） / 无 BGM。
- 52 个单元测试全绿；舞台层纪律通过；节奏 89.0%、片尾空场 1.20s；纯函数 seek 12 个时刻一致；1366×768 冒烟通过；页面错误 0。
- 新混音峰值 -2.97 dBFS、RMS -20.4 dBFS、0 削顶；纯音效峰值 -7.45 dBFS；混音 4.5kHz 以上 4.3%。

### 已知边界

- 暗夜军械库**未注册进 `decks/`**，不改变牌组指纹；要注册成随机卡，必须另补 `compatibility.json` / `weights.json` / `decks/worlds.json`，跑 `doctor.mjs` 与 `pick.mjs --validate`，并让用户确认 diff。
- 案例里的 AI 场景板只做空间与光，不含文字；`/pdf-kit · 0 次调用` 是演示数据，画面与片尾均标注。
- 成片 MP4 已渲染：`out/final/dsh-armory-vault-4x3.mp4`（837 帧 / 27.90s / H.264 1440×1080 / AAC 48kHz）。成片 QA PASS：峰值 -3.02 dBFS、RMS -20.38 dBFS、0 削顶、音画偏移 +0.0ms、9 帧逐帧回捞平均差 0.99–1.40 / 大幅差 0%。SHA-256 `ff3a0c2e4177fc212337da97efd89a9321025560ba7170068c6ddf41eb2e8ca7`（字幕二次放大到 42px 后重渲）。
- 设计方向获用户认可，但不替代 0–10 成片评分；3+1 回访已随交付发出，暂不记 `experiences/` 分数。

---

## v2.3.0 — 2026-11-05

把 v2.2.0 评审里剩下的 6 条做完（3 medium + 3 low），并补上"防呆网自己也要能被证明会破"这一层。

### 新增（机器检查，不再是文档约定）

- `scripts/check_engine_discipline.mjs`：舞台层纪律检查器。只认登记在 `R.*` 上、且**被某个幕渲染器写过**的 `#stage` 共享元素，要求它在 `renderAt` 调用 `RENDERERS` 之前被复位（或由 overlay 每帧重写），并且必须出现在 `signature()` 里。退出码 0/1/2，附 good/bad 两个 fixture（bad 例就是 2026-11-05 落版压灰 bug 的最小复刻）。
- `scripts/pacing_report.py`：节奏闸门量化器。把留白拆成**开场 lead / 幕首 lead / 句间空白 / 跨幕空场 / 片尾空场 / 旁白占时比**六项分别判，避免把设计需要的呼吸当缺陷报（第一版就是把开场 lead 0.5s 误判成死空气）。阈值 `--open-lead/--scene-lead/--line-gap/--cross-scene-air/--tail-air/--speech-min` 可覆盖。
- `scripts/tests/` 从 3 个文件扩到 6 个、**52 用例 / 约 11s**：新增 `test_qa_mp4.py`（回捞工具自检：相同帧为 0、已知块差为 55/50%、尺寸不符必须报错、暗底有结构≠空帧、纯白≠有内容、包络偏移能量出 30ms）、`test_build_voice.py`（归一化表逐键生效且不动 display、空 display 快速失败、润音链不改样本数、真峰值不越上限、RMS 对齐而非峰值对齐、`--from-cache` 一次都不联网）、`test_gates.py`、`test_meta_and_ledger.py`。

### 修复

- `scripts/qa_mp4.py` `diff()` 不再静默取左上角交集：尺寸不一致直接 `ValueError` 并提示统一 `--width/--height`。旧行为会让回捞在视口变化后退化成"只比一小块"，PASS 不可信。
- `scripts/qa_mp4.py` `frame_is_blank()` 判据从「既暗又无结构」收紧为「无结构即空，或又暗又无亮像素」：界面帧没加载出来是**纯白**，旧判据会放它过关，而白 plate 恰是最可能的渲染事故。真实画面永远有台面/网格，std 不可能 <6，不引入假阳性（已用交付片 11 帧复验，std 27–63 全 OK）。
- `scripts/qa_mp4.py` 抽出纯函数 `envelope_offset()`，音画偏移检测从此可单测（不再需要造 MP4）。
- `scripts/render.mjs`：`meta.json` 现在写进 `srcFingerprint`；`--encode-only / --audio-only` 读到与当前页面/素材不符的指纹时拒绝并给出两条出路（`--meta-only` 刷新 / `--force-stale-meta` 显式放行）。旧行为是 timeline.js 改了却照旧事件表混音，字幕与音效落点全错位且无提示。
- `scripts/feedback.mjs`：`promoted` 现在必须 (a) 写 `promotionBasis`、(b) `changes` 非空、(c) changes 里带路径的条目真实存在、(d) `CHANGELOG.md` 有版本段落（可选 `ruleVersion` 必须能在 CHANGELOG 里找到）。堵掉"记了升级却没落地"。

### 流程强制（评审第 2 轮当场闭环的两条）

- `SKILL.md` Phase 5 / §5 预览 QA / §7 成片 QA 都把 `python -m unittest discover -s scripts/tests` 写成硬性勾选项，并明写「测试不全绿不许进确认门、不许出片」。52 个用例如果没人跑，就只是装饰。
- `references/facts-and-copy.md` §1 事实表加「是否上屏（是/否/仅脚注）」列，并给一行填好的样例：本机数量/路径/账号名默认「否」，删不掉的界面帧数字三选一（演示数据集重拍 / 放大裁切 / 保留+脚注）——把「开工前问死口径」从散文变成表格里必须填的格子。

### 文档

- `SKILL.md` Phase 5 与 §5 预览 QA 清单加入两个新检查器作为固定步骤；§7 登记 `check_engine_discipline.mjs` / `pacing_report.py` / `scripts/tests/`。版本 2.2.0 → 2.3.0。

### 已知边界

- 六个节奏阈值的标定数据只有 skilllocker 一支片（旁白占时 87.2%、句间 0.20–0.22、跨幕 0.34–0.40、片尾 1.60 超标），第 2 个项目复现后再收紧；`pacing_report.py` 文件头已写明这条。
- 纪律检查器是正则级静态分析，识别的是命名约定（`R.*` + `RENDERERS`/`renderS\d+`）；内联匿名幕函数、或把共享元素存在别的容器里，它看不见。所以它只能挡"忘复位"，不能证明"复位正确"。
- 交付中的 skilllocker 成片按新闸门复检：`s03 幕首 lead 0.50s`、`s04 幕首 lead 0.75s`、`片尾空场 1.60s` 三项超标 —— 这是按旧默认值剪的历史事实，用户已明确"这次不用改，说的是以后"，故不重渲。


## v2.2.0 — 2026-11-05

由 skilllocker（实验台 44.07s）一支片的交付反馈 + dual-axis 双轴评审（自动 50 / LLM 72 / 最终 61）驱动。评审推翻了我自己先前的优先级：两个 `render.mjs` 的操作性陷阱比文案规则更该先修。

### 修复（脚本）

- `scripts/render.mjs` **未知参数不再静默开渲**：参数白名单 + `--help/-h`，未知项打印用法并 `exit 2`，绝不进入渲染分支。实测旧行为：`--help` 直接开始截 1322 帧并覆写 `out/final/film.mp4`（约 7 分钟 + 覆盖出品）。
- `scripts/render.mjs` **帧目录输入指纹**：`out/frames/_stamp.json` 记录页面内容哈希 + assets（js/css/json 取内容、PNG/WAV 取 size+mtime）+ 视口。已有 PNG 且指纹不符时拒绝续跑并给出两条出路（清目录重截 / 显式 `--resume-anyway`）。守卫提到开浏览器之前，因此可被无浏览器单测覆盖。实测旧行为：被中断的进程留下 388 帧，下一个进程静默复用并出片。
- `scripts/build_sfx.py` **去掉重复的 `__main__` 入口**：文件末尾有两个入口块，`main()` 跑两遍，13 个材质被合成并写盘两次（`--list` 也会打印两遍材质清单）。
- `scripts/feedback.mjs` **升级依据不再自相矛盾**：新增 `promotionBasis: repeat | explicit-request | none`；`candidate` 现在接受「success + generalizable」或「用户明确要求（需 userQuote 原话）」，`promoted` 必须写依据。旧校验器只认前者，导致 SKILL.md 写的"或用户明确要求"这条合法路径根本无法入账（实测 conditional+candidate 直接 FAIL，只能降级成 none，升级线索丢失）。
- `scripts/build_sfx.py` 只加测量不改合成：同 seed 重产 13 个 wav 与已交付的 `sfx_raw` **逐字节一致**（已验证）。

### 新增（质量闸门）

- **高频闸门**：`build_sfx.py` 对每个材质打印 4.5kHz 以上能量占比（整段 2048 点分块平均 + 起音两个值取大），>0.30 标 ⚠ 并打印可复制的母带链与增益建议。依据：2026-11-05 实测 13 个材质里 8 个超标（relay 0.43 / scan 0.40 / paper 0.57 / snap 0.46 / switch 0.41 / type 0.59 / shutter 0.44 / ratchet 0.44，峰值 -1.4～-6.2 dBFS），42 秒 26 个事件压在旁白（语音窗口 RMS -17.2 dBFS）下面，用户反馈成「配音有杂音」；压暗后混音 4.5k+ 占比 0.016、逐声道峰值 -2.00 dBFS、非语音窗口 -37.8 dBFS。
- **节奏闸门（用户明确要求"以后"）**：`SKILL.md` §3.3 与 `references/story-rhythm.md` §1/§4 默认时长从 45s 改为 **41s（5×8.2s）**，并加可判定的上限：旁白占时比 ≥0.80、每幕最长空白 ≤0.35s、落版除 CTA hold 外 ≤1.0s；不达标压 `gap_after`（0.16–0.22）与幕间 `pad`，禁止用拉长镜头凑时长或默认用户会开倍速。依据：实测旁白占时已达 87.2%（字数不缺），慢在幕间留白 0.45–0.50s 与落版空白 1.60s，用户结论「1× 偏慢，要靠倍速才舒服」。
- **舞台层复位规则**：`references/preview-contract.md` §3/§9 与 `SKILL.md` §4/§5 新增强制项 —— 挂在 `#stage` 而非 `.scene` 的共享元素（调暗/遮罩/颗粒/字幕/HUD/脚注/淡入淡出）必须在 `renderAt(t)` 开头复位，且全部列入 `signature()`。依据：S03 的 `.dim` 设到 0.20 后没人复位，顺序渲染时漏进落版把它压灰 20%，而单帧 seek 不继承 —— 只有逐帧回捞抓得到，代价是重渲 1322 帧。
- **本机数据口径前置**：`references/facts-and-copy.md` §1 新增一条 —— 技能数量/格位数/体积/账号名/本机路径这类"真实但不该上屏"的数字，默认按不上屏准备，并在事实表阶段让用户三选一（演示数据集重拍 / 放大裁切出画 / 保留+脚注）。依据：v1 把 56 / 392 / 16 / 48 / 27.6 MB 全上屏，用户看预览才要求撤掉，文案字幕返工一轮并多跑一次 TTS。

### 新增（测试）

- `scripts/tests/test_render_guard.py`：`--help`/未知参数/手误参数必须 exit 2 且不进渲染；指纹不符必须在开浏览器前 exit 1；`--resume-anyway` 放行；同指纹可续跑且「跳过已存在」计数正确。
- `scripts/tests/test_build_timeline.py`：幕起点与首尾相接、六种时刻表达式、`total` 公式、sfx 排序与量化契约（timeline.js 存未量化时刻，预览与混音各自用 `ceil(t*fps)/fps`），以及 6 类必须 `SystemExit` 的错（atLine 越界 / 字幕行越界 / 字幕窗口反向 / 音效超成片 / 未知时间键 / sceneStart 指向不存在的幕）。
- `scripts/tests/test_build_sfx.py`：同 seed 逐字节相同、换 seed 至少改动一个噪声材质、高频材质必须被点名并给出母带建议、入口只有一个且 `main()` 只跑一遍。
- `scripts/tests/fixture/preview.html`：最小可渲染页面（实现 `window.PROMO` + `__ready/__duration/__fps/__setTime` 契约），供守卫测试用。
- 全套 20 用例通过（约 8s）：`python -m unittest discover -s scripts/tests -p "test_*.py"`。

### 文档结构

- `SKILL.md` 补 `## When to Use` / `## Prerequisites` / `## Workflow` / `## Output` / `## Resources` 五个规范章节（指针式，不复制正文，避免两处漂移）；`## Output` 明确一支片的完整交付物清单。版本 2.1.0 → 2.2.0。
- `references/feedback-loop.md` §5 升级闸门改为按 `promotionBasis` 判定；`experiences/2026-11-04-dsh-armory-atlas.md` 补 `promotionBasis: explicit-request`。
- 新经验条目 `experiences/2026-11-05-skilllocker.md`：`conditional`（用户未打分，`score: null`，按 feedback-loop 的"还行"档判），`promotion: promoted` + `promotionBasis: explicit-request`。


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
