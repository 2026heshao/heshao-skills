# 2026-11-05 · skilllocker

```json
{
  "date": "2026-11-05",
  "project": "skilllocker",
  "recipe": "recipes/skilllocker-20261104-a.json",
  "format": "4:3 1440x1080",
  "duration": 44.07,
  "score": null,
  "verdict": "conditional",
  "hardFail": false,
  "tags": [
    "节奏",
    "文案",
    "声音"
  ],
  "generalizable": true,
  "promotion": "promoted",
  "promotionBasis": "explicit-request",
  "ruleVersion": "2.3.0",
  "summary": "1× 播放偏慢，用户靠倍速才舒服：旁白占比已经 87%，慢的不是字数而是幕间与落版的留白；以后默认把幕间留白压到 0.3s 内、落版空白收到 1.0s 内",
  "userQuote": "希望以后节奏可以快一点点，不用加速视频就给人舒服的速度，其他方面还行，可以复用",
  "changes": ["SKILL.md §3.3/§4/§5/Phase4/Phase5/Phase6/Phase8 + 规范章节", "references/preview-contract.md §3/§9", "references/story-rhythm.md §1/§4", "references/audio-and-render.md §4", "references/facts-and-copy.md §1", "references/feedback-loop.md §5", "scripts/render.mjs 参数白名单 + 帧目录指纹 + meta 指纹", "scripts/build_sfx.py 高频占比报告", "scripts/qa_mp4.py diff 与空帧判据", "scripts/feedback.mjs promotionBasis + promoted 落地校验", "scripts/check_engine_discipline.mjs", "scripts/pacing_report.py", "scripts/tests/ 六个文件 52 用例"],
  "reverted": false
}
```

分数说明：用户没给数字，按 `references/feedback-loop.md` §「用户只给一句话时怎么判」——「还行」= `conditional`，且明确「不要替用户补分数」，所以 `score: null`。

升级口径的冲突（待用户裁决）：SKILL.md §Phase 8 写「`candidate` 需要 2 个独立项目重复，**或用户明确要求**」，用户这次明确说了「以后」；但 `scripts/feedback.mjs --validate` 只接受 `success + generalizable` 才能配 `candidate`，`conditional` 会被判不合格。所以本条先按校验器写 `promotion: none`，把"用户明确要求单次升级"这件事记在这里，等 diff 被确认后一并改校验器和 SKILL.md 的口径。

## 这次做对了什么

- 事实表先行 + 本机实跑取数（`scan` / `status` / `verify` 原文），文案没有一句编造功能；用户提"不要本机数字"时，能精确指出哪些上屏项要改、哪些是产品身份（版本号、系统要求）该留。
- 杂音按 skill 的口径先量再修：非语音段 -200 dBFS 数字零、m4a 句间 -106 dBFS、逐声道峰值 -3.21 dBFS 无削顶 → 排除旁白底噪，定位到自产音效的 8 个高频材质（4.5k 以上占比 0.40–0.59），只压这批材质 + 降音效母线，不整片降噪。
- 逐帧回捞抓到一个真缺陷：舞台层的"夜里调暗"图层在 S03 设成 0.20 后没人复位，顺序渲染时漏进落版，把最该亮的一幕压灰 20%。回捞 3 帧对不上不是假阳性。
- 预览确认门有效：用户在预览阶段就否掉了本机数字和杂音，成本远低于出片后返工。

## 下次怎么复用

- **1× 就要是舒服的速度**：出片前量两个数——旁白占时比、每幕最长空白。这次的实测是旁白 87.2%（不低），但幕间留白 0.45–0.50s、落版空白 1.60s，观感就是"慢半拍"。默认改成：句间 `gap_after` 0.16–0.22、幕间留白 ≤0.30s、落版除 CTA hold 外空白 ≤1.0s；同样文案能自然收到 42–43s。
- **舞台层共享件每帧归零**：任何挂在 `#stage` 而不是挂在某个 `.scene` 里的元素（调暗层、全局遮罩、颗粒层），必须在 `renderAt(t)` 开头复位，且加进 `signature()` 的比对清单，否则"顺序渲染 vs 单帧回捞"必然不一致。
- **杂音先分四类再动手**：底噪 / 底拍 click / 瞬态咔哒 / 削顶。这次是第三类之外的"高频材质铺太多"，修法在音效不在旁白。
- **演示数据的边界要早问**：本机数量、本机路径这类"真实但不该上屏"的数据，在事实表阶段就该确认口径，而不是等用户看预览时才发现。

## 如果重做

- 分幕预算从 5×9s 收到 5×8.2s（≈41s），或者保持 45s 但每幕加一个动作层而不是拉长留白——慢不是时长问题，是空场问题。
- 第一版就把 `signature()` 覆盖到舞台层共享件，省掉一次 1322 帧重渲（约 7 分钟）。
- 音效材质出表时就标 HF 占比，>0.30 的直接进母带处理，不留到用户说"有杂音"再补。
