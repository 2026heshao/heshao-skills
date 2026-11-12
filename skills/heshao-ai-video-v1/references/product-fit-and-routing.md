# 产品适配与抽卡选路 / Product Fit & Routing

Phase 0.5 的手册：**先看清目标产品，再决定去哪儿抽卡。**
范围仅限 `product_promo`；纯动画故事/表演走 [动画流程](ai-animation-workflow.md)，不因没有产品操作而被拒绝，也不伪造画像和 `fit`。代码/AI/混合制作的选择不是本页 local/trial/handmade 配方路线。

这一步存在的理由是一条代码事实：`bestFor` 在 `decks/worlds.json` 里写了 7 处，`scripts/` 里 0 处引用。`pick.mjs` 不知道你的产品是什么，它对"这个牌组贴不贴"完全无感——你问它要配方，它就在牌组内给你一组**方法自洽但可能贴错产品**的组合。错配不会报错，只会在你画到分镜、写完旁白之后才暴露，代价是整支重做。

所以判定归人（或归 AI），一致性归脚本：本文件负责前者，`doctor.mjs` §9–§10 负责后者。

## 1. 产品画像卡

四行，做完再谈牌组。素材来自真实勘察（代码、README、界面、package.json），**不需要联网**：

| 项 | 写什么 | 反例 |
|---|---|---|
| 核心动作 | 用户对产品做的那一件事，动词原形 | "提升效率"（这是结果，不是动作） |
| 观众痛点 | 一句人话 | "解决工具管理难题"（功能名堆砌） |
| 可见证据 | 界面上真能截到、能读出的字段/状态/命令 | "智能推荐"（截不出来就不能上屏） |
| 记忆点候选 | 一个具体物件或场面 | "科技感"（不是物件） |

filled example（示例产品，非真实数据）：

```
核心动作：两个人同时改一份清单，改动互相即时可见
观众痛点：共享文档每次都要刷新、不知道谁在改
可见证据：在线成员头像、光标位置、变更行高亮、历史记录条目
记忆点候选：一条被两个人同时拉动的线
```

## 2. 适配判据

把「核心动作」对着各世界的 `motion` 与 `motifs` 逐个比（`node scripts/pick.mjs --list` 看牌面），再用 SKILL.md Phase 1 的三问收口，其中第 3 问是闸门：**这个世界为什么只适合这个产品？**

关键是区分两种"不像"，只有一种该动牌组：

| 情形 | 判定 | 动作 |
|---|---|---|
| 品类名不在 `bestFor` 里，但 `motion` 能承载核心动作 | **算适配** | 路线 A，别加卡；在 `fit.reason` 写为什么能借 |
| `motion` 里没有任何动作能表达核心动作 | **不适配** | 路线 B，出试用卡 |
| 你已经明确知道要哪几个轴的组合 | 与适配无关 | 路线 C，手写 + `--validate` |
| 三问一个都答不上（没有可展示的真实操作、没有能上屏的事实） | 暂不进入产品抽牌 | 回主 SKILL §1：产品片先补事实；纯动画故事/表演转 S0–S6，不伪造产品画像 |

真例（可查）：atlas「星图台」的 `bestFor` 是 capability map / discovery / tool library / skill manager，与 depot 在"工具库、技能管理"上**重叠**，但 2026-11-04 那支过闸——原因不是名字新，而是镜头语法、转场、字幕、声音、CTA 全换了一套（`references/case-dsh-armory-atlas.md` §2）。

假例（示例）：产品核心是"多人实时协同、改动即时互见"，而现有 7 套世界的 motion 全是**单机**物件动作——`conveyor / magnetic snap / stamp impact / tool roll / lid flip`（depot）、`line draw / dimension close / section reveal / paper fold`（blueprint）、`radar sweep / strip slide / light blink / panel switch`（tower）、`folder pull / page turn / label stick / drawer`（archive）、`drip / liquid line / clamp / measure`（lab）、`binder flip / map pull / tape peel / zip`（field）、`sky rotate / star ignition / constellation draw / aperture iris`（atlas）——没有一个表达"两个人同时在一份东西上"。（以上动作表来自 `decks/worlds.json` 实测，不是印象。）

**别把"我懒得比对"写成缺卡。** 判 `trial` 必须能填出 `whyLocalDeckFailed` 那句具体话，指向某个轴；写"不太搭""不够高级"的一律视为判错。

## 3. 三条路线

### A `local`：本地牌组（默认）

```bash
node scripts/pick.mjs --project my-film --seed 20261105-a --no-history
```

