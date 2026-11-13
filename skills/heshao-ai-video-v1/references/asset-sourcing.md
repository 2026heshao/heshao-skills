# 素材来源、授权台账与进工程形态

适用：任何**非代码绘制**的画面/声音素材进入影片工程时——图库图、实拍、录屏、3D 资产、字体、AI 生成物。
授权条款核对：**2026-11-13**，只核对许可页正文；价格、上传上限、可用地区等易变项不固化，执行前回站复核。

本文件管「素材从哪来、能不能用、怎么进工程、怎么留痕」。不管：分镜怎么排（→ `story-rhythm.md`）、画面怎么画（→ `preview-contract.md`）、AI 提示词怎么写（→ `subskills/seedance-20/`）。

## 1. 一句话立场

**素材来源可以外包，溯源责任不能外包。**
没有 `license` 与 `source.url` 的素材，和没有出处的数字一样，不许上屏。

## 2. 六类来源与授权实况

| # | 来源 | 典型渠道 | 商用 | 署名 | 硬限制 / 坑 |
|---|---|---|---|---|---|
| S1 | **代码绘制** | 本 skill 的 `engine.js` + `renderAt(t)` | 自有 | 无需 | 唯一已实测帧精确路径；复杂角色/材质成本高 |
| S2 | **自制** | 自己截产品图、自己录屏、自己拍摄 | 自有 | 无需 | 出镜者需本人同意；屏幕内容不得含他人版权素材 |
| S3 | **免费商用图库** | Pexels / Unsplash / Pixabay / StockSnap / Burst / Kaboompics | ✅ 可 | 不强制 | 见 §2.1；**人物可识别仍需肖像授权** |
| S4 | **公有领域 / CC 混合库** | Wikimedia Commons、Flickr CC 区、机构数字馆藏 | ⚠️ 逐文件核 | 多数要求 | **同一库里许可混杂**，必须开单个文件页确认，不能用搜索结果页的筛选项代替 |
| S5 | **AI 生成** | Seedance 2.0 子技能、ImageGen 等 | ⚠️ 看 provider 条款 | 多数不要求 | 付费前确认 provider/额度；生成物也可能是"撞同款"来源 |
| S6 | **付费图库 / 影视帧** | 商用图库订阅、影片截图 | ⚠️ 看订阅条款 | 多数要求 | **影视截图不因"注明出处"而获授权**；不要拿参考片抽帧当素材 |

### 2.1 三个站的具体红线（2026-11-13 核对）

| 站 | 许可 | 允许 | 明确禁止 | 容易漏的 |
|---|---|---|---|---|
| **Pexels** | Pexels License | 免费商用、可修改、署名为"赞赏非强制" | 卖未修改的原始副本作海报/实物；暗示图中人物或品牌为产品背书；在其它图库/壁纸平台转售；用作商标/商号 | 人物可识别时，商用场景的 model release 由**你**负责，站方不提供 |
| **Unsplash** | Unsplash License | 免费商用、无需许可、不可撤销 | 卖未经显著修改的图；用 Unsplash 图汇编成同类/竞争性服务 | ①许可**不覆盖**图里的商标、可识别人脸、他人艺术作品；②**走 Unsplash API 集成时署名是强制**（不同于网页下载）；③Unsplash+ 付费层另有条款（含赔偿额度，同时禁止用于 AI 训练） |
| **Pixabay** | Pixabay Content License | 免费商用、可修改、无需署名 | 卖未修改副本；敏感/背书性使用 | ①**带 "Sponsored Images" 的是 Shutterstock 供稿，不在免费许可内**，详情页才看得出来；②2019 年前下载的旧图仍适用 CC0，规则不同 |

**通用判断**：三站的许可都只解决"这张图本身"，不解决"图里的人、图里的商标、图里的第三方作品"。后三者各自需要独立授权。

### 2.2 自动获取的合法边界（与当前可用性）

"能不能让 AI 自己上网搜素材下下来"——**能搜、能下，但不能写爬虫**。区别在这：

| 做法 | 可行 | 依据 |
|---|---|---|
| 会话里联网搜候选 → 人确认 → 按明确 URL 或本地文件登记 | ✅ | 单条、来源明确、有留痕，不构成系统性采集 |
| 图库官方 API 检索 + 下载 | ⚠️ 看 key | 遵守 rate limit 与署名要求即可（见下表） |
| 脚本爬图库网页批量抓图 | ❌ | Pexels ToS 明确禁止 bulk / large-scale / systematic copying 与自动化采集；违者封 key |
| Unsplash API 下载后转存进视频 | ❌ | API 强制**热链接** `photo.urls`、不得 re-host、每次下载回调 download 端点。视频渲染必须落地成文件，正撞条款。Unsplash 只能人工网页下载（走 Unsplash License，合法） |

