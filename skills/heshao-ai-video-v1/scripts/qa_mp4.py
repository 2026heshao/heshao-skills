#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generic MP4 QA for a 4:3 product promo.

Checks: size / fps / codec / frame count / duration / audio peak / clipping /
A/V envelope offset / contact sheet / optional frame re-capture comparison.

Usage:
  python qa_mp4.py --mp4 out/final/film.mp4 --meta out/final/meta.json
  python qa_mp4.py --mp4 ... --meta ... --ref --render scripts/render.mjs
  python qa_mp4.py --mp4 ... --times 1.2,8.0,19.9,43.4 --width 1440 --height 1080

Requires: ffmpeg, numpy, Pillow. Set PROMO_FFMPEG if ffmpeg is not on PATH.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

def find_ffmpeg() -> str:
    """PROMO_FFMPEG → PATH → 剪映自带。全落空时给可执行的指示，而不是抛裸 traceback。"""
    import glob
    import shutil

    env = os.environ.get("PROMO_FFMPEG")
    cands = [env] if env else []
    cands.append(shutil.which("ffmpeg") or "")
    local = Path(os.path.expanduser("~")) / "AppData" / "Local" / "JianyingPro" / "apps"
    if local.is_dir():
        cands += sorted(glob.glob(str(local / "*" / "ffmpeg.exe")), reverse=True)
    for c in cands:
        if c and Path(c).is_file():
            return c
    raise SystemExit(
        "找不到 ffmpeg，成片 QA 跑不了。已尝试 PROMO_FFMPEG、PATH、剪映自带目录。\n"
        "请设 PROMO_FFMPEG 指向 ffmpeg.exe，或用 --ffmpeg <路径>。"
    )


FF = find_ffmpeg()
fails: list[str] = []


def chk(ok, msg):
    if not ok:
        fails.append(msg)
    print(("  OK  " if ok else "  !!  ") + msg)
    return ok


def run(args, **kw):
    return subprocess.run([FF, "-hide_banner", *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", **kw)


def info(mp4: Path):
    s = run(["-i", str(mp4)]).stderr
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", s)
    v = re.search(r"Video: (\w+)[^\n]*?, (\d{2,5}x\d{2,5})[^\n]*?, ([\d.]+) fps", s)
    a = re.search(r"Audio: (\w+)[^\n]*?, (\d+) Hz, ([^,\n]+),[^\n]*?, (\d+) kb/s", s)
    return {
        "seconds": int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)) if dur else None,
        "size": v.group(2) if v else "?",
        "codec": v.group(1) if v else "?",
        "fps": float(v.group(3)) if v else None,
        "audio": f"{a.group(1)} {a.group(2)}Hz {a.group(3)} {a.group(4)}kb/s" if a else "?",
    }


def frame_count(mp4: Path) -> int:
    r = run(["-loglevel", "error", "-i", str(mp4), "-map", "0:v", "-c", "copy",
             "-f", "framecrc", "-"])
    return len(re.findall(r"^\d+,", r.stdout, re.M))


def decode_audio(mp4: Path) -> np.ndarray:
    raw = subprocess.run(
        [FF, "-hide_banner", "-loglevel", "error", "-i", str(mp4),
         "-map", "0:a", "-ac", "2", "-ar", "48000",
         "-f", "f32le", "-acodec", "pcm_f32le", "-"],
        capture_output=True).stdout
    # Keep stereo: -ac 1 uses 0.707 downmix and can create fake peaks.
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def audio_stats(mp4: Path) -> dict:
    r = run(["-i", str(mp4), "-map", "0:a",
             "-af", "astats=measure_perchannel=Peak_level+RMS_level:measure_overall=Peak_level+RMS_level",
             "-f", "null", "-"])
    peaks = [float(x) for x in re.findall(r"Peak level dB: (-?[\d.]+)", r.stderr)]
    rms = [float(x) for x in re.findall(r"RMS level dB: (-?[\d.]+)", r.stderr)]
    x = decode_audio(mp4)
    return {
        "peak": max(peaks) if peaks else None,
        "rms": max(rms) if rms else None,
        "clips": int((np.abs(x) >= 0.999).sum()),
        "seconds": len(x) / 48000,
    }


