# 经验模板 / Experience Template

> 用 `node scripts/feedback.mjs --new ...` 生成，不要手写文件名。
> 一条只记一个教训；正文控制在 20 行内；不写个人信息、原始素材、凭据。

```json
{
  "date": "YYYY-MM-DD",
  "project": "project-slug",
  "recipe": "recipes/project-seed.json",
  "format": "4:3 1440x1080",
  "duration": 46.98,
  "score": 8.5,
  "verdict": "success",
  "hardFail": false,
  "tags": ["钩子", "节奏", "视觉", "文案", "声音", "封面", "工程"],
  "generalizable": true,
  "promotion": "candidate",
  "summary": "一句话：这次最值得复用或最该避免的是什么",
  "userQuote": "用户原话（短句，不要改写）",
  "changes": [],
  "reverted": false
}
```

`verdict`：

- `success`：≥8，且无硬失败；写“复用清单”。
- `conditional`：6–7.9；写“在什么条件下可复用”，不升级规则。
- `fail`：<6 或任一硬失败；写“根因 + 已验证修法”。
- `unrated`：用户没评/只说“没问题”；只留元数据。

`promotion`：

- `none`：只做案例。
- `candidate`：可能升级为规则；需要 2 个独立项目重复，或用户明确要求。
- `promoted`：已经用户确认并改入 SKILL/references/decks/weights。
- `reverted`：升级后回退；在 `changes` 写原因。

## 这次做对了什么

- 

## 下次怎么复用

- 

## 如果重做

- 