抽完把配方的 `fit` 改掉：`verdict: "local"`、`productActions: [...]`、`reason: "一句话，能查"`。`fit.verdict` 停在 `TBD` 会被 doctor 记 WARN，交付闸门（SKILL §5 成片）过不去。

### B `trial`：联网第二熵源 → 试用卡

```bash
# 1) 检索，边查边记：查了什么、看了哪些页、原文关键段、差异声明
# 2) 照模板写卡
cp decks/proposals/_TEMPLATE.world.json decks/proposals/vault.json   # 换成你的 id
# 3) 只在本项目使用：显式注入 + 锁定
node scripts/pick.mjs --project my-film --seed 20261105-b \
  --lock world=vault --deck decks/proposals/vault.json
# 4) 体检
node scripts/doctor.mjs
```

试用卡的行为边界（都是实测，不是设计意图）：

- 不给 `--deck`：`--list` 不显示它，`--lock world=vault` 直接报 `unknown world id`。
- 给了 `--deck` 但不给 `--allow-trial`：它**进不了随机池**。80 组种子实测命中 0 次，其余 7 个世界正常分布；要随机可达得显式加 `--allow-trial`（同批实测 10/80 ≈ 12.5%，与权重 1/13 + 探索 0.3 一致）。
- 指纹不变：`deckFingerprint` 由未注入试用卡的正式牌组算出，实测注入前后同为 `2f57e06a064b`；既有配方的 `--validate` 不会因为一张试用卡而变成"不可复现"。
- 撞 id 直接拒：`--deck` 一张与正式卡同名的卡，pick 报 `已存在于牌组`，doctor 报 `不许覆盖或蹭正式卡`。

### C `handmade`：手填 + 机器校验

```bash
cp recipes/_template.json recipes/my-film-20261105c.json   # 改 picks 六个格子
node scripts/pick.mjs --validate recipes/my-film-20261105c.json
# FAIL transition drawer-slam not compatible with atlas (allowed: eclipse-wipe, hard-cut)
```

手抄的配方没有牌组指纹（`--validate` 会 NOTE 一句"没有记录牌组指纹"），补盖一下才知道日后能不能复现：

```bash
node scripts/pick.mjs --fingerprint          # 打印当前指纹，现值 2f57e06a064b
# 写进配方的 context.deckFingerprint
```

适用场景：错配不是缺世界，而是你早知要哪组组合、随机只添噪。`fit.verdict` 记 `handmade` 并写理由；`--validate` 通过即可当配方用，`fixed.qa`、`deliverables` 契约照旧。

## 4. 联网检索的操作规范

联网**只用来找新的视觉表达**，不用来找产品事实。上屏的每个数字、字段、状态仍要指回代码 / README / package.json / 测试（`references/facts-and-copy.md`）；搜来的说法一律不上屏，包括竞品页面上的数字。

每张试用卡的 `source` 必须填全四件，缺任一件 doctor 判 FAIL：

| 字段 | 为什么不能省 |
|---|---|
| `queries` | 日后判断是不是重复搜过、换词能不能再挖 |
| `urls` | 唯一能追溯的东西 |
| `retrievedAt` | 联网结果每次不同；没有时间戳，"当时看到什么"无法申辩 |
| `evidence` | 原文关键段（≤5 行）或本地截图路径。只留 URL 等于什么都没留——页面会改会删 |
| `originality` | 借方法不借表达的落点：指出没照抄哪几样（母题/配色/字体/构图/镜头顺序） |

检索姿势：找**同类问题的别的解法**，不要找同款片的截图。有效问法是"XX 类产品怎么做可视化""如何表现 Y 这个动作"，看的是别人的**母题与动作设计**；直接搜"最佳产品宣传片"会把你拉回复刻参考片的老路（SKILL §6 第 1 坑）。

红线：搜到的具体表达不得原样进卡——母题、配色、字体、构图、镜头顺序至少改掉三样，写进 `originality`。这条与 9 轴闸门同源（`references/originality-gates.md`），只是参照对象从"那支参考片"变成"这批搜索结果"。

## 5. 试用卡转正五步

转正 = 把 L1.5 并进 L1，**这一步会改牌组指纹**，所以要有节制。

