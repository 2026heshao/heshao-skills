# 受控随机 / Controlled Randomness

## 1. 问题

直接让模型“再来一版”，等于把**创意决策**和**渲染**混在一起：每次都在全空间里采样，结果不可解释、不可复现、不可积累。

受控随机不是把 temperature 调低——那只是更保守，不是更可控。它做的是：

> **决策从有限牌组里选，渲染由确定性模板执行；随机只发生在预选过的组合和微扰动里。**

## 2. 三层

| 层 | 内容 | 随机 |
|---|---|---|
| L0 宪法 | 产品事实、品牌、画幅、时长、QA、禁用表达 | 不随机 |
| L1 牌组 | world / hook / transition / caption / sound / rhythm | 只在预审过的卡片里选 |
| L2 种子 | 具体组合、纹理相位、粒子、微偏移 | 用 seed 固定 |

80% 来自系统，20% 是一次有边界的实验。

## 3. 牌组

```
decks/
  worlds.json       6 个视觉世界
  hooks.json        6 种钩子（+ 1 张参考片禁用卡）
  transitions.json  5 种转场（+ 3 张参考片禁用卡）
  captions.json     4 种字幕系统（+ 1 张参考片禁用卡）
  sounds.json       4 种声音材质（+ 1 张参考片禁用卡）
  rhythms.json      5 种叙事骨架
compatibility.json  world × hook/transition/caption/sound/rhythm 的合法组合
weights.json        权重与 explore 比例
recipes/            每个项目一份可复现配方
```

卡片里带 `banned: true` 的是参考片的具体表达（暖光扫、半调擦除、闪白、中下关键词贴纸、riser/whoosh/shimmer、四个地方的钩子）。抽牌器默认永不选它们；它们留在牌组里是为了对照和审计，不是为了使用。

## 4. 抽牌器

```bash
# 第一次：全部随机（但仍在牌组内）
node scripts/pick.mjs --project my-film --seed 20261103-a --no-history

# 基于上一支配方，只换两个轴
node scripts/pick.mjs --project next \
  --base recipes/dsh-armory-depot-20261103.json \
  --vary hook,transition \
  --seed 20261103-b

# 只换世界；不兼容的轴会自动重抽并记录在 forcedAxes
node scripts/pick.mjs --project next --base recipes/dsh-armory-depot-20261103.json --vary world

# 校验一份配方
node scripts/pick.mjs --validate recipes/dsh-armory-depot-20261103.json

# 看牌组与权重
node scripts/pick.mjs --list
```

规则：

- `--base` 时最多改 **2 个轴**；其余锁定。
- 改 world 后，如果旧的 transition/caption/sound 不兼容，会自动重抽，写进 `forcedAxes`。
- 默认排除最近 3 份 recipe 用过的 world 和 hook（`--last 3`；`--no-history` 关闭；`--allow-repeat` 允许重复）。
- 同 seed + 同 decks + 同 weights + 同 history = 同 picks。history 和 decks 变了，结果会变，所以 recipe 里记录 `context`。
- `--explore 0.3` 是 epsilon-greedy：30% 概率在允许集合里均匀抽，70% 按权重抽。想更稳就 0，想探索就 0.5–0.8。

## 5. 配方长什么样

```json
{
  "version": 2,
  "project": "dsh-armory-next",
  "seed": "20261103-b",
  "format": "video-4x3",
  "picks": {
    "world": "depot",
    "hook": "loss",
    "transition": "hard-cut",
    "caption": "lower-left-label",
    "sound": "mechanical",
    "rhythm": "audit"
  },
  "newAxes": ["hook", "transition"],
  "forcedAxes": [],
  "compatibility": true,
  "context": { "base": "recipes/dsh-armory-depot-20261103.json", "vary": ["hook", "transition"] },
  "prompt": { "image": "...", "video": "...", "cover": "...", "negative": "..." },
  "storyboard": [{ "name": "入库口", "budget": 6.0 }],
  "score": { "hook": 0, "thumbnail": 0, "fact": 0, "rhythm": 0, "originality": 0, "audio": 0 }
}
```

`prompt` 是给下游生成用的固定块 + 槽位：ImageGen 只负责构图/光/材质；视频用 `renderAt(t)`；封面用同一份配方派生。

## 6. 项目循环

1. **抽配方**：`pick.mjs`，最多 2 个新轴。
2. **生成 2–3 个候选**：只按配方里的 world/hook/transition 生成，不改宪法。
3. **盲评**：用 `references/scorecard.md` 打分；去掉作者标签。
4. **锁定**：只保留一个 recipe，写入 `score` 和 `notes`；后续视频/封面都从它派生。
5. **上线后回填**：把播放/完播/互动或主观反馈写成 `performance`，调整 `weights.json`。
6. **只引入一个新变量**：下一支片最多改 2 个轴，且至少 1 个轴是上次验证过的。

## 7. 怎么加卡

### 新 world

1. 在 `decks/worlds.json` 加卡：id、concept、palette、type、motifs、motion、bestFor、imageDirection、coverDirection、risk。
2. 在 `compatibility.json` 给它配 hooks/transitions/captions/sounds/rhythms。
3. 在 `weights.json` 的 `worlds` 给一个初始权重（1–2）。
4. `pick.mjs --validate` 一份用它的测试配方；确认没有“暖纸 + 霓虹紫”这类坏组合。
5. 先在一支片子里试，别同时加两张新卡。

### 新 hook / transition / caption / sound

- 先问：它是**新的表达**，还是参考片的换皮？参考片的具体表达标 `banned: true`，只做对照。
- 加到对应 deck 后，要给每个 world 的兼容列表补上它，或在兼容矩阵里明确“不搭”。
- 初始权重 1；验证过再加到 2–3。

## 8. 怎么调权重

> **单次反馈不改权重。** 先按 `references/feedback-loop.md` 落一条经验；只有同一模式在 ≥2 个独立项目重复，或用户明确要求，且给用户看过 before/after 分布后，才动 `weights.json`。至少用 3 个已完成配方回测。

`weights.json` 是唯一的事实来源：

```json
{
  "explore": 0.3,
  "worlds": { "depot": 3, "blueprint": 2, "tower": 2, "archive": 2, "lab": 1, "field": 1 }
}
```

- 成功配方：通过升级闸门后，对应卡片 +0.5～1，封顶 5。
- 失败配方：-0.5，保底 0.2；如果连续两次失败，移到 `risk: high` 并检查兼容性。
- 新卡：1；不要因为“新鲜”就给 5。
- 每季度回看一次：把长期不用的卡降权或重写，不要堆垃圾卡。

## 9. 图片和视频的边界

- **图片**：随机 2 个轴（构图、光位/材质），字体、版式、品牌、安全区不动；最终文字用 HTML/SVG。
- **视频**：固定叙事骨架和幕长；随机 world/transition/sound，不随机幕数；渲染由 `renderAt(t)` 执行。
- **封面**：从同一份 recipe 派生；只换画幅和裁切，不换 world。
- **不要**让 AI 直接生成带中文的最终封面；它只做 reference，文字交给代码。

## 10. 失败模式

- 一次改 4 个轴：无法归因，下一次还是抽卡。
- 把“随机”当创意：随机只是搜索，先验和评分才是创意。
- 牌组里混入参考片的禁用卡：迟早被抽到。
- 不记录 seed/history：同一配方无法复现。
- 权重只加不减：牌组会越来越偏，最后只剩一种风格。
- 只按“好看”评分：事实、缩略图可读性、原创性、音频必须一起过。
- 把一次好评直接写进权重：下一支片就会过拟合；先写 `experiences/`，重复再升级。