**API 现状（2026-11-13 实测，不是文档抄的）**：

| 通道 | 状态 | 说明 |
|---|---|---|
| **本地文件 / 直链**（`--file` / `--url`） | ✅ **零依赖，推荐默认** | 浏览器里下好，脚本复制进工程并登记 |
| Pexels API | ❌ **新 key 签发已暂停** | 官方页面提示"新API密钥的签发目前已暂停，无法申请"。`--pexels-*` 代码保留，key 恢复后可直接用 |
| Openverse API | ⚠️ **当前 504**（Frankfurt / Singapore 节点均超时） | 无 key（匿名约 100 次/天），字段带 `license`/`creator`/`foreign_landing_url`，服务恢复后值得复核。**未实测其真实响应，勿据本文写死字段** |
| Pixabay API | ⚠️ 需 key，注册常卡 | 官方文档：100 次/60 秒、要求展示来源、**禁止永久热链接**（须下载到自有服务器，与我们的用法一致）、须缓存 24h、禁批量下载。**注册页报「请不要使用自动工具填写此表格」时，实际原因是 Google reCAPTCHA 加载失败，不是真检测到自动化**（社区排查结论，非官方说明）——换浏览器无效，因为换哪个浏览器都连不上该域名 |

### 2.3 不需要账号、不需要 key 的取图站

注册卡住就别耗在注册上。下面这些站**网页直接下载大图、无需登录**，一样能满足 1440×1080：

| 站 | 许可 | 备注 |
|---|---|---|
| Pexels | Pexels License | 免登录直下；大图 `images.pexels.com` 直链可拿 |
| Unsplash | Unsplash License | 免登录直下（**不要**用它的 API 转存，见 §2.2） |
| StockSnap.io | CC0 | 免登录，公有领域贡献，最干净 |
| Burst (Shopify) | Burst License | 免登录，电商/商品图偏多 |
| Kaboompics | 自有许可 | 免登录，生活方式/室内 |
| Wikimedia Commons | 逐文件（CC0 / CC BY / PD） | 免登录，但**必须逐文件核许可**，同一页混杂 |

Pixabay 的独特优势只是"图+矢量+视频+音乐都在一个库里"，不是唯一来源。为它一个注册流程卡住整条流程不值得。

所以本 skill 的默认分工：**找素材由人（或 agent 联网搜）+ 浏览器下载，落地由脚本登记并过闸门**。脚本里没有"爬站搜索"，那不应当归因于保守，而应归因于这条路径不合规，且会把全网同款塞进片子。

```bash
# ① 浏览器下载后登记（零网络依赖，Pexels 停 key 时唯一稳的路）
python scripts/fetch_asset.py --file ~/Downloads/hall.jpg --out assets/img/hall.jpg \
    --id hall --role space --license pexels-license --source-type stock \
    --source-url https://www.pexels.com/photo/xxx

# ② 有直链时直接下
python scripts/fetch_asset.py --url <图片直链> --out assets/img/hall.jpg --id hall --role space \
    --license pexels-license --source-url https://www.pexels.com/photo/xxx \
    --attribution "Photo by X on Pexels"

# ③ 只看会写什么
python scripts/fetch_asset.py ... --dry-run

# ④ Pexels key 恢复后才可用
export PEXELS_API_KEY=xxxx
python scripts/fetch_asset.py --pexels-search "warehouse night" --list-only
python scripts/fetch_asset.py --pexels-id 12345678 --out assets/img/hall.jpg --id hall --role space
```

脚本做四道拦截：非 http/https 的 `--url` 拒收、超过 200MB 拒收、**按 magic bytes 判容器**（防盗链页常带 `image/jpeg` 头，只信头会把 HTML 存成 jpg）、同内容重复登记拒绝（跨镜复用）。`--file` 是**复制**不是移动，原件留着。下载完自动算 `sha256`、写 manifest、立刻跑 `check_assets`；台账不合规返回 1 但不删已下载文件——文件不丢，补字段再跑。

**`--file` 最容易丢溯源**：本地文件没有 URL，非自制素材必须手工填 `--source-url`，否则台账报 E012。没有来源页的素材，等于事后无法证明授权，不许上屏。

## 3. 选路决策树

按顺序问，命中即停：

