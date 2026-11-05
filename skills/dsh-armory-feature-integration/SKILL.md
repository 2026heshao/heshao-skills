---
name: dsh-armory-feature-integration
description: dsh-armory 插件中新增或修改市场/RPC 功能的端到端清单。Use when adding or changing an RPC method, market card or detail data, ExpertMarket props, user-visible Chinese copy, or regression tests in dsh-armory — especially when touching lib/typert.js, lib/client.js, lib/index.js, or when contract-consistency, i18n-coverage, client-i18n, no-conditional-hooks, or run-all checks fail.
---

# dsh-armory 市场/RPC 功能集成

按顺序走完本清单。仓库的护栏是唯一能发现下列问题的机制：编译器、ESLint、`node --check` 都看不见契约漏一处、漏译文、条件 hook、测试没登记。

## 何时使用

- 新增或修改面板可调的 RPC 方法
- 市场卡片 / 条目详情 / 专家市场新增字段、状态或交互
- 新增任何用户可见的中文文案
- 新增回归测试
- 上述护栏报警：恒 404、英文界面蹦中文、React #310、新测试静默不跑

## 开工前

1. 在仓库根读 `package.json` 的 `scripts` 与 `test/run-all.mjs`，确认当前命令与已有套件。
2. 用符号名定位，不要凭记忆改行号（行号会漂移）：

```bash
grep -n "wbRepoMeta" lib/typert.js lib/client.js lib/index.js
grep -n "parseGithubRepo" lib/community-meta.js lib/client.js
```

3. 读对应护栏测试的原文再动结构。断言可能已经演进，以现场为准。

## 1. 契约三处同时改

一个面板可调方法必须同时出现在三处，漏一处就是运行期恒 404（`toolTailor`、`installInfo` 都踩过）：

| 位置 | 写法 | 作用 |
| --- | --- | --- |
| `lib/typert.js` | `mv('method', [params], 'Result')` | strict schema，宿主 loader 注册进 `ctx.typert.local` |
| `lib/client.js` | `{ id: 'dsh-armory#mcpManager/<method>', method: '<method>', result: mcpCodec('...') }` | 面板能调什么；`id` 段是实际端点名 |
| `lib/index.js` | `Remote('<method>')` 装饰器 + `McpManagerGateway` 里的 `async <method>(payload)` | 网关把 descriptor 直接 `Reflect.get` 到类实例 |

方向约束（`test/contract-consistency.mjs` 按运行时解析源码，不硬编码方法名）：

- `client ⊆ typert`：面板能调 ⇒ 类型层必须声明
- `client ⊆ index` 方法集（装饰器方法 ∪ 无装饰器 async 方法）
- `index` 装饰器 ⊆ `typert`
- `typert ⊆ client` **不要求**：允许存在纯类型条目

改完先跑契约护栏，再往下写逻辑：

```bash
node test/contract-consistency.mjs
```

## 2. 客户端 helper 必须内联

`client.js` 是浏览器半，ModuleLoader 只注入宿主模块，**不能相对 import `lib/` 里的兄弟模块**。需要在客户端用的解析 / 格式化逻辑只能内联复制一份。

已存在的重复是合法且有意的，例如仓库写法解析：

- 宿主侧 `lib/community-meta.js` 的 `parseGithubRepo`
- 客户端侧 `lib/client.js` 的 `parseGithubRepoKey`

规则：

- 两处口径必须一致（同输入同输出）；改一处必须同步另一处
- 逻辑有副作用、发网络请求、读写用户目录的，一律留在宿主模块，通过 RPC 暴露
- 不要在客户端直接请求 GitHub 等外部接口绕过宿主的缓存 / ETag / 限流

## 3. i18n：新增中文必须补非恒等英文

- 所有用户可见中文都用 `t('中文原文', [args])` 包裹，字典键 = 中文原文
- 新增键必须在 `client.js` 内联的 `EN_US_MESSAGES` 里补一条英文
- **恒等翻译等于没翻译**：英文值原样抄中文会被判失败（`test/i18n-coverage.mjs` 的恒等判据）
- `i18n-coverage` 做源码 `t()` 键 ↔ 字典键双向差集：
  - 新增漏键立即失败；历史缺口只许通过 `KNOWN_MISSING_KEYS` 收缩，**不要**为省事往基线里加新键
  - 改文案后旧键会变成死键，顺手删除（否则进 `KNOWN_ORPHAN_KEYS`）
