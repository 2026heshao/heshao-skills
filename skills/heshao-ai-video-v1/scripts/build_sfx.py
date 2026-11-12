#!/usr/bin/env python3
"""heshao-ai-video-v1 · 自产音效合成（不引用参考片的声音素材）

全部用 numpy 合成，44.1kHz / 16bit / stereo。默认这套材质是「机械 / 纸」家族：
继电器、扫码、印章、翻纸、磁吸、伺服、键盘、闸门、底拍、棘轮、箱扣。没有
riser / whoosh / shimmer 这类参考片常用的转场音（它们在本技能里是 banned 卡）。

  python scripts/build_sfx.py                       # 生成到 assets/sfx/
  python scripts/build_sfx.py --out-dir out/sfx-electronic --seed 20261104
  python scripts/build_sfx.py --list                # 只看有什么材质

固定 RNG seed 是刻意的：同 seed 同参数必须产出逐字节相同的 wav，这样
「旁白 + 事件表 → ffmpeg 钉帧」的混音才可复现。换一支片子时，按
references/audio-and-render.md §4 的思路新写一族材质，不要直接复用这一族的
名单与卡点排列（SKILL.md §3.5）。
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

try:  # Windows 控制台默认 GBK，打印 ⚠/❌/中文会直接炸；显式转 UTF-8
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SR = 44100
OUT = Path("assets/sfx")
RNG = np.random.default_rng(20261103)


def seed_for(base: int, name: str) -> int:
    """把 (基准 seed, 材质名) 派生成一个稳定的 int。
    default_rng() 只收 int 或 int 序列，不收字符串 —— 必须先哈希成 int。
    用 blake2s 而不是内建 hash()：后者带进程随机盐，跨次运行结果会变。"""
    import hashlib

    return int.from_bytes(
        hashlib.blake2s(f"{base}-{name}".encode("utf-8"), digest_size=8).digest(), "little"
    )


def t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def env(n: int, attack: float = 0.002, decay: float = 0.08, power: float = 2.0) -> np.ndarray:
    x = np.arange(n) / SR
    a = np.clip(x / max(attack, 1e-5), 0, 1)
    d = np.exp(-np.maximum(x - attack, 0) / max(decay, 1e-5)) ** power
    return a * d


def noise(dur: float) -> np.ndarray:
    return RNG.standard_normal(int(dur * SR))


def lowpass(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    # one-pole cascade, enough for short SFX
    a = math.exp(-2 * math.pi * cutoff / SR)
    y = x.copy()
    for _ in range(order):
        z = np.empty_like(y)
        acc = 0.0
        for i, v in enumerate(y):
            acc = (1 - a) * v + a * acc
            z[i] = acc
        y = z
    return y


def highpass(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    return x - lowpass(x, cutoff, order)


def bandpass(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return highpass(lowpass(x, hi, 2), lo, 2)


def norm(x: np.ndarray, peak: float = 0.85) -> np.ndarray:
    m = float(np.max(np.abs(x))) or 1.0
    return x / m * peak


def place(buf: np.ndarray, x: np.ndarray, at: float, gain: float = 1.0) -> np.ndarray:
    i = int(at * SR)
    n = min(len(x), len(buf) - i)
    if n > 0:
        buf[i:i + n] += x[:n] * gain
    return buf


def write(name: str, x: np.ndarray, pan: float = 0.0) -> float:
    """归一化 → 恒功率声像 → 淡入淡出 → 16bit。返回写盘后的线性峰值，被削样本数另报。"""
    x = norm(x)
    # constant-power pan; keep mono-compatible
    th = (pan + 1) * math.pi / 4
    l = x * math.cos(th)
    r = x * math.sin(th)
    st = np.stack([l, r], axis=1)
    # 3ms fade edges to avoid clicks
    f = int(0.003 * SR)
    if len(st) > 2 * f:
        ramp = np.linspace(0, 1, f)[:, None]
        st[:f] *= ramp
        st[-f:] *= ramp[::-1]
    over = int(np.sum(np.abs(st) > 1.0))     # norm() 之后还超满刻度，才是真被 clip 掉
    pcm = np.clip(st, -1, 1)
    data = (pcm * 32767).astype("<i2").tobytes()
    path = OUT / f"{name}.wav"
    import struct
    with path.open("wb") as fh:
        fh.write(b"RIFF")
        fh.write(struct.pack("<I", 36 + len(data)))
        fh.write(b"WAVEfmt ")
        fh.write(struct.pack("<IHHIIHH", 16, 1, 2, SR, SR * 4, 4, 16))
        fh.write(b"data")
        fh.write(struct.pack("<I", len(data)))
        fh.write(data)
    peak = float(np.max(np.abs(pcm))) if pcm.size else 0.0
    dbv = 20 * math.log10(max(peak, 1e-12))
    whole, attack = hf_ratio(pcm)
    hf = max(whole, attack)
    HF_REPORT.append((name, hf, whole, attack, dbv))
    print(f"  {name:10s} {len(st)/SR:5.2f}s  {path.stat().st_size/1024:5.1f} KB  写盘峰值 {dbv:5.1f} dBFS"
          f"  4.5k+ 整段 {whole:4.2f} / 起音 {attack:4.2f}"
          + ("  ⚠高频偏亮" if hf > HF_CEILING else "")
          + (f"  ⚠ 被削 {over} 样本" if over else ""))
    return peak


HF_CEILING = 0.30      # 4.5kHz 以上能量占比上限；超过就该过一遍母带，别等用户报「杂音」
HF_REPORT: list = []


def _hf_of(x, n=2048) -> float:
    fr = np.fft.rfftfreq(n, 1 / SR)
    hi = fr >= 4500
    w = np.hanning(n)
    acc = cnt = 0.0
    a = 0
    while a < len(x):
        seg = x[a:a + n]
        if seg.size < n:
            pad = np.zeros(n)
            pad[:seg.size] = seg
            seg = pad
        F = np.abs(np.fft.rfft(seg * w))
        ssum = float(F.sum())
        if ssum > 0:
            acc += float(F[hi].sum()) / ssum
            cnt += 1
        a += n
    return acc / cnt if cnt else 0.0


def hf_ratio(pcm):
    """返回 (整段占比, 起音占比)。

    为什么两个都要看：2026-11-05 skilllocker 实测里，8 个材质在「起音 2048 点」上
    占比 0.40-0.59，但按整段平均只有 2 个超 0.30 —— 因为这类材质就是「一声亮的撞击 +
    一段衰减」。压在旁白下面被听成杂音的正是那个起音，所以闸门取两者较大值，
    只看整段会把 relay/switch/type/scan 这类放过去。
    """
    if not pcm.size:
        return 0.0, 0.0
    x = pcm[:, 0] if pcm.ndim == 2 else pcm
    if x.size == 0:
        return 0.0, 0.0
    n = min(2048, x.size)
    whole = _hf_of(x, n)
    attack = float(_hf_of(x[:n], n)) if x.size >= 256 else whole
    return whole, attack


def relay() -> np.ndarray:
    dur = 0.09
    x = np.zeros(int(dur * SR))
    n = len(x)
    click = bandpass(noise(dur), 900, 6000) * env(n, 0.0005, 0.012, 2.4) * 0.6
    tone = np.sin(2 * np.pi * 1650 * t(dur)) * env(n, 0.0005, 0.018, 3.0) * 0.35
    body = np.sin(2 * np.pi * 420 * t(dur)) * env(n, 0.0005, 0.035, 2.0) * 0.2
    return click + tone + body


def scan() -> np.ndarray:
    dur = 0.13
    x = t(dur)
    f = 760 + 680 * (x / dur)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(x), 0.004, 0.05, 2.0)
    air = bandpass(noise(dur), 1800, 7000) * env(len(x), 0.002, 0.035, 2.5) * 0.25
    return sig * 0.55 + air


def stamp() -> np.ndarray:
    dur = 0.32
    n = int(dur * SR)
    thump = np.sin(2 * np.pi * 92 * t(dur)) * env(n, 0.001, 0.09, 2.3) * 0.9
    knock = bandpass(noise(dur), 90, 1200) * env(n, 0.0008, 0.028, 3.0) * 0.55
    tail = bandpass(noise(dur), 300, 2400) * env(n, 0.004, 0.14, 2.0) * 0.12
    return thump + knock + tail


def paper() -> np.ndarray:
    dur = 0.34
    n = int(dur * SR)
    x = bandpass(noise(dur), 700, 6500)
    e = np.exp(-np.maximum(np.arange(n) / SR - 0.02, 0) / 0.12)
    flutter = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * 17 * t(dur)))
    return x * e * flutter * 0.55


def snap() -> np.ndarray:
    dur = 0.16
    n = int(dur * SR)
    click = bandpass(noise(dur), 1400, 9000) * env(n, 0.0004, 0.012, 3.0) * 0.65
    body = np.sin(2 * np.pi * 330 * t(dur)) * env(n, 0.001, 0.045, 2.4) * 0.35
    return click + body


def servo() -> np.ndarray:
    dur = 0.62
    x = t(dur)
    f = 150 + 60 * np.sin(2 * np.pi * 3.2 * x) + 90 * (x / dur)
    saw = 2 * ((x * f) % 1) - 1
    sig = lowpass(saw, 900, 2) * (0.5 + 0.5 * np.sin(2 * np.pi * 22 * x))
    e = np.minimum(x / 0.02, 1) * np.exp(-np.maximum(x - 0.05, 0) / 0.24)
    return sig * e * 0.5


def switch() -> np.ndarray:
    dur = 0.22
    a = relay()
    b = relay()
    buf = np.zeros(int(dur * SR))
    place(buf, a, 0.0, 0.8)
    place(buf, b, 0.065, 1.0)
    return buf


def typekey() -> np.ndarray:
    dur = 0.07
    n = int(dur * SR)
    click = bandpass(noise(dur), 1200, 9000) * env(n, 0.0003, 0.008, 3.0) * 0.7
    tone = np.sin(2 * np.pi * 980 * t(dur)) * env(n, 0.0004, 0.015, 3.0) * 0.25
    return click + tone


def shutter() -> np.ndarray:
    dur = 0.36
    buf = np.zeros(int(dur * SR))
    for at, g in ((0.0, 1.0), (0.075, 0.75), (0.15, 0.5)):
        place(buf, bandpass(noise(0.16), 500, 5000) * env(int(0.16 * SR), 0.0008, 0.03, 2.6), at, g)
    place(buf, np.sin(2 * np.pi * 78 * t(dur)) * env(len(buf), 0.002, 0.1, 2.0), 0.0, 0.55)
    return buf


def sub() -> np.ndarray:
    dur = 0.55
    n = int(dur * SR)
    return np.sin(2 * np.pi * 54 * t(dur)) * env(n, 0.006, 0.18, 2.0)


def pulse() -> np.ndarray:
    # 纯低频 thump：不再带 700–4500 Hz 的噪声点击。
    # 参考片没有底拍；这里保留一个很轻的机械心跳，但不能在旁白下听起来像杂音。
    dur = 0.14
    n = int(dur * SR)
    low = np.sin(2 * np.pi * 72 * t(dur)) * env(n, 0.001, 0.045, 2.6) * 0.55
    sub = np.sin(2 * np.pi * 42 * t(dur)) * env(n, 0.002, 0.070, 2.0) * 0.22
    return low + sub


def ratchet() -> np.ndarray:
    dur = 0.30
    buf = np.zeros(int(dur * SR))
    for i in range(4):
        place(buf, relay(), i * 0.055, 0.75 - i * 0.08)
    return buf


def crate() -> np.ndarray:
    dur = 0.28
    buf = np.zeros(int(dur * SR))
    place(buf, relay(), 0.0, 0.9)
    place(buf, stamp(), 0.02, 0.55)
    return buf


# (材质名, 生成函数, 默认声像) —— 声像烘在 WAV 里，混音时不再二次 pan
MATERIALS = [
    ("relay", relay, -0.05),
    ("scan", scan, 0.18),
    ("stamp", stamp, 0.0),
    ("paper", paper, -0.12),
    ("snap", snap, 0.1),
    ("servo", servo, -0.15),
    ("switch", switch, 0.0),
    ("type", typekey, 0.05),
    ("shutter", shutter, 0.0),
    ("sub", sub, 0.0),
    ("pulse", pulse, 0.0),
    ("ratchet", ratchet, -0.08),
    ("crate", crate, 0.08),
]


def main() -> None:
    global OUT, RNG
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="assets/sfx", help="wav 输出目录")
    ap.add_argument("--seed", type=int, default=20261103, help="固定 RNG，保证逐字节可复现")
    ap.add_argument("--list", action="store_true", help="只列材质")
    args = ap.parse_args()

    if args.list:
        print("材质：" + ", ".join(n for n, _, _ in MATERIALS))
        return

    OUT = Path(args.out_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    peaks = []
    for name, fn, pan in MATERIALS:
        # 每个材质一条独立的随机流：加卡、删卡、调整生成顺序都不会改动其它材质的字节。
        # 共用一条全局流时，改一个材质会连带改掉它之后每一个 —— 那会让 wav 不可复现，
        # 而 render.mjs 的「旁白 + 事件表 → 钉帧混音」正依赖音效字节稳定。
        RNG = np.random.default_rng(seed_for(args.seed, name))
        peaks.append(write(name, fn(), pan))
    worst = max(peaks) if peaks else 0.0
    print(f"done → {OUT}  {len(MATERIALS)} 个材质  seed={args.seed}  写盘最高峰值 {20*math.log10(max(worst,1e-12)):.2f} dBFS")
    hot = [r for r in HF_REPORT if r[1] > HF_CEILING]
    if hot:
        print(f"  ⚠ {len(hot)}/{len(HF_REPORT)} 个材质 4.5k+ 占比 >{HF_CEILING}（取整段/起音较大值）：" +
              ", ".join(f"{r[0]} {r[1]:.2f}" for r in hot))
        print("    只压这批过母带（确定性、不动合成参数）：highpass=f=60, lowpass=f=4800, "
              "equalizer=f=7000:t=q:w=1.2:g=-7, equalizer=f=2600:t=q:w=1.0:g=-1.5, "
              "alimiter=limit=0.20（≈ -14 dBFS）；并把它们的事件增益乘 0.7、音效母线降到 0.50。")
    if worst > 0.999:
        print("  ⚠ 有材质写盘后被削顶 —— 降 norm() 的 peak 目标")


if __name__ == "__main__":
    main()