```
① 画面要出现精确文字 / 界面 / 数字 / 命令？
   └ 是 → S1 代码绘制。AI 必错字，图库不可能有你的产品界面对。
② 要证明真实产品外观 / 真实操作过程？
   └ 是 → S2 自制截图或录屏。事实表可核，不担心"这不是我们的界面"。
③ 要真实世界的环境、质感、人、物（非产品）？
   └ 是 → S3 免费商用图库（优先）；找不到再 S4 公有领域。
④ 要一个现实中不存在 / 拍不到的空间或氛围？
   └ 是 → S5 AI 静帧。只做"空间"，不做文字与产品 UI。
⑤ 要连续动作 / 角色表演 / 实拍级镜头运动？
   └ 是 → S5 AI 视频 → **必须抽帧成图片序列**（见 §5），不要直接嵌 MP4。
⑥ 只是声效 / 底拍？
   └ 是 → `build_sfx.py` 自产（numpy）。不要复用参考片音效名单。
```

两条硬顺序：

- **S3/S4 之前先想 S1/S2。** 能截自己的产品、能录自己的操作，就不要用图库——图库图无法证明任何产品事实，只能当氛围。
- **S5 之前先看 Phase 0.5。** 产品片要先确认牌组贴不贴；故事片要先有视觉基准。不要"抽不出卡就上网生一张"。

## 4. 素材规格硬要求

输出是 1440×1080 / 4:3，素材买进来就要按这个尺子验，别等渲染了才发现糊。

| 项 | 要求 | 为什么 |
|---|---|---|
| 最短边 | **≥ 1080px**，首屏/主视觉建议 ≥ 1600px | 低于 1080 放大后必然软；4:3 裁切还要再吃掉边 |
| 宽高比 | **允许裁到 4:3 后构图仍成立** | 图库多是 3:2 / 16:9，裁切会切掉主体；下载前先想裁切线 |
| 安全区 | 主体不要贴边；左右各留 ≈12% 可裁余量 | 4:3 裁 16:9 会横切约 25% 宽 |
| 肤色/白平衡 | 同一套素材色温一致 | 混用不同摄影师的图，拼起来像素材站大杂烩 |
| 视频素材 | 帧率 ≥ 工程 fps（30）；优先短 GOP | 长 GOP 会撞 §5 的 seek 上限 |
| 序列帧 | `f_0001.png` 起，等宽补零，序号连续无断号 | 断号会被 `Math.floor(t*fps)` 索引到错帧且不报错 |
| 字体 | 只装 OFL / Apache 等可商用许可，并保存 `OFL.txt` 之类许可文件 | 商用字体授权不属于"能下载"的范畴 |

## 5. 三种进工程形态与确定性

| 形态 | 帧精确 | 实测依据 | 用法 |
|---|---|---|---|
| **图片序列 PNG** | ✅ | 已实测（无声最小工程 60/60 帧，MAD 0.97–1.37） | **首选**。唯一可复现的素材路径，用 `frames_from_video.py` 从视频抽 |
| **单张静图 + 代码动效** | ✅ | 已实测（vault 5 张 AI 场景板 + DOM 文字） | **次选**。占比最高的实际做法 |
| **MP4 嵌 `<video>`** | ⚠️ 0–1 帧；GOP 180 未等待时 **−52 帧（≈1.73s）** | 已实测（2026-11-12，v2.7.2） | 只在确认门后试用，截图前必须轮询 `seeking` 结束 |
| 内联 base64 | ❓ 未实测 | — | 仅小图标；大图会让 HTML 膨胀、预览变慢，不推荐 |

### 5.1 视频转序列（替代嵌 MP4 的唯一确定路径）

```bash
# 标准：30fps、cover 裁切填满 1440×1080
python scripts/frames_from_video.py --input clip.mp4 --out assets/seq/clip-a

# 只取 2.4–6.0s；加边不裁切；吐出 manifest 片段
python scripts/frames_from_video.py --input clip.mp4 --out assets/seq/clip-b --start 2.4 --end 6.0
python scripts/frames_from_video.py --input clip.mp4 --out assets/seq/clip-c --fit contain
python scripts/frames_from_video.py --input clip.mp4 --out assets/seq/clip-c --emit-manifest --root .

# 先看命令不执行
python scripts/frames_from_video.py --input clip.mp4 --out assets/seq/clip-a --dry-run
```

脚本做四件事：按工程 fps 规整（`fps=30`）、画幅处理（`cover` 裁切 / `contain` 加边 / `none` 原样）、**序号连续性校验**、**实际帧数 vs 期望帧数对账**。它不用 ffprobe（精简构建常没带），元信息从 `ffmpeg -i` 的 stderr 解析。

