# AI 动画来源、模型差异与查证方法

检索/核对日期：2026-11-12。此表是知识来源，不是已实测模型清单；本次没有调用视频生成、安装模型或验证本机生成性能。先读 [流程](ai-animation-workflow.md)，再为具体镜头查当前入口。

## 1. 证据分层

- **官方能力**：只适用于文档所写的模型、版本、入口和操作。某公司有该能力不代表它的所有产品入口都有。
- **动画/影视原理**：解释镜头与动作设计，不证明某 AI 能精确执行。
- **整合建议**：本 skill 将上述资料转成预演、记录和验收步骤，需要在项目中检验。
- **本机实测**：只有真实执行、查看并留下结果时才这样标记；不要把论文、示例片、文档或行为评估写成自己的成片验证。

过期或抓取失败时保留不确定性；不把搜索摘要、第三方转述和旧接口名称冒充当前官方接口。

## 2. 动画与制作来源

| 编号 | 来源 | 支持的内容 | 迁移边界 |
|---|---|---|---|
| A1 | [Adobe：12 Principles of Animation](https://www.adobe.com/creativecloud/animation/discover/principles-of-animation.html) | staging、预备动作、关键姿态、时长、弧线、跟随等 | 按风格选择；不是要求机械产品也橡皮变形 |
| A2 | [Adobe：Animatics](https://www.adobe.com/uk/creativecloud/animation/discover/animatics.html) | 带时间与声音的故事板预演，用于检查 timing/flow | 不是最终动画；不以占位图冒充角色动作 |
| A3 | [Blender Studio：Wing It! layout/previs](https://studio.blender.org/blog/wing-it-a-lesson-in-the-mixture-of-layout-and-previs/) | 故事板动态预演与完成动画之间的制作步骤 | 传统制作案例，不是 AI 生成服务教程 |
| A4 | [Toon Boom：Harmony 24 glossary](https://docs.toonboom.com/help/harmony-24/premium/glossary/glossary.html) | 角色设定表/多视角基准 | 多视图有帮助，但不保证模型身份一致 |
| A5 | [StudioBinder：Eyeline Match](https://www.studiobinder.com/blog/what-is-an-eyeline-match/) | 跨镜视线匹配 | 允许有意的空间误导，但须有表达理由 |
| A6 | [StudioBinder：180 Degree Rule](https://www.studiobinder.com/blog/what-is-the-180-degree-rule-film/) | 轴线、屏幕方向与空间连续性 | 不是永不可越轴的法律 |
| A7 | [StudioBinder：Match on Action](https://www.studiobinder.com/blog/what-is-a-match-on-action-cut/) | 同一运动在切点两侧延续 | 转成验收问题，不假装原文含 AI 实测 |
| A8 | [Epic：Fix Foot Sliding](https://dev.epicgames.com/documentation/unreal-engine/fix-foot-sliding-with-ik-retargeter-in-unreal-engine) | 在骨骼重定向中固定应静止的脚部目标 | 只借接触滑移检查思路，不能直接用于修复 AI 视频像素 |

## 3. 生成平台：不能混用的能力

| 编号 / 已核对来源 | 可采用的方法 | 不可外推 |
|---|---|---|
| P1 [Runway Gen-4 Video Prompting](https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide) | 输入图承担外观/构图，文字重点描述主体、环境与镜头运动；逐次增加一个要素；用正向描述 | 该指南不支持 negative phrasing；不能给所有模型统一追加负向词 |
| P2 [Runway Gen-4 Image References](https://help.runwayml.com/hc/en-us/articles/40042718905875-Creating-with-Gen-4-Image-References) | 在图片阶段统一人物与环境，再把批准的图作为视频输入 | 这是图像参考工作流，其参考图上限不是视频接口上限 |
| P3 [Firefly：使用图像生成视频](https://helpx.adobe.com/cn/firefly/web/work-with-audio-and-video/work-with-video/generate-videos-using-images.html) | 用首帧/尾帧约束起止布局，提示词说明过渡 | 本文流程加入首帧会关闭部分镜头/风格/构图选项，加入尾帧后运动选项也关闭；不能承诺所有控制同时叠加 |
| P4 [Firefly：Match camera motion](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-video/match-camera-motion-to-reference-video.html) | 从参考视频借相机运动；记录 seed 以便比较相似结果 | 运镜参考不等于动作参考、身份参考；seed 不是身份锁 |
| P5 [Google DeepMind：Veo](https://deepmind.google/models/veo/) | 区分人物参考、首尾帧过渡与原生延长 | 能力页不保证 Gemini/Flow/Vertex 或其它入口的字段、权限、价格与上限相同 |
| P6 [阿里云：万相首尾帧 legacy API](https://help.aliyun.com/zh/model-studio/legacy-image-to-video-by-first-and-last-frame-api-reference) | 首尾帧加过渡描述；有独立 `negative_prompt`；记录改写开关和可取得的实际提示 | 是早期接口案例，不是全系列最新接口；明确即使相同 seed 也不能保证完全一致 |

本次不固化价格、可用地区、最大分辨率、参考数量和片长；实际执行前到对应入口重新核实。以旧文档作方法示例可以，以旧数值冒充当前通用能力不可以。

P6 中 `prompt_extend` 默认开启；开启后成功任务可提供 `actual_prompt`，应连同原始提示记录。其他平台不一定返回改写后的提示，取不到就标明不可见，不编造。

P1、P2 的正文由研究代理从官方帮助中心读取；P3–P5 由研究代理读取官方正文。主助手重抓 P1/P3 文章页面收到 403，并未将该次请求记为读取成功。P6 与 A1/A2/A3/A7/A8 由主助手另行读取核对；A4–A6 由研究代理核对。上述资料均未转化为本机生成实测。

## 4. 具体项目的查证卡

外部服务执行前检查实际接口/界面和可用工具，最少记录：

| 字段 | 要记录什么 |
|---|---|
| 身份 | provider、surface/入口、model/版本、operation/模式 |
| 来源 | 官方 URL、读取日期、关键能力及证据；未核实项 |
| 输入 | 参考素材角色、字段/标签、格式限制、控制互斥、是否自动改写 |
| 输出 | 图像/视频/音频、时长/比例、任务查询与输出链接有效期 |
| 成本与权限 | 当前价格或未知、授权的次数与金额、素材上传范围 |
| 复现记录 | 原始提示、能取得的实际提示、输入资产哈希、seed、设置、任务 id、返回文件与接受状态 |

不要求用户在聊天里贴密钥。没有可用生成入口时可交付分镜、提示词和素材规格，不宣称已经提交任务。只有操作身份与真实响应结构核对后才写对接代码；不能根据某厂商另一个操作猜字段。

原生延长可能携带已有视频的运动和音频上下文；仅用末帧续接只继承静态布局，不保证动作相位或声音连续。首尾帧是端点约束，不是中间逐帧轨迹锁。身份参考、动作参考、风格参考和相机参考应分别命名，不能混作一项。

配方抽签的 seed 与模型采样的 seed 分开记录。既有 recipe 的确定性条件并不能证明模型输出可逐字节复现。

## 5. 网页合成的技术来源

T1：[MDN — requestVideoFrameCallback](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback)。回调针对提交给合成器的视频帧，提供 `mediaTime` 等元数据；与显示刷新驱动的 rAF 不同，也有 best-effort 时序限制。

本 skill 的整合判断：两次 rAF 和 DOM 签名不能保证 MP4 已解码到目标帧。应单独验证异步就绪、时间映射、失败与像素结果；接口名出现不代表工程已实现。现有脚本边界见 [流程 §5](ai-animation-workflow.md#5-现有脚本的能力边界)。

## 6. 未采用的主张

- 不写“同 seed 永不变脸”“首尾帧保证丝滑”“一次生成整片稳定可用”。
- 不写“所有二维动画禁用摄影词汇”或“所有动画必须用 24fps”；经验取决于风格、模型和交付。
- 不把产品口播占比≥80%、每幕空白限制和 CTA 套给无声故事。
- 不从一条成功样片推导成功率、节省比例或付费推荐；需要记录真实样本和成本。
- 检索到 Hugging Face Diffusers 视频指南，但本轮正文两次抓取失败，因此不据此新增安装命令、显存门槛或“本机能跑”的保证。需要本地开源生成时另做硬件、模型授权、实际依赖和小样验证。
