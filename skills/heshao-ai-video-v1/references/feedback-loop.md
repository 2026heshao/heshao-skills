# 交付后反馈与自更新 / Feedback & Self-Update

目标：让 skill 越用越顺手，但不被一次性的偏好带偏。
范围：3+1 回访、规则升级与共享经验账本可用于两条影片路线。产品用真实 recipe；无产品配方的故事使用脚本已有的 `--recipe manual`（省略也默认 manual），不伪造配方。故事镜头/素材/QA 详情留在影片工程，见 [动画流程](ai-animation-workflow.md)；共享账本只存评价与经验摘要。分镜认可或提前指定的分数不能记作已验收成片的成功评价。

核心原则：**单次反馈只写案例，重复出现或用户明确要求才升级为规则；规则改动必须人工确认。** 这是 Warp 的 inner/outer skill、Claude Code 的 `/reflect` 置信度分级、Addy Osmani 的 patterns/gotchas 共同做法。

---

## 1. 三层，不要混

| 层 | 放哪 | 内容 | 谁能改 |
|---|---|---|---|
| L3 案例 | `experiences/YYYY-MM-DD-<project>.md` | 这次发生了什么、用户原话、分数、下一次怎么复用 | 每次交付写一条 |
| L3 教训 | 同文件的“下次怎么复用 / 如果重做” | 一句可执行的教训 | 每次交付写 |
| 规则 | `SKILL.md`、`references/`、`decks/`、`weights.json` | 跨项目通用的做法 | 只有通过升级闸门 + 用户确认 |

不要把一次案例直接写进 `SKILL.md`；也不要把失败案例删掉。经验账本由 `scripts/feedback.mjs` 统一命名、校验、建索引。

---

## 2. 什么时候问

- 只在**成片/封面交付、QA 结果给出之后**问；不要在预览阶段问“好不好”，那时还没定稿。
- 一次交付只问一次，控制在 3+1 个问题；用户忙就允许“不评”。
- 用户没回：本次标 `unrated`，只留元数据；下次开工前不要追问。
- 用户说“这次别记”：尊重，不落盘。

### 推荐问法（可直接复制）

> 成片和验收结果在上面。如果方便，给我三个反馈：
> 1）整体 0–10 分（≥8 很好 / 6–7 可用 / <6 不行）；
> 2）最想保留的一点（钩子 / 节奏 / 视觉 / 文案 / 声音 / 封面 / 工程）；
> 3）最想改的一点（能指到秒数或某一幕最好）。
> 这次经验想怎么沉淀：仅本次 / 可复用 / 可直接改规则。不想评也行，我标记 unrated。

优先用平台的 `AskUserQuestion`；没有就发一条消息。不要拆成七项评分卡追问，也不要问“是不是很好”这种引导题。

---

## 3. 怎么判

| 用户反馈 | verdict | 写什么 | promotion |
|---|---|---|---|
| ≥8，无硬失败，且说“可复用” | `success` | 复用清单：哪条做法下次直接照做 | `candidate` |
| ≥8，只说“很好/没问题” | `success` | 只留元数据 + 一句原话 | `none` |
| 6–7.9，或“能用但某处别扭” | `conditional` | 在什么条件下成立、什么条件下别用 | `none` |
| <6，或出现任一硬失败 | `fail` | 根因 + 已验证修法 + 防复发检查 | `none`（修 bug 除外） |
| 没回 / 不评 | `unrated` | 只留项目、配方、日期 | `none` |

### 用户只给一句话时怎么判

| 用户原话（例） | verdict | 备注 |
|---|---|---|
| 很好 / 可以 / 没问题 / 喜欢 / 就这样 | `success` | 没给分数就 `score: null`；没说“可复用”就 `promotion: none` |
| 还行 / 能用 / 但某处别扭 | `conditional` | 把“但”后面的内容写进 summary 与“下次怎么复用” |
| 不行 / 重做 / 别这样 / 看着不舒服 | `fail` | 允许没有分数；写清具体原因和已验证修法 |
| 只回答了“最满意”或“最想改” | 按已有信息记 | 不补问；没回答的项不要替用户脑补 |
| 不评 / 忙 / 下次再说 | `unrated` | 只留元数据，不追问 |

不要替用户补分数；不要把“还行”写成 success。

### 硬失败（任一命中就不能算成功）

- 事实错误：上屏字段/数字/命令没有出处，或演示数据没角标。
- 原创性：与参考片 3 个以上轴同/近，或直接复用原句/分镜/视觉母题。
- 音频：可听出的底噪/齿音/click，或削顶、音画偏移 >1 帧。
- 工程：没经用户确认就渲染 MP4，或成片/预览不一致。
- 表达：把视觉比喻写成产品功能（产品里没有的东西，用“实现/生成/点亮”承诺）。

> 硬失败优先于分数：`hardFail=true` 只能记 `fail`，9 分也不能记 success。脚本会拒绝矛盾组合：`success` 需 score≥8 或无分数；`conditional` 需 6–7.9；`fail` 需 hard-fail 或 <6；`unrated` 不带分数；`candidate` 必须是 success + generalizable。

> 硬失败里的“已验证修法”可以直接回写 `references/`（这是修 bug）；审美偏好、权重、牌组不因一次失败自动改。

---

## 4. 怎么落盘

