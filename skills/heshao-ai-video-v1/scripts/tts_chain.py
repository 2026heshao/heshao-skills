#!/usr/bin/env python3
"""heshao-ai-video-v1 · 旁白合成与润音链（通用件，被 build_voice.py 调用）

Edge TTS 逐句出原始 mp3；ffmpeg 解码成 float PCM，于是可以在不做二次探测的前提下
用样本数拼出句子级时间轴（start/end 精确到 1/SR 秒，比词边界事件更稳，也不依赖 ffprobe）。

润音链参数来自 references/audio-and-render.md §2；改动链时务必用 --from-cache 重润，
否则每句重新合成会让时间轴漂移。

ffmpeg 自动探测顺序：PROMO_FFMPEG → PATH 上的 ffmpeg → 剪映自带（版本号会变，按目录枚举）。
"""
from __future__ import annotations

import asyncio
import glob
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import edge_tts
from scipy import ndimage
from scipy.signal import butter, sosfilt, lfilter, resample_poly

SR = 44100


def find_ffmpeg() -> str:
    """解析出可用的 ffmpeg；找不到就报得清楚，别在跑到一半时才崩。"""
    env = os.environ.get("PROMO_FFMPEG")
    cands = [env] if env else []
    cands.append(shutil.which("ffmpeg") or "")
    local = Path(os.path.expanduser("~")) / "AppData" / "Local" / "JianyingPro" / "apps"
    if local.is_dir():
        cands += sorted(glob.glob(str(local / "*" / "ffmpeg.exe")), reverse=True)
    for c in cands:
        if not c:
            continue
        p = Path(c)
        if p.is_file():
            return str(p)
    raise SystemExit(
        "找不到 ffmpeg。已尝试 PROMO_FFMPEG、PATH、剪映自带目录。\n"
        "请设环境变量 PROMO_FFMPEG 指向 ffmpeg.exe，或给 build_voice.py 传 --ffmpeg <路径>。"
    )


FFMPEG = Path(find_ffmpeg())


@dataclass
class Line:
    text: str              # text sent to TTS
    display: str           # text shown in captions / docs
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    gap_after: float = 0.22


def _decode_mp3(path: Path) -> np.ndarray:
    cmd = [
        str(FFMPEG), "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-f", "f32le", "-acodec", "pcm_f32le",
        "-ac", "1", "-ar", str(SR), "pipe:1",
    ]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def _trim_silence(x: np.ndarray, threshold_db: float = -45.0, tail: float = 0.08) -> np.ndarray:
    if len(x) == 0:
        return x
    thr = 10 ** (threshold_db / 20)
    idx = np.flatnonzero(np.abs(x) > thr)
    if len(idx) == 0:
        return x
    start = max(0, idx[0] - int(0.02 * SR))
    end = min(len(x), idx[-1] + int(tail * SR))
    return x[start:end]


def _biquad_peaking(x: np.ndarray, f0: float, gain_db: float, q: float = 1.0) -> np.ndarray:
    """RBJ cookbook peaking EQ."""
    a = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * f0 / SR
    alpha = math.sin(w0) / (2 * q)
    b0 = 1 + alpha * a
    b1 = -2 * math.cos(w0)
    b2 = 1 - alpha * a
    a0 = 1 + alpha / a
    a1 = -2 * math.cos(w0)
    a2 = 1 - alpha / a
    b = np.array([b0, b1, b2]) / a0
    aa = np.array([1.0, a1 / a0, a2 / a0])
    return lfilter(b, aa, x)


def _highpass(x: np.ndarray, cutoff: float = 75.0) -> np.ndarray:
    sos = butter(2, cutoff / (SR / 2), btype="highpass", output="sos")
    return sosfilt(sos, x)