已实测（2026-11-13，本机剪映 ffmpeg）：2.00s / 24fps / 320×240 源 → 30fps 序列 60 帧、序号 `0001–0060` 连续、时长对账一致。

两条必须知道的边界：

- **断号不是小事**：`f_0001…f_0060` 中间缺 40，`Math.floor` 索引不报错，只是画面在 t 处卡一下。脚本会把断号判 FAIL 并退出 1。
- **实测帧数以实际为准**：源帧率低于工程帧率会补重复帧，尾帧不足半帧会被丢，差 1–2 帧属正常。写时序用脚本报的 `count`，不要用 `duration × fps` 自己算。

只在脚本不可用时才手敲：

```bash
ffmpeg -i clip.mp4 -vf "fps=30,scale=1440:1080:force_original_aspect_ratio=increase,crop=1440:1080" \
       -start_number 1 -q:v 2 assets/seq/clip-a/f_%04d.png
```

```js
// engine.js：序列随时间取帧，末帧夹取，不越界
const frame = Math.min(seq.count - 1, Math.floor(t * PROMO.fps));
```

两个必须做：

- **图片必须 `await img.decode()`**。`window.__ready` 只代表脚本声明就绪，不代表素材可用；实测延迟 1.5s 到达的素材丢了前 17 帧（MAD 74.4）。
- **序列帧数 × 素材段时长要与时间轴对账**。少一帧不报错，只是最后一帧被重复夹取。

## 6. manifest 契约：`assets/asset-manifest.json`

放在**影片工程**内（技能包不存素材，也不存 manifest）。一份工程一个文件。

固定路径 `<project>/assets/asset-manifest.json`；`path` 一律**相对工程根** `<project>` 解析（脚本按目录名自动上溯一层，非标准布局用 `--root` 指定）。

```json
{
  "schemaVersion": 1,
  "projectId": "promo-vault",
  "commercial": true,
  "assets": [
    {
      "id": "hall-desk",
      "path": "assets/img/hall-desk.jpg",
      "kind": "image",
      "role": "space",
      "source": {
        "type": "ai",
        "url": "internal:imagegen",
        "provider": "ImageGen",
        "retrievedAt": "2026-11-10"
      },
      "license": {
        "id": "provider-terms",
        "commercialUse": true,
        "attributionRequired": false
      },
      "sha256": "…",
      "derivedFrom": null,
      "usedIn": ["hall"],
      "notes": "只做空间，无文字；文字全部 DOM 叠加"
    }
  ]
}
```

### 字段表

| 字段 | 必填 | 取值 / 说明 |
|---|---|---|
| `id` | ✅ | 全局唯一，`derivedFrom` 靠它解析 |
| `path` | ✅ | 相对 manifest 所在工程根；序列填目录或首帧 |
| `kind` | ✅ | `image` / `sequence` / `video` / `audio` / `font` / `model3d` |
| `role` | ✅ | `space` / `identity` / `prop` / `environment` / `texture` / `voice` / `sfx` / `bgm` / `typeface` |
| `source.type` | ✅ | `self` / `stock` / `public-domain` / `ai` / `screen-record` / `owned` |
| `source.url` | 非自制必填 | 原始页面或 `internal:<工具>`；填不出来的素材不许上屏 |
| `source.retrievedAt` | ✅ | `YYYY-MM-DD`，条款会变，日期就是证据 |
| `license.id` | ✅ | 见 §7 白名单 |
| `license.commercialUse` | ✅ | 布尔。工程 `commercial: true` 时必须为 `true` |
| `license.attributionRequired` | ✅ | 为 `true` 时 `attributionText` 必填 |
| `sha256` | ✅ | 内容指纹；同时是"同一素材重复使用"的判据 |
| `derivedFrom` | 派生件必填 | 指向另一个 `id`（原片/原图），必须能解析 |
| `usedIn` | 建议 | 用在哪几幕；一条素材只在**一镜**成立，多镜复用见 §8 |
| `frameCount` | sequence 必填 | 目录里实际 PNG 数；与磁盘不符即 FAIL（重抽后最容易过期的字段） |

### 校验

```bash
python scripts/check_assets.py --manifest <项目>/assets/asset-manifest.json
python scripts/check_assets.py --manifest <项目>/assets/asset-manifest.json --commercial   # 商用工程
python scripts/check_assets.py --manifest <项目>/assets/asset-manifest.json --stamp        # 回填缺失 sha256
```

退出码：0 通过（可带 WARN）；1 有 FAIL；2 参数/文件错误。

## 7. 许可白名单