```bash
node scripts/feedback.mjs --new \
  --project dsh-armory-atlas \
  --recipe recipes/dsh-armory-atlas-20261104a.json \
  --score 8.5 --tags "视觉,音频" \
  --summary "星图比喻合同 + 单句气口换 take" \
  --quote "这版可以，星图是看法这句说清楚了" --generalizable
```

然后填三节，控制在 20 行内：

- **这次做对了什么**：3 条以内，每条一个动作，不写“整体不错”。
- **下次怎么复用**：写成可执行句，例如“产品里没有的名词，第一次出现必须用‘比作’”。
- **如果重做**：只写这次实际踩到的坑；不要写泛泛的“加强沟通”。

写完：

```bash
node scripts/feedback.mjs --validate
node scripts/feedback.mjs --index
```

规则：

- 一条只记一个教训；一个项目一次交付一条。
- `userQuote` 保留用户原话（短句），不要改写成自己的总结。
- 不写个人信息、原始视频、素材路径、凭据；只留项目、配方、分数、标签。
- `recipe` 要能指回真实文件；没有配方就写 `manual`。

---

## 5. 升级闸门：什么时候允许改规则

`candidate` 不等于规则。必须同时满足：

1. **依据**（写进 `promotionBasis`，校验器按它判，不再只认 success + generalizable）：
   - `repeat` —— 同一教训在 ≥2 个独立项目中出现，且本条 `verdict: success` + `generalizable: true`；
   - `explicit-request` —— 用户原话明确说“以后都这样 / 写进规则 / 这次不用改，我说的是以后”，此时 `conditional` / `fail` 也能合法记 candidate，`userQuote` 必须留下那句原话。
   `promoted` 必须带 `promotionBasis`。2026-11-05 实测：旧校验器只接受 success + generalizable，把"用户明确要求"这条合法路径堵死，只能把 promotion 记成 none，升级线索丢失。
2. **可执行**：能写成一句检查项/参数/分支，不是“注意质量”。
3. **人工确认**：把 diff 给用户看，用户点头后才改 `SKILL.md` / `references/` / `decks/` / `weights.json`。
4. **可回滚**：改完 bump 版本 + 写 `CHANGELOG.md`，在经验文件里把 `promotion` 改为 `promoted`；下一支片若回归，改 `reverted` 并回退规则。

### 置信度（借鉴 `/reflect`）

- `high`：用户给了明确规则或具体修法；可直接进候选。
- `medium`：跨 2 个项目重复出现的模式；先做候选。
- `low`：单次观察/个人偏好；只做案例，不升级。

### 权重/牌组特别规则

- 单次好评**不许**改 `weights.json`、`decks/*.json`、`compatibility.json`。
- 要改权重：至少 3 个已完成项目/配方做回测，给用户看 before/after 分布，再确认。
- 要加卡/禁卡：走 `doctor.mjs`，保持牌组、兼容矩阵、权重、文档计数一致。

---

## 6. 每次交付的收尾顺序

1. 交付成片/封面 + QA 数字 + 文件链接。
2. 发“3+1”反馈问题；不阻塞交付。
3. `feedback.mjs --new` 建条目，填三节。
4. `--validate` + `--index`。
5. 看 `--candidates`：有候选 → 给用户看 diff；没有 → 结束。
6. 用户确认后才改规则；改完 bump 版本 + changelog + `promotion: promoted`。
7. 用户不评 → `unrated`；下次开工不追问。

---

## 7. 反模式

- 问七个维度、写成长问卷 → 用户不填，数据更差。
- 把“没问题/可以”当“高质量”，直接改权重。
- 一次好评就改牌组/权重，下一支立刻跑偏。
- 只记成功，不记失败；失败案例才是防复发的部分。
- 把用户原话改写成自己的总结，丢掉可核对的信息。
- 把案例塞进 `SKILL.md` 主文件，越用越臃肿。
- 自动提交规则改动，不给人看 diff。

---

## 8. 参考

- aiskill.market · Feedback Loop Pattern: Self-Improving Skills — 任务后问“具体要改什么”、按维度阈值评分、能泛化才更新 skill，个案留 case note，多评估器避免过拟合。https://aiskill.market/blog/feedback-loop-pattern-skills
- developersdigest · Self-Improving Skills: Claude Code That Learns From Every Session — `/reflect` 扫描会话中的纠正，按 high/medium/low 置信度提出更新，区分一次性反馈与通用规则。https://www.developersdigest.tech/blog/self-improving-skills-claude-code
- Addy Osmani · Self-Improving Coding Agents — 把 gotchas/patterns 追加到 AGENTS.md，重复出现才升级为规则，条目短而事实化。https://addyosmani.com/blog/self-improving-agents/
- Warp on Claude · How Warp builds self-improving agents — inner/base skill 做任务，outer/improver skill 改它；合并前必须人工批准。https://claude.com/resources/articles/how-warp-builds-self-improving-agents-on-claude
- MindStudio · Self-Improving AI Agent Feedback Loop — 把具体 lessons 写入持久 `learnings.md`，下次运行加载；用多样化 evals 防过拟合。https://www.mindstudio.ai/blog/self-improving-ai-agent-feedback-loop
- MUSE-Autoskill — 按技能积累 per-skill experience，供后续任务检索。https://arxiv.org/html/2605.27366v2
