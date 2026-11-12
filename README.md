# heshao-skills

我自己写的 agent skills（SKILL.md 工作流包）。主体是我自己写的内容；唯一例外是 `heshao-ai-video-v1` 内嵌的 Seedance 2.0 子技能——第三方、MIT、保留原 LICENSE 与出处，单独标注。其余不含从技能商店或社区仓库安装进来的 skill。

目前收录 3 个。判据很实在：内容离了我这台机器或我自己的项目就讲不通——github.com 整段不通只能走 API、WorkBuddy 沙箱大文件传输被出口代理掐断、参考片驱动的宣传片方法论。

## 清单

| Skill | 一句话 | 什么时候用 |
| --- | --- | --- |
| [`heshao-ai-video-v1`](skills/heshao-ai-video-v1/SKILL.md) | 参考片驱动的原创产品宣传片工作流：先看产品画像再决定熵源，拆解参考片的钩子/文案/节奏/镜头/字幕/音效方法，重新设计视觉世界与分镜，产出原创文案、4:3 网页高仿真预览、旁白与自产音效，再逐帧渲染 MP4 并做音画 QA；需要 AI 生成镜头/空镜/转场时走内置的 Seedance 2.0 子技能 | 要做产品宣传片、要分镜节奏表、要可控随机而不是每次抽卡；要 AI 生成实拍级镜头素材 |
| [`github-publish-via-api`](skills/github-publish-via-api/SKILL.md) | github.com 整段不通但 api.github.com 通时，改走 Git Data / Contents API 提交代码、建 Release、传附件，并让本地与远端 SHA 精确对齐 | 需要推送源码或发安装包，但 `git push` 完全走不通；以及排查提交被挂成 web-flow 机器人 |
| [`github-sandbox-download`](skills/github-sandbox-download/SKILL.md) | 在沙箱内字节级精确下载 GitHub 文件/目录/仓库，绕开出口代理对大传输的强制连接重置 | 要取 raw 内容、复制 skill 包，直连下载每次都断 |

## 目录约定

```
skills/<skill-name>/
  SKILL.md        frontmatter 的 name 与目录名一致
  scripts/        配套脚本（可选）
  references/     分册长文（可选）
  decks/ recipes/ evals/   数据与验证材料（可选）
  subskills/      附属技能包（可选，按相对路径按需加载）
packages/<skill-name>/package.json   分发元数据（可选）
```

全部文件 UTF-8。`__pycache__`、`*.pyc` 不入库。

## 安装

```bash
git clone https://github.com/2026heshao/heshao-skills.git
cp -r heshao-skills/skills/heshao-ai-video-v1 ~/.qoder/skills/
```

Qoder 读 `~/.qoder/skills/`，Claude Code 读 `~/.claude/skills/`，Codex 读 `~/.codex/skills/`（这三个都是本机实测存在的路径），把需要的目录拷进去即可；用 SkillLocker 管理的话走它的导入，选到单个 skill 目录。

`heshao-ai-video-v1` 的 `subskills/` 用相对路径引用，安装时要整个目录一起拷，不要只拷 `SKILL.md`。

## 常用命令

```bash
cd skills/heshao-ai-video-v1

# 抽一套配方
node scripts/pick.mjs --project my-film --seed 20261103-a --no-history

# 用户点名视觉世界时（锁定后不兼容的依赖轴会自动重抽）
node scripts/pick.mjs --project my-film --seed x1 --no-history --lock world=atlas

# 牌组注册表体检：加卡/禁卡/动 proposals 后必跑，不一致时退出码 1
node scripts/doctor.mjs

# 校验某份既有配方是否仍与当前牌组兼容
node scripts/pick.mjs --validate recipes/dsh-armory-depot-20261103.json

# 成片音画 QA（参数是 --mp4，不是位置参数）
python scripts/qa_mp4.py --mp4 out/final/film.mp4 --meta out/final/meta.json
```

本机 `ffmpeg`/`ffprobe`/Edge 常常不在 PATH 上，但 `render.mjs`、`qa_mp4.py`、`build_voice.py`
都会自动探测（`PROMO_FFMPEG`/`PROMO_EDGE` → PATH → 剪映自带），`pick.mjs`/`doctor.mjs`/渲染管线只依赖
Node，可独立运行。**开工前先跑 `render.mjs --preflight`。**

旁白 → 时间轴 → 音效 → 成片 的完整链路：

```bash
cd skills/heshao-ai-video-v1

python scripts/build_voice.py --make-spec > narration.json   # 口播稿
python scripts/build_voice.py --spec narration.json --out-dir assets/audio
python scripts/build_timeline.py --make-spec > film.json      # 镜头规格
python scripts/build_timeline.py --spec film.json \
        --voice-timeline assets/audio/voice_timeline_demo.json --out-dir assets
python scripts/build_sfx.py --out-dir assets/sfx              # 13 种材质音效
node scripts/render.mjs --root . --preflight                  # 工具链探测
node scripts/render.mjs --root .                              # 逐帧 + 混音 + 编码
python scripts/qa_mp4.py --mp4 out/final/film.mp4 --meta out/final/meta.json
```

`build_timeline.py` 同时导出 `narration.vtt/.srt`（整句口播，发平台用的外挂字幕）和
`captions.vtt/.srt`（上屏关键词）。字幕时刻按帧边界量化，与渲染端 `ceil(t*fps)/fps` 同一口径。

## 许可

自写部分暂未声明 License，默认保留所有权利，想复用或改编请先开 issue 说一声。内嵌的 `skills/heshao-ai-video-v1/subskills/seedance-20/` 为 MIT 许可（版权归 Iamemily2050，见该目录 `LICENSE`），仅作随包依赖分发，未做改写。

## 关于「为什么不放全部 56 个」

本机装了 56 个 skill，其中大部分是社区与商店产物（remotion 官方、alibaba/open-code-review、skillhub 带 `_meta.json` 的那些、D&AD 文案合集等），它们有原作者和上游仓库，不该由我在这里代发。

## 变更记录

镜像内的技能各自带 `CHANGELOG.md`，以那里为准。仓库结构上一次调整（2026-11-12）把 `heshao-ai-video-v1` 升到 v2.6.0：合并产品画像线、并入 Seedance 2.0 子技能，并更新本 README 的目录约定、安装与许可说明。