1. 确认条件：本片跑完整 QA 并通过交付；且第 2 个独立项目再次需要这张卡（或用户明确说"以后都要这个"）。单支片子跑通不足以转正——那只是一次成功，不是规则。
2. 把 `card` 并入 `decks/worlds.json`，`compat` 并入 `compatibility.json`，`weights.worlds.<id> = 1` 起步。
3. 文档同步：SKILL.md §7 的「N 套视觉世界配方」、`references/visual-worlds.md` 加一节。漏改会被 doctor 的文档计数拦下。
4. 删除 `decks/proposals/<id>.json`，并把引用过它的配方里的 `research.trialDecks` 说明一句「卡已转正，见 CHANGELOG vX」——否则 doctor 会报 `试用卡文件被删了？`。
5. `node scripts/doctor.mjs` 必须 PASS，`CHANGELOG.md` 记版本与影响（旧 seed 的可复现性从此刻到期，这是事实不是 bug）。

## 6. 反模式

- **抽完再找产品理由**：先有结论再找证据，等于没做 Phase 0.5。画像卡在前，判定在后。
- **为了新鲜感加卡**：牌组会从"7 套预审世界"退化成"每次都在抽卡"（`controlled-randomness.md` §10）。
- **拿搜来的数字上屏**：第二熵源只管表达，不管事实。
- **试用卡跨项目偷用**：`trialFor` 声明给 A 项目却被 B 用了，doctor 记 WARN。要用就先转正，或明确改 `trialFor` 并在新配方里说明。
- **把"不适用"处理成"缺卡"**：产品没有可展示操作时硬造一个世界，产出会是一支穿着工装的空片。
- **静默覆盖正式卡**：靠撞 id 检查拦住了，别绕过 `--deck` 直接改 `decks/*.json` 来"临时试"。

## 7. 这套闸门会拦什么

`node scripts/doctor.mjs`（§5b、§9、§10）逐条：试用卡缺 `compat`／缺 `source.urls`／缺 `evidence`／与正式卡或彼此撞 id／`kind` 非法／引用不存在的卡或 banned 卡 → FAIL；缺 `trialFor`／缺 `whyLocalDeckFailed`／缺 `promoteWhen` → WARN；配方 `fit.verdict` 非法或与 picks 里的试用卡矛盾、`trial` 却没记 `research.trialDecks`、试用卡文件已删、`rejectedCards` 缺 why → FAIL；老配方没 `fit`、`verdict` 仍 `TBD` → WARN（旧配方不回改，但交付闸门不放过没填的）。宪法侧还锚了三处具体文字：`**L1.5 试用卡**`、`### Phase 0.5 —`、`decks/proposals`——缺任一说明实现与文档脱节，直接 FAIL（只查 "L1.5" 这种子串会让闸门假绿：删掉一条 bullet 还剩一条）。

正常路径实测（副本里跑，真包不动）：

```bash
cp -r . /tmp/fit-demo && cd /tmp/fit-demo
node scripts/pick.mjs --project demo-coop --seed 20261105-coop --no-history \
  --lock world=coop --deck decks/proposals/coop.json --out recipes/demo-coop-20261105-coop.json
#   world   双人账房 (coop)
#   trial   world/coop ← decks/proposals/coop.json  来源 1 条
node scripts/doctor.mjs            # PASS
node scripts/pick.mjs --validate recipes/demo-coop-20261105-coop.json
#   FAIL - unknown world: coop      ← 不给 --deck 就用不了，这是设计：试用卡不会悄悄变成全局资产
```

坏例自证（同副本，跑完即删）——把 compat 删掉、evidence 删掉、造一张撞 `depot` 的卡、`fit.verdict` 填 "凑合"、`research.trialDecks` 清空、清单数字改错、宪法锚点抹掉，得到 7 条 FAIL + exit 1：

```
- controlled-randomness.md 的牌组清单写 "worlds.json 5 个/种"，decks/worlds.json 实际 active 7 张
- decks/proposals/clash.json: "depot" 与正式牌组同名 —— 试用期卡不许覆盖或蹭正式卡…
- decks/proposals/nocompat.json: 试用世界没带 compat —— allowedFor() 会静默放开整副牌组…
- decks/proposals/nocompat.json: 缺 source.evidence（原文摘要或截图路径）…
- recipes/demo-coop-20261105-coop.json 用了试用卡 decks/proposals/coop.json，但 research.trialDecks 没记它…
- recipes/demo-coop-20261105-coop.json 判为 trial 却没有 research.trialDecks…
- recipes/dsh-armory-depot-20261103.json 的 fit.verdict "凑合" 非法，只能是 local / trial / handmade…
```

抽牌器侧的三条边界（2026-11-05 实测）：默认不给 `--allow-trial` 时 80 组种子命中试用卡 0 次；给了 80 组命中 10 次（≈12.5%，与权重 1/13 + 探索 0.3 相符）；`deckFingerprint` 注入前后同为 `2f57e06a064b`，12 组种子的 picks 与 v2.1.1 逐字相同。
