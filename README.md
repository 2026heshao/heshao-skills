# heshao-skills

我自己写的 agent skills（SKILL.md 工作流包）。这里只放本机的东西是我自己写的，不含从技能商店或社区仓库安装进来的 skill。

目前收录 3 个。判据很实在：内容离了我这台机器或我自己的项目就讲不通——github.com 整段不通只能走 API、WorkBuddy 沙箱大文件传输被出口代理掐断、参考片驱动的宣传片方法论。

## 清单

| Skill | 一句话 | 什么时候用 |
| --- | --- | --- |
| [`heshao-ai-video-v1`](skills/heshao-ai-video-v1/SKILL.md) | 参考片驱动的原创产品宣传片工作流：拆解参考片的钩子/文案/节奏/镜头/字幕/音效方法，重新设计视觉世界与分镜，产出原创文案、4:3 网页高仿真预览、旁白与自产音效，再逐帧渲染 MP4 并做音画 QA | 要做产品宣传片、要分镜节奏表、要可控随机而不是每次抽卡 |
| [`github-publish-via-api`](skills/github-publish-via-api/SKILL.md) | github.com 整段不通但 api.github.com 通时，改走 Git Data / Contents API 提交代码、建 Release、传附件，并让本地与远端 SHA 精确对齐 | 需要推送源码或发安装包，但 `git push` 完全走不通；以及排查提交被挂成 web-flow 机器人 |
| [`github-sandbox-download`](skills/github-sandbox-download/SKILL.md) | 在沙箱内字节级精确下载 GitHub 文件/目录/仓库，绕开出口代理对大传输的强制连接重置 | 要取 raw 内容、复制 skill 包，直连下载每次都断 |

## 目录约定

```
skills/<skill-name>/
  SKILL.md        frontmatter 的 name 与目录名一致
  scripts/        配套脚本（可选）
  references/     分册长文（可选）
  decks/ recipes/ evals/   数据与验证材料（可选）
```

全部文件 UTF-8。`__pycache__`、`*.pyc` 不入库。

## 安装

```bash
git clone https://github.com/2026heshao/heshao-skills.git
cp -r heshao-skills/skills/heshao-ai-video-v1 ~/.qoder/skills/
```

Qoder 读 `~/.qoder/skills/`，Claude Code 读 `~/.claude/skills/`，Codex 读 `~/.codex/skills/`（这三个都是本机实测存在的路径），把需要的目录拷进去即可；用 SkillLocker 管理的话走它的导入，选到单个 skill 目录。

## 许可

暂未声明 License。仓库内容默认保留所有权利，想复用或改编请先开 issue 说一声。

## 关于「为什么不放全部 56 个」

本机装了 56 个 skill，其中大部分是社区与商店产物（remotion 官方、alibaba/open-code-review、skillhub 带 `_meta.json` 的那些、D&AD 文案合集等），它们有原作者和上游仓库，不该由我在这里代发。