def _lowpass(x: np.ndarray, cutoff: float = 7200.0, order: int = 8) -> np.ndarray:
    """把 7 kHz 以上的齿噪压掉 —— 这一级才是「杂音」的真正解药。

    实测（voice_xiaoyi，带限 RMS，dBFS，只统计语音帧）：
      素材原样        中频 1.5-4k -34.1   HF 5.5-11.5k/中频  -4.2 dB
      6 阶 7.2 kHz    中频 -34.0（不动）                    HF/中频  -8.2 dB
      8 阶 7.2 kHz    5.5-7k 只掉 0.3 dB                     HF/中频 -10.2 dB
      8 阶 6.5 kHz    5.5-7k 掉 1.4 dB                       HF/中频 -11.6 dB（开始发闷）
    自然语音的 HF/中频大概在 -10 ~ -14 dB，-4 dB 意味着每个字上都糊着一层
    高频 splash，听感就是"沙沙的杂音"。所以拐点保持 7.2 kHz（存在感频段不动），
    只把斜率从 6 阶加到 8 阶。注意两件已经排除掉的事：
      1) 换 96 kbps 素材几乎没用（同文本 HF/中频只差 0.7 dB、两版差值 -43 dB RMS），
         所以这不是 MP3 码率能修的，别再折腾 outputFormat；
      2) ffmpeg afftdn（nr=12/20）把这层能量当语音本身，处理后 HF/中频 -4.1 dB，
         纹丝不动 —— 只能用频域整形，不要用谱减噪，那只会引入音乐噪声。
    """
    sos = butter(order, cutoff / (SR / 2), btype="lowpass", output="sos")
    return sosfilt(sos, x)


def _compress(x: np.ndarray, threshold_db: float = -20.0, ratio: float = 2.5,
              attack: float = 0.006, release: float = 0.09, makeup_db: float = 3.0) -> np.ndarray:
    """Smooth envelope-follower compressor. Cheap, musical, good enough for VO."""
    env = np.abs(x)
    # one-pole envelope with separate attack/release
    a_att = math.exp(-1.0 / (attack * SR))
    a_rel = math.exp(-1.0 / (release * SR))
    out_env = np.empty_like(env)
    prev = 0.0
    for i, v in enumerate(env):
        coeff = a_att if v > prev else a_rel
        prev = coeff * prev + (1 - coeff) * v
        out_env[i] = prev
    thr = 10 ** (threshold_db / 20)
    gain = np.ones_like(out_env)
    mask = out_env > thr
    gain[mask] = (thr / out_env[mask]) ** (1 - 1 / ratio)
    makeup = 10 ** (makeup_db / 20)
    return x * gain * makeup


def _fade(x: np.ndarray, fade_in: float = 0.012, fade_out: float = 0.04) -> np.ndarray:
    y = x.copy()
    ni, no = int(fade_in * SR), int(fade_out * SR)
    if ni:
        y[:ni] *= np.linspace(0, 1, ni, dtype=np.float32)
    if no:
        y[-no:] *= np.linspace(1, 0, no, dtype=np.float32)
    return y


def db(x: float) -> float:
    return 20 * math.log10(max(abs(float(x)), 1e-12))


def _true_peak(x: np.ndarray, over: int = 4) -> float:
    """4× 过采样后的峰值 ≈ 真实峰值（dBFS 用 db() 换算）。
    采样峰值本身骗人：AAC 解码器输出的是重建后的连续波形，
    实测这份素材「AAC 解码峰值 − WAV 采样峰值」稳定地等于 +3.0 dB，
    也就是浏览器拿到的是比源文件响 3 dB 的波形 —— 顶到 0 dBFS 就削，
    那 6 处「咔」就是这么来的。所以必须按真实峰值收敛。"""
    y = resample_poly(x, over, 1) if over > 1 else x
    return float(np.max(np.abs(y)))


