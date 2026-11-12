# 音频与渲染 / Audio & Render

本页主要描述产品口播工具链，不要求所有动画都有旁白。对白/无旁白/完全无声故事按 [动画流程 §5](ai-animation-workflow.md#5-现有脚本的能力边界) 选路：当前完整渲染要求实际基础音轨，纯零峰值探测也有边界；不能为了套本页而添加假台词或底噪。完全无声走 §5 的 frames-only + 无音轨编码（已实测，见该节）；视频素材逐帧解码接入仍未支持。

## 1. 旁白 TTS

- 推荐 `edge-tts`（`zh-CN-XiaoyiNeural` / `XiaoxiaoNeural` / `YunxiNeural`）。
- 逐句生成，每句单独 rate / pitch / gap；不要整段一次读，后面无法对齐动作。
- 先缓存原始 `line_000.mp3`；改润音链时用 `--from-cache` 重润，时间轴不漂移。
- 全片时间轴由旁白起止推导：`scenes[].start/end`、`captions`、`sfx` 都从它生成。

### 口播归一化

| 原文 | 送 TTS |
|---|---|
| MCP | M C P |
| DSH | D S H |
| sha256 | sha 二五六 |
| PDF | P D F（或按语境） |
| v2.4.7 | v 二点四点七 |

## 2. 润音链（可复现起点）

```
highpass 80 Hz
EQ 250 Hz -1.0 dB
EQ 3.2 kHz +1.2 dB
EQ 5.2 kHz -1.5 dB      # 压齿音；本片新增
compress 1.9:1（threshold -16 dB, attack 8ms, release 180ms, makeup 1.2dB）
lowpass 6.8 kHz (8th)   # 比参考片 7.2k 再收一点
fade 12ms / 40ms
true-peak limit -3 dBTP
```

先按每句 RMS 对齐到约 -17 dBFS，再走链；不要每句顶到同一峰值。

## 3. 噪音诊断（不要猜）

用户说“有噪音”时，先分四类：

| 现象 | 量什么 | 常见原因 |
|---|---|---|
| 持续沙沙 | 静音段 RMS、4–8k 能量 | TTS 高频齿音 / 编码噪声 / 压缩 makeup |
| 每 0.6s 一响 | 音效事件表、pulse 频谱 | 底拍里的高频 click |
| 咔哒/爆音 | 最大 sample-to-sample 跳变、行拼接处 | 淡入淡出不足 / 素材切点 |
| 削顶 | 源 WAV 峰值 vs 解码 MP4 逐声道峰值 | AAC 过冲 / 母线没留余量 |

本片实测：

- 静音段是数字零（-120 dB），说明不是底噪；
- 语音帧 6–8k 能量占比 0.078 → 加 5.2k/6.8k 后 0.062；
- 最大瞬态跳变 0.454 → 0.306；
- 底拍去掉 700–4500Hz 噪声 tick，4–8k 占比为 0。

### 单句气口异常（atlas 实测）

如果只有某一句听起来“有杂音”，不要给全片加降噪。按句切 20ms 帧，算每句的 p10 / p5：

| 句 | p10 | p5 | 判断 |
|---|---:|---:|---|
| 第 10 句“点一次，三条指令按顺序落下。” | -56.9 dB | -62.6 dB | 离群，比其它句高约 10 dB |
| 其它 12 句 | -64 ~ -72 dB | -70 ~ -74 dB | 正常 |

定位：这是 TTS 自带的呼气/气口，不是全片底噪，也不是 AAC 编码问题。

处理顺序：

1. **先换 take**：同一句把逗号改成分号（`点一次；三条指令按顺序落下。`），重新生成，p10 `-56.9 → -64.7 dB`、p5 `-62.6 → -69.0 dB`，气口不再离群；语音 RMS/真峰值不变，时长只多 0.1s。
2. 连带把视觉卡点后移 0.3s，和新气口对齐。
3. 不要先试 `afftdn`：这类气口会被当成语音，几乎无效，还可能引入音乐噪声。
4. 不要用整片门限：−46 dB 扩增器实测只降 1.4 dB（受包络 release 与气口电平影响），且可能切字尾；如果必须门限，放在低通之后、release 不要太慢，但优先换 take。

规则：**按句量，找离群；单句异常先换 take，再做全片处理。**

**修复优先级**：先处理底拍/音效，再处理旁白高频；不要一上来加 `afftdn`。参考项目实测 `afftdn` 对“沙”无效，低通 + EQ 更有效。

### 持续底噪 vs 单句气口（vault 实测）

不是所有“配音有杂音”都在人声里。先量旁白本身，再量混音句间：

| 检查 | 结果 | 结论 |
|---|---|---|
| 旁白句间 RMS | -180 dBFS | 数字零，不是旁白底噪 |
| 旁白逐声道削顶 | 0 | 不是削顶 |
| 句首/句尾 10ms 最大跳变 | 0.001 | 不是拼接咔哒 |
| 旁白 4–8kHz 能量 | 2–13% | 没有失控齿音 |
| 源 WAV vs m4a mean/max | -20.5 / -4.1 dBFS 一致 | 不是 AAC 编码问题 |

旧混音句间：

| 窗口 | RMS | 主要频率 | 判断 |
|---|---:|---|---|
| 3.72–3.92s | -42.0 dBFS | 90Hz + 45Hz | 持续房间底噪的嗡声 |
| 22.09–22.31s | -43.4 dBFS | 90.9Hz + 45.5Hz | 同上 |
| 10.19–10.39s | -28.4 dBFS | 55Hz | sub 尾，偏大 |
| 27.30–27.70s | -57.8 dBFS | 90Hz | 底噪收尾 |

修法：

1. 从音效表整条删除 28.2s 房间底噪（棕噪 + 45/90Hz）；句间回到数字零。
2. SFX 母线 0.9 → 0.82；纸/继电器/伺服/木箱再降 3–6 dB；sub 0.5 → 0.24。
3. 保留图章、打字、纸卡等必要动作音；机械音效压到旁白下 12–16 dB。
4. 不先给旁白加 `afftdn` / 门限；旁白本来没有底噪。

新混音：峰值 -2.97 dBFS、RMS -20.4 dBFS、逐声道 0 削顶；纯音效峰值 -7.45 dBFS；混音 4.5kHz 以上 4.3%、纯音效 0.47%。

规则：**单句气口 → 换 TTS take；持续底噪 → 删床。** 两类问题不要用同一种“整片降噪”处理。案例：`references/case-dsh-armory-vault.md` §6。

## 4. 音效合成

用 numpy 合成，44.1kHz / 16bit / stereo。常用材质：

| 名称 | 合成思路 | 用途 |
|---|---|---|
| relay | 2ms 噪声 + 1.6k 正弦衰减 + 420Hz body | 行/字段/按钮 |
| scan | 760→1440Hz chirp 130ms | 扫码 |
| stamp | 92Hz thump + 90–1200Hz 噪声 | 印章 |
| paper | 700–6500Hz 噪声 + 17Hz flutter | 纸/工具卷 |
| snap | 1.4–9k click + 330Hz body | 磁吸/落牌 |
| servo | 150Hz saw + 22Hz tremolo | 表盘/卷轴 |
| switch | 两个 relay 间隔 65ms | 开关 |
| type | 1.2–9k click 70ms | 键盘 |
| shutter | 三记噪声 + 78Hz | 快门/闸门 |
| sub | 54Hz sine 550ms | 标题/重章 |
| pulse | 72Hz + 42Hz，**不含高频噪声** | 0.6s 底拍 |
| ratchet | 4 个 relay 间隔 55ms | 传送带 |
| crate | relay + stamp | 箱扣 |

规则：

- 底拍要么没有，要么纯低频；高频 click 在旁白下会被听成杂音。
- **出表即测高频**：`build_sfx.py` 对每个材质打印 4.5kHz 以上能量占比（整段分块平均 + 起音 2048 点两个值），取较大值 >0.30 就标 ⚠。
  2026-11-05 skilllocker 实测：13 个材质里 8 个超标（relay 0.43 / scan 0.40 / paper 0.57 / snap 0.46 / switch 0.41 / type 0.59 / shutter 0.44 / ratchet 0.44），峰值 -1.4～-6.2 dBFS，42 秒 26 个事件压在旁白（语音窗口 RMS -17.2 dBFS）下面 —— 用户反馈就是「配音有杂音」。
  只压这批材质过一遍母带（确定性、不动合成参数、不改其它材质字节）：
  `highpass=f=60, lowpass=f=4800, equalizer=f=7000:t=q:w=1.2:g=-7, equalizer=f=2600:t=q:w=1.0:g=-1.5, alimiter=limit=0.20`（≈ -14 dBFS），
  再把它们的事件增益乘 0.7、音效母线从 0.62 降到 0.50。修完混音 4.5k+ 占比 0.016、逐声道峰值 -2.00 dBFS、语音窗口 -17.2 / 非语音窗口 -37.8 dBFS。
  注意：剪映那台 ffmpeg 没有 `peaking` 滤镜，用等价的 `equalizer`。
- 音效不要复用参考片的名单与卡点；换材质。
- 立体声声像可以烘在 WAV 里；ffmpeg 混音时不要二次 pan。

## 5. 时间轴与混音

- 旁白 lead 0.5–0.6s、tail 1.0–1.3s；句间 gap 0.18–0.6s。
- 幕边界落在下一句前 0.25–0.36s，给转场留时间。
- 音效事件按绝对秒；渲染时 `adelay` 用 `ceil(t*fps)/fps` 量化到帧。
- `amix=inputs=N:duration=longest:normalize=0`；不要 `-shortest`。
- 先探真峰值，再给全片统一母线 trim；只整体平移，不改旁白/音效比例。
- 目标峰值 -1 dBFS 左右；AAC 可能过冲，留 1–3 dB 余量。

## 6. 逐帧渲染

- headless Edge + CDP，打开 `preview.html?render=1`，`Emulation.setDeviceMetricsOverride(1440,1080,1)`。
- 等 `__ready`；循环 `__setTime(i/fps)`；等两个 `rAF`；`Page.captureScreenshot({format:'png'})`。
- 已存在帧跳过；支持 `--from/--to` 断点续跑。
- 0.2–0.25s/帧是正常速度；1348 帧约 5 分钟（本机 2026-11-04 实测：1348 帧 264s，0.196 s/帧）。
- 编码（NVENC）：`h264_nvenc -preset p7 -tune hq -rc vbr -cq 19 -b:v 0 -maxrate 40M -bufsize 80M -pix_fmt yuv420p -profile:v high -level 4.2`。
- 没有 NVENC：`libx264 -preset slow -crf 18 -pix_fmt yuv420p -profile:v high -level 4.2`。
- 音频：AAC 192k / 48kHz / stereo；`-movflags +faststart`。
- 渲染后清理 PNG 帧目录；保留 meta/audio-check/接触表。

## 7. 成片 QA

必须查：

- 画幅、帧率、编码、帧数、容器时长；
- 音频时长覆盖整片；源 WAV 与解码 MP4 的峰值/削顶；
- 音画包络互相关偏移 ≤ 1 帧；
- 10 个关键帧“现截 vs 解码”平均差 / 大幅差；
- 接触表；文件大小；SHA-256。

### 两个真实假阳性

1. **`-ac 1` 假削顶**：ffmpeg 立体声→单声道下混会用 0.707 系数；左右相关时单声道峰值可能超过任一声道。检查削顶必须解码 `-ac 2`，逐声道看。
2. **AAC 过冲**：源 WAV 峰值 -2.07 dBFS，解码 AAC 仍可能超过 1.0（本片未发生，但必须验）。若发生，降低母线 2–3 dB 或加真峰值限制器，再重编码音频。

### 验收命令

脚本现在随包附带（`scripts/render.mjs`），不再依赖某一支片子的工作目录。先探测工具链，再分阶段跑：

```bash
node scripts/render.mjs --preflight                    # 浏览器 / ffmpeg / 页面，缺就当场说清楚

# 在影片工程根目录跑（页面与素材都相对它解析）
node scripts/render.mjs --root .                       # 全片：逐帧 + 混音 + 编码
node scripts/render.mjs --root . --frames-only --from 20 --to 21 --keep   # 只调试一段构图

python scripts/qa_mp4.py --mp4 out/final/film.mp4 --meta out/final/meta.json \
        --audio-check out/final/audio-check.wav        # 规格 + 逐声道削顶 + 包络偏移 + 接触表
python scripts/qa_mp4.py --mp4 ... --meta ... --ref --project-root .   # 追加逐帧回捞比对
```

分阶段是有意的：`--frames-only` 先看构图，`--audio-only` 只听混音，最后才 `--encode-only`。
`--ref` 会在 `--project-root` 打开 `preview.html` 重截关键帧与成片解码帧比对，所以那个目录必须
真的有页面和素材；不在那里跑就别加 `--ref`。

## 8. 常见坑

- 每帧写 `voice.currentTime` → 沙沙/咔哒；用迟滞纠偏。
- `-shortest` 截掉画面；用 `apad + -t`。
- `adelay` 不按帧量化 → 整体早 0–33ms。
- 混音不探真峰值 → 转 s16 削顶。
- 只压旁白不压母线 → 音效叠加后过载。
- 改音频不加版本号 → 浏览器播旧缓存。
- 在 `fonts.ready` 后重画 `t=0` → poster 变黑帧；重画 `lastT`。
- 用 CSS transition 做正片动画 → seek 与逐帧渲染不一致。