def read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    import wave
    with wave.open(str(path), "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    x = raw.reshape(-1, ch).astype(np.float32) / 32768.0
    return x.mean(axis=1), sr


def av_offset(mp4: Path, ref_wav: Path | None) -> float | None:
    if not ref_wav or not ref_wav.exists():
        return None
    a, sr = read_wav_mono(ref_wav)
    if sr != 48000:
        return None
    b = decode_audio(mp4).mean(axis=1)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    hop = 480  # 10 ms
    m = n // hop
    ea = np.sqrt((a[:m * hop].reshape(m, hop) ** 2).mean(axis=1) + 1e-12)
    eb = np.sqrt((b[:m * hop].reshape(m, hop) ** 2).mean(axis=1) + 1e-12)
    start, end = int(5 * 100), min(int(35 * 100), m)
    if end <= start:
        return None
    ea, eb = ea[start:end], eb[start:end]
    ea, eb = ea - ea.mean(), eb - eb.mean()
    corr = np.fft.irfft(np.fft.rfft(ea, len(ea) * 2) * np.conj(np.fft.rfft(eb, len(eb) * 2)))
    lags = np.concatenate([np.arange(0, 21), np.arange(-20, 0)])
    vals = np.concatenate([corr[:21], corr[-20:]])
    return float(lags[int(np.argmax(vals))]) * 10.0


def extract(mp4: Path, idx: int, fps: float, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["-y", "-ss", f"{idx / fps:.6f}", "-i", str(mp4),
         "-frames:v", "1", "-f", "image2", str(dest)])
    return dest


def resample(render: Path, idx: int, fps: float, root: Path) -> Path:
    subprocess.run(
        ["node", str(render), "--frames-only",
         "--from", f"{idx / fps:.6f}", "--to", f"{(idx + 0.5) / fps:.6f}", "--keep"],
        cwd=str(root), check=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace")
    return root / "out" / "frames" / f"f{idx:05d}.png"


def diff(a: Path, b: Path) -> tuple[float, float]:
    x = np.asarray(Image.open(a).convert("L"), dtype=np.int16)
    y = np.asarray(Image.open(b).convert("L"), dtype=np.int16)
    h, w = min(x.shape[0], y.shape[0]), min(x.shape[1], y.shape[1])
    d = np.abs(x[:h, :w] - y[:h, :w])
    return float(d.mean()), float((d > 24).mean())


def luminance(path: Path) -> float:
    return float(np.asarray(Image.open(path).convert("L"), dtype=np.float32).mean())


def frame_content(path: Path) -> tuple[float, float, float]:
    """返回 (平均亮度, 亮度标准差, 亮像素占比)。

    「这一帧是不是空的」要问有没有结构，不是够不够亮：本技能 7 个世界里
    atlas #05070f、tower #050b16、blueprint #071b2b、depot #080d0a 都是暗底，
    有内容的落定帧实测 mean 只有 5~7（stddev 18、亮像素 1.2%），
    而快门闭合/纯黑帧是 mean 2.8、stddev 3.2、亮像素 0.05%。
    所以旧判据 mean > 8 会把暗色世界的正常画面误判成空镜。"""
    x = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    return float(x.mean()), float(x.std()), float((x > 40).mean())


def frame_is_blank(path: Path) -> bool:
    """既暗又无结构才算空帧。落在换幕快门上的采样仍会被抓到（那确实是空帧）。"""
    mean, std, bright = frame_content(path)
    return std < 6.0 and bright < 0.003


def sheet(rows: list[tuple[float, Path]], dest: Path, cols: int = 4) -> Path:
    tw, th, pad, label = 420, 315, 12, 26
    r = (len(rows) + cols - 1) // cols
    img = Image.new("RGB", (cols * tw + (cols + 1) * pad,
                            r * (th + label) + (r + 1) * pad), (12, 18, 14))
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 17)
    except OSError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(img)
    for i, (t, p) in enumerate(rows):
        c, rr = i % cols, i // cols
        x = pad + c * (tw + pad)
        y = pad + rr * (th + label + pad)
        img.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
        d.text((x + 2, y + th + 4), f"{t:.1f}s", fill=(242, 235, 220), font=font)
    img.save(dest)
    return dest


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--mp4", required=True)
    ap.add_argument("--meta", help="meta.json with total/fps")
    ap.add_argument("--times", default="1.2,3.0,8.0,13.3,16.0,19.9,22.8,26.6,31.0,35.5,39.8,43.4")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--out", default=None)
    ap.add_argument("--ref", action="store_true", help="re-capture frames via render.mjs")
    ap.add_argument("--render", default=str(Path(__file__).resolve().parent / "render.mjs"))
    ap.add_argument("--ffmpeg", default=None, help="显式指定 ffmpeg.exe，覆盖自动探测")
    ap.add_argument("--project-root", default=None,
                    help="影片工程根目录；--ref 在这里打开 preview.html 截帧（默认当前目录）。"
                         "注意不要把 --render 的路径当成工程根目录。")
    ap.add_argument("--audio-check", default=None, help="reference WAV for A/V offset")
    args = ap.parse_args()

    if args.ffmpeg:
        global FF
        if not Path(args.ffmpeg).is_file():
            sys.exit(f"--ffmpeg 指向的文件不存在：{args.ffmpeg}")
        FF = args.ffmpeg
    print(f"ffmpeg: {FF}")

    mp4 = Path(args.mp4).resolve()
    project_root = Path(args.project_root).resolve() if args.project_root else Path.cwd()
    if not mp4.exists():
        sys.exit(f"missing MP4: {mp4}")
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8")) if args.meta else {}
    total = float(meta.get("total", 0))
    fps_meta = float(meta.get("fps", 30))
    n_expect = round(total * fps_meta) if total else None
    dur_expect = n_expect / fps_meta if n_expect else None
    outdir = Path(args.out).resolve() if args.out else mp4.parent / "mp4check"
    outdir.mkdir(parents=True, exist_ok=True)
    times = [float(x) for x in args.times.split(",") if x.strip()]

    i, n, a = info(mp4), frame_count(mp4), audio_stats(mp4)
    print(f"MP4 {mp4.name}")
    print(f"  {i['seconds']}s  {i['size']}  {i['codec']} @{i['fps']}fps  {i['audio']}")
    chk(i["size"] == f"{args.width}x{args.height}", f"size {i['size']} == {args.width}x{args.height}")
    chk(abs((i["fps"] or 0) - fps_meta) < 0.01, f"fps {i['fps']} == {fps_meta}")
    chk(i["codec"].lower() in ("h264", "hev1", "hevc"), f"codec {i['codec']}")
    if n_expect:
        chk(abs(n - n_expect) <= 1, f"frames {n} == {n_expect}")
        chk(abs((i["seconds"] or 0) - dur_expect) <= 1 / fps_meta + 0.02,
            f"container {i['seconds']}s == {dur_expect:.4f}s")
        chk(a["seconds"] >= dur_expect - 0.05, f"audio {a['seconds']:.3f}s covers {dur_expect:.3f}s")
    chk(a["clips"] == 0, f"clipping samples {a['clips']} (stereo per-channel)")
    chk(a["peak"] is not None and a["peak"] <= 0.0,
        f"peak {a['peak']:.2f} dBFS / RMS {a['rms']:.2f} dBFS")

    off = av_offset(mp4, Path(args.audio_check) if args.audio_check else (mp4.parent / "audio-check.wav"))
    if off is not None:
        chk(abs(off) <= 33.4, f"A/V envelope offset {off:+.1f}ms (<= 1 frame)")
    else:
        print("  ..  skip A/V offset (no 48k audio-check.wav)")

    rows = []
    for t in times:
        idx = int(round(t * fps_meta))
        p = extract(mp4, idx, fps_meta, outdir / f"t_{t:05.1f}.png".replace(" ", "0"))
        rows.append((t, p))
        if t >= 2.0:
            mean, std, bright = frame_content(p)
            chk(not frame_is_blank(p),
                f"{t:4.1f}s frame has content (mean {mean:5.1f}  std {std:5.1f}  亮像素 {bright*100:4.2f}%)")
    print("  sheet:", sheet(rows, outdir / "sheet.png"))

    if args.ref:
        render = Path(args.render).resolve()
        print("  frame re-capture:")
        bad = []
        for t in times[2:]:
            idx = int(round(t * fps_meta))
            ref = resample(render, idx, fps_meta, project_root)
            got = extract(mp4, idx, fps_meta, outdir / f"ref_{idx:05d}.mp4.png")
            m, large = diff(ref, got)
            ok = m < 6.0 and large < 0.20
            if not ok:
                bad.append((t, m, large))
            print(f"    {'OK' if ok else '!!'} {t:5.1f}s frame {idx:5d} mean {m:5.2f} large {large * 100:5.1f}%")
        chk(not bad, f"decoded frames match re-captures (fail {len(bad)})")

    print()
    print("PASS" if not fails else f"FAIL ({len(fails)})")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