def _limit(x: np.ndarray, ceiling_db: float = -2.0, over: int = 4,
           lookahead: float = 0.004, release: float = 0.06,
           margin_db: float = 0.8) -> np.ndarray:
    """过采样真峰值限制器：只压最顶的那几个峰，整条响度几乎不动
    （不像「整体降 3 dB 换安全」那样把旁白拖小声），而且彻底不削顶。

    增益在基带（44.1 kHz）作用，只有检测走 4× 过采样 —— 这样不做上下采样
    往返，不会被抗混叠滤波磨掉高频；lookahead 让增益在峰值到来前先落，
    release 控制回升速度（防泵）。margin 补偿「基带增益、过采样峰值」这一步
    的估算误差，迭代到真实峰值达标为止。"""
    x = np.asarray(x, dtype=np.float32)
    if db(_true_peak(x, over)) <= ceiling_db:
        return x                                        # 本来就达标的，原样返回
    y = x.copy()
    for _ in range(4):
        tp = db(_true_peak(y, over))
        if tp <= ceiling_db:
            return y.astype(np.float32)
        thr = 10 ** ((ceiling_db - margin_db - max(0.0, tp - ceiling_db) * 0.2) / 20)
        up = resample_poly(y, over, 1).astype(np.float64)
        need = np.minimum(1.0, thr / np.maximum(np.abs(up), 1e-9))
        la = max(1, int(lookahead * SR * over))
        need = ndimage.minimum_filter1d(need, size=2 * la + 1, mode="nearest")
        g = need[:(len(need) // over) * over].reshape(-1, over).min(axis=1)
        a_rel = math.exp(-1.0 / (release * SR))
        prev = 1.0
        gg = np.empty(len(g), dtype=np.float64)
        for i, v in enumerate(g):
            prev = v if v < prev else a_rel * prev + (1 - a_rel) * v
            gg[i] = prev
        n = min(len(y), len(gg))
        y = (y * np.concatenate([gg[:n], np.ones(len(y) - n)])).astype(np.float32)
    return y.astype(np.float32)


#: 旁白润音链（单一事实来源）。noisefloor.py 逐帧打印每一级的输出，
#: 所以这里加一级就自动多一级审计，不会和检查脚本走偏。
VOICE_CHAIN: list[tuple[str, "object"]] = [
    ("highpass 80 Hz",      lambda x: _highpass(x, 80)),
    # 250 Hz 收 1 dB：去掉手机外放的浑浊；3.2 kHz 只加 1.2 dB ——
    # 原来 +2.2 dB 会把 5 kHz 以上那层齿噪一起顶出来，听着像杂音。
    ("EQ 250 Hz -1.0 dB",   lambda x: _biquad_peaking(x, 250, -1.0, 0.9)),
    ("EQ 3.2 kHz +1.2 dB",  lambda x: _biquad_peaking(x, 3200, 1.2, 1.0)),
    # 本片新增：5.2 kHz 收 1.5 dB，压住「嘶/齿」那一层；不碰 3.2k 的清晰度。
    ("EQ 5.2 kHz -1.5 dB",  lambda x: _biquad_peaking(x, 5200, -1.5, 1.0)),
    # 压缩比从 2.6 降到 1.9、release 从 0.10 s 放慢到 0.18 s：
    # 阈值以下的停顿段不再被 makeup 抬起来，也就不会「一停就冒底噪」的泵感。
    ("compress 1.9:1",      lambda x: _compress(x, threshold_db=-16.0, ratio=1.9,
                                                attack=0.008, release=0.18,
                                                makeup_db=1.2)),
    # 本片把 7.2 kHz 收到 6.8 kHz：参考片的 7.2k 仍留下 6–7k 的齿音层，
    # 6.8k 8 阶低通 + 上面 5.2k 的 -1.5 dB 一起，把「些许沙沙」压下去，
    # 同时保留 5k 以内的清晰度。
    ("lowpass 6.8 kHz (8th)", lambda x: _lowpass(x, 6800, 8)),
    # 旧链在这里有一步 _reverb(mix=0.075)，它的脉冲响应是 np.random.standard_normal
    # 生成的白噪声 × 指数衰减，再把湿声峰值归一到干声峰值 —— 实测叠进来的分量
    # 比节目 RMS 只低 20 dB，等于在每句话上糊一层随音量起伏的沙沙声。
    # 宣传片旁白配 BGM 本来就不需要房间感，直接去掉。
    ("fade",                _fade),
]

#: 每拍的响度目标与真峰值上限
VOICE_RMS_DB = -17.0
VOICE_TP_DB = -3.0


def polish_voice(x: np.ndarray) -> np.ndarray:
    """逐拍润音：先按 RMS 对齐响度（比原来「每拍都顶到同一峰值」稳，短句不会
    再被推得比长句响），走 EQ / 压缩 / 淡入淡出，最后过真峰值限制器。"""
    y = np.asarray(x, dtype=np.float32)
    rms = float(np.sqrt(np.mean(y.astype(np.float64) ** 2))) + 1e-9
    y = (y * (10 ** (VOICE_RMS_DB / 20) / rms)).astype(np.float32)
    for _, fn in VOICE_CHAIN:
        y = np.asarray(fn(y), dtype=np.float32)
    tp = _true_peak(y)
    if db(tp) < VOICE_TP_DB - 0.2:                 # 偏轻的拍子补到上限附近
        y = (y * (10 ** ((VOICE_TP_DB - 0.2) / 20) / (tp + 1e-9))).astype(np.float32)
    return _limit(y, ceiling_db=VOICE_TP_DB)


def _write_wav(path: Path, x: np.ndarray, stereo: bool = True) -> None:
    import wave
    path.parent.mkdir(parents=True, exist_ok=True)
    y = np.clip(x, -1, 1)
    ch = 2 if stereo else 1
    if y.ndim == 2:
        # 调用方已经给成 (n, channels)，按它自己的通道数写，别再叠一层
        ch = int(y.shape[1])
    elif stereo:
        y = np.column_stack([y, y])
    # 四舍五入而不是截断：截断恒向 0 走，等于给每个采样加一个与信号相关的
    # 量化误差（可闻失真 + 1 bit 的底噪）。听感上不值当，顺手改掉。
    pcm = np.rint(np.clip(y, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


async def synth_line(line: Line, voice: str, out_mp3: Path) -> tuple[np.ndarray, list[dict]]:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    boundaries: list[dict] = []
    last_err = None
    for attempt in range(4):
        try:
            comm = edge_tts.Communicate(
                line.text, voice, rate=line.rate, pitch=line.pitch,
                volume=line.volume, boundary="WordBoundary",
            )
            audio = bytearray()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    boundaries.append({
                        "offset": chunk["offset"] / 10_000_000,
                        "duration": chunk["duration"] / 10_000_000,
                        "text": chunk["text"],
                    })
            out_mp3.write_bytes(bytes(audio))
            wav = _decode_mp3(out_mp3)
            return wav, boundaries
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            await asyncio.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"edge-tts failed: {last_err}")


async def synth_cached(out_mp3: Path) -> tuple[np.ndarray, None]:
    """复用已经落盘的逐拍 mp3：不联网、字节完全一致，所以逐句时长与
    voice_timeline_*.json 严格不变 —— 只换润音链时必须走这条路。
    WordBoundary 事件不会重来（返回 None），由调用方从旧 timeline 继承。"""
    return _decode_mp3(out_mp3), None


async def render_lines(lines: list[Line], voice: str, workdir: Path,
                       lead: float = 0.12, tail: float = 0.25,
                       use_cache: bool = False) -> tuple[np.ndarray, list[dict]]:
    """Render a list of lines, polish each, assemble sample-accurately.

    Returns (mono float32 track, sentence metadata with absolute start/end).
    """
    workdir.mkdir(parents=True, exist_ok=True)
    pieces: list[np.ndarray] = [np.zeros(int(lead * SR), dtype=np.float32)]
    meta: list[dict] = []
    cursor = lead
    for i, line in enumerate(lines):
        mp3 = workdir / f"line_{i:03d}.mp3"
        if use_cache and mp3.exists():
            wav, bounds = await synth_cached(mp3)
        else:
            wav, bounds = await synth_line(line, voice, mp3)
        wav = _trim_silence(wav)
        wav = polish_voice(wav)
        start = cursor
        end = start + len(wav) / SR
        meta.append({
            "index": i, "text": line.display, "tts": line.text,
            "start": round(start, 4), "end": round(end, 4),
            "duration": round(end - start, 4), "boundaries": bounds,
        })
        pieces.append(wav)
        gap = line.gap_after
        if i == len(lines) - 1:
            gap = tail
        if gap > 0:
            pieces.append(np.zeros(int(gap * SR), dtype=np.float32))
            cursor += gap
        cursor += len(wav) / SR
    track = np.concatenate(pieces).astype(np.float32)
    return track, meta