- 非 `client.js` 字面量的数据型文案（更新日志、内置 MCP 目录）有各自套件，改它们要跑对应测试

```bash
node test/client-i18n.mjs      # 中文是否都被 t() 包裹
node test/i18n-coverage.mjs    # 是否有译文、是否恒等、locale 四级回落
```

## 4. Hook 形状：条件分支内零 hook

React #310 的唯一定式：`cond ? (() => { … })() : null` / `&&` / `||` 的 IIFE 内部声明 `use[A-Z]`。首帧条件为假时一次都不调，条件转真后同一组件多调 hook，整块面板进错误边界。

规则：

- hook 一律声明在组件顶层、每次渲染都调用
- 局部状态只在数据到手后有意义，也要提前声明，用条件控制的是渲染而不是声明
- `test/no-conditional-hooks.mjs` 锚定的是**字面签名** `const ExpertMarket = ({ call }) => {`。给 `ExpertMarket` 加 prop 会直接让锚点失配
- 需要从外部把数据送进 `ExpertMarket` 时，优先用模块级种子 / 单监听，而不是加 prop：
  - 一次性种子：`seedExpertMarketQuery` / `takeExpertMarketSeedQuery`（`lib/client.js`）
  - 变更通知：`setMarketPulseListener` / `emitMarketPulse`，模块级单监听，组件卸载即摘除
- 确实必须改签名时，把测试里的锚点一起显式更新，并在汇报里说明；不要为了过测而弱化断言

```bash
node test/no-conditional-hooks.mjs
```

## 5. 新测试必须登记到 run-all

`test/run-all.mjs` 是**显式白名单**，不是自动发现。新文件不登记就永远不会跑，而 `npm test` 依然全绿。

- 在 `SUITES` 里加 `{ name: '简短中文说明（守什么）', file: 'xxx.mjs' }`
- 跑完 `npm test` 后确认输出的 `=== 套件名 ===` 里出现了新套件，而不是只看最后的 PASS
- 测试是独立 node 进程，互不污染；必须零真实网络、零真实 `~/.dsh`（`mkdtemp` 隔离 + `fetch` 替身）
- 不用 `node --test`：它会把 `test/` 下有副作用的迁移 / e2e 脚本也当测试执行

## 6. 收尾验证顺序

按此顺序跑，任一步失败先修再继续：

```bash
node test/contract-consistency.mjs
node test/client-i18n.mjs
node test/i18n-coverage.mjs
node test/no-conditional-hooks.mjs
npm test
npm run lint
```

大规模改格式时再跑 `npm run format:check`。

汇报时只写真实结果。没有做浏览器实机验收就明说「未做实机验收」，不要用测试通过代替功能可用。

## 失败归因

| 现象 | 根因 | 修法 |
| --- | --- | --- |
| RPC 恒 404 / `gateway/method-unavailable` | 三处契约少一处 | 看 `contract-consistency` 的差集输出，补对应层 |
| 英文界面突然出现中文或 key 名 | 新文案缺 en-US | 补非恒等译文；不要扩基线 |
| 市场点「详情」整块白屏 / React #310 | hook 写在条件 IIFE 内 | 上提到组件顶层 |
| 一致性测试「定位不到 ExpertMarket」 | 组件签名被改 | 恢复签名改用模块级种子，或显式同步锚点 |
| 新测试写了但从不运行 | `run-all` 未登记 | 加 `SUITES` 条目并确认输出 |
| 详情里某条元数据不显示但正文正常 | 单条上游查询失败被收行 | 属预期降级；检查缓存/限流/stale 回落而非强行显示 |

## 边界

- 不改版本号、不发版、不建 tag；发版有独立流程
- 市场信号必须有真实上游来源，不伪造在线人数、评分、活跃度
- 新增「社区感」功能时，优先把用户送到真实出口（仓库、Issue、源站），不在插件里搭空社区
- 不做站内账号体系与后端；缓存、鉴权、限流留在宿主侧

## 参考文件

- 契约：`lib/typert.js`、`lib/client.js`、`lib/index.js`
- 护栏：`test/contract-consistency.mjs`、`test/client-i18n.mjs`、`test/i18n-coverage.mjs`、`test/no-conditional-hooks.mjs`、`test/run-all.mjs`
- 可参照的完整样例：`lib/community-meta.js` + `wbRepoMeta`（宿主模块 → 三处契约 → 客户端内联解析 → 详情按需查询）