| `license.id` | 含义 | 商用 | 备注 |
|---|---|---|---|
| `own` / `self` | 自己拍摄、录制、绘制 | ✅ | 出镜者同意自行留档 |
| `pexels-license` | Pexels License | ✅ | 见 §2.1 |
| `unsplash-license` | Unsplash License | ✅ | API 集成时署名转强制 |
| `pixabay-content-license` | Pixabay Content License | ✅ | 排除 Sponsored Images |
| `cc0-1.0` | 公有领域贡献 | ✅ | 最干净 |
| `cc-by-4.0` | 署名 | ✅ | `attributionText` 必填 |
| `cc-by-sa-4.0` | 署名 + 相同方式共享 | ⚠️ | 衍生作品需同许可，商用片慎用 |
| `ofl-1.1` / `apache-2.0` | 开源字体 | ✅ | 保留许可文件 |
| `provider-terms` | AI 生成物按 provider 条款 | ⚠️ | 记录 provider 与生成日期 |

**不在白名单的许可一律 FAIL**，要放行必须显式 `--allow-license <id>` 并在 `notes` 写理由。这不是形式主义：`cc-by-nc`（禁商用）、`editorial-only`（仅编辑用途）混进商用片是真实的赔付风险。

## 8. 与原创性 9 轴的分层口径

**素材来源不计入原创性分数，原创性只判组织方式。**

| 层 | 判什么 | 闸门 |
|---|---|---|
| 组织层 | 钩子、叙事顺序、镜头语法、幕长、转场、字幕系统、视觉母题、声音排列、CTA | 原 `originality-gates.md` 九轴，一字不改 |
| 素材层 | 素材从哪来、能不能用、用了几次 | 本节三条 |

素材层三条独立闸门（任一不成立即不许出片）：

1. **单镜原则**：同一 `sha256` 只在一个镜头里成立。跨镜复用同一张图 = 观众看得出"这是一张底图来回推"，直接判视觉贫乏。多镜复用需在 `usedIn` 里写明并说明为什么非它不可。
2. **非参考片原则**：不得使用参考片的任何原帧、原音、原字体。抽参考片的帧当素材，等于把"借方法不借表达"整条作废。
3. **留痕原则**：`source` + `license` 齐全，`check_assets.py` 跑过。

反过来也成立：**用了图库素材不能成为降低原创性的借口**。"这张图是 Pexels 的"不构成九个轴雷同的豁免——雷同判的是你把素材怎么排，不是素材本身谁拍的。

## 9. 授权红线（无条件禁止）

- 影视截图、他人作品截图、社交媒体图，**不因注明出处而获得授权**。
- 真实人物肖像 / 声音 / 姓名用于商业宣传，必须有本人或代理人授权；图库许可不替代。
- 品牌 logo、商标、可识别产品外观，未经授权不得作为画面主体或暗示背书。
- 用 AI 生成"某明星的脸""某电影的角色"——即使模型能出，也不能商用。
- 拿 `cc-by-nc`、`editorial-only`、`rights-managed` 素材做商用片。
- 把素材库的图汇编成"自己的素材站"或对外分发原始文件。

拿不准的，记 `license.commercialUse: false` 并当场问用户，不要自己判"应该没事"。

## 10. 常见坑

1. **只看了搜索结果页的筛选器**：CC 混合库里，搜索结果允许商用 != 这个文件允许商用。必须开文件页。
2. **下载了 Sponsored / Plus / Editorial 混排的图**：Pixabay Sponsored 是 Shutterstock 供稿，Unsplash+ 是付费层，都不在免费许可内。
3. **漏掉图里的人和商标**：许可只覆盖图本身。人物可识别的商用场景，model release 是你的责任。
4. **分辨率不够**：4:3 裁切 + 放大到 1440 宽，最短边 < 1080 必糊。下载前先估裁切后剩余像素。
5. **直接嵌 MP4 图省事**：GOP 长的素材会掉到 −52 帧，且脚本只告警不拦。要确定性就抽帧。
6. **忘了 `await img.decode()`**：`__ready` 绿了也可能截到空帧，实测丢过前 17 帧。
7. **序列断号**：`f_0001` 到 `f_0100` 中间缺 40 帧，`Math.floor` 索引不报错，只是画面卡一下。
8. **素材当视觉母题的替代品**：九轴要求"一个片子一套世界"，图库图拼出来的世界是别人的世界。
9. **manifest 最后补**：素材一进来就登记。事后补等于凭记忆填许可，等于没填。
10. **把 AI 场景板当产品截图**：AI 图里没有你的真实界面。产品 UI 只能 S1/S2。
