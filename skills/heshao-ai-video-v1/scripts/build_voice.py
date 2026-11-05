#!/usr/bin/env python3
"""heshao-ai-video-v1 · 逐句旁白 → 样本级句子时间轴

兑现 references/preview-contract.md §2 与 SKILL.md §4 承诺的「时间轴由旁白推导」：
本脚本站在已验证的润音链（tts_chain.py）之上，把一份口播稿变成句子级时间轴，
供 build_timeline.py 生成画面/字幕/音效，也供 render.mjs 钉帧混音。

用法：
  python scripts/build_voice.py --spec narration.json --out-dir assets/audio
  python scripts/build_voice.py --spec narration.json --out-dir assets/audio --from-cache
  python scripts/build_voice.py --make-spec            # 先吐一份口播稿模板

为什么逐句而不整段：整段读出来的音频没法给每句单独调 rate/pitch/gap，也无法把
画面卡点对齐到具体那句话（见 references/audio-and-render.md §1）。

改润音链时用 --from-cache：原始 mp3 已缓存，重润不改句子时长，时间轴不漂移。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tts_chain as tc  # noqa: E402

TEMPLATE = {
    "slug": "my-film",
    "label": "旁白试听",
    "voice": "zh-CN-XiaoyiNeural",
    "lead": 0.55,
    "tail": 1.1,
    "normalize": {
        "说明": "送 TTS 前替换，避免缩写被读成英文整词；display 是上屏文本，两者可以不同",
        "MCP": "M C P", "DSH": "D S H", "sha256": "sha 二五六",
    },
    "lines": [
        {"display": "给 AI 装了这么多，你还记得几件？", "scene": "s00",
         "rate": "+8%", "pitch": "+2Hz", "gap_after": 0.28},
        {"display": "装完就再没被叫过。", "scene": "s00",
         "rate": "+4%", "pitch": "-1Hz", "gap_after": 0.36},
    ],
}


def apply_normalize(text: str, table: dict) -> str:
    for k, v in table.items():
        if k == "说明" or not isinstance(v, str):
            continue
        text = text.replace(k, v)
    return text


def to_lines(spec: dict) -> list[tc.Line]:
    table = spec.get("normalize") or {}
    out = []
    for raw in spec.get("lines") or []:
        display = (raw.get("display") or raw.get("text") or "").strip()
        if not display:
            raise SystemExit(f"这一句没有 display/text：{raw}")
        out.append(tc.Line(
            text=apply_normalize(raw.get("tts") or display, table),
            display=display,
            rate=raw.get("rate", "+0%"),
            pitch=raw.get("pitch", "+0Hz"),
            volume=raw.get("volume", "+0%"),
            gap_after=float(raw.get("gap_after", 0.22)),
        ))
    if not out:
        raise SystemExit("spec 里 lines 为空")
    return out


def scene_map(spec: dict) -> dict:
    """把每句归到幕里，方便下游按幕取首句/末句。"""
    scenes: dict[str, dict] = {}
    for i, raw in enumerate(spec.get("lines") or []):
        sid = raw.get("scene") or "s00"
        s = scenes.setdefault(sid, {"id": sid, "lines": []})
        s["lines"].append(i)
    for s in scenes.values():
        s["first"], s["last"] = s["lines"][0], s["lines"][-1]
    return scenes


def encode_m4a(wav: Path, m4a: Path, sr: int) -> None:
    cmd = [tc.FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(wav), "-c:a", "aac", "-b:a", "192k", str(m4a)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"旁白转 m4a 失败：\n{(r.stderr or '')[-1200:]}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="口播稿 json（见 --make-spec）")
    ap.add_argument("--make-spec", action="store_true", help="打印一份模板后退出")
    ap.add_argument("--out-dir", default="assets/audio")
    ap.add_argument("--voice", help="覆盖 spec.voice；如 zh-CN-XiaoxiaoNeural / zh-CN-YunxiNeural")
    ap.add_argument("--slug", help="覆盖 spec.slug，决定输出文件名")
    ap.add_argument("--from-cache", action="store_true", help="复用已缓存的原始 mp3，只重润")
    args = ap.parse_args()

    if args.make_spec:
        print(json.dumps(TEMPLATE, ensure_ascii=False, indent=2))
        return
    if not args.spec:
        raise SystemExit("需要 --spec <narration.json>，或先用 --make-spec 生成模板")

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    slug = args.slug or spec.get("slug") or "film"
    voice = args.voice or spec.get("voice") or "zh-CN-XiaoyiNeural"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / f"_work_{slug}"

    lines = to_lines(spec)
    print(f"旁白：{len(lines)} 句  声线 {voice}  缓存复用={args.from_cache}")
    print(f"ffmpeg：{tc.FFMPEG}")

    track, meta = await tc.render_lines(
        lines, voice, work,
        lead=float(spec.get("lead", 0.55)),
        tail=float(spec.get("tail", 1.1)),
        use_cache=args.from_cache,
    )

    # 把幕归属写回每句，build_timeline 直接按句取时刻
    scenes = scene_map(spec)
    for i, m in enumerate(meta):
        m["scene"] = next((sid for sid, s in scenes.items() if i in s["lines"]), "s00")

    total = round(len(track) / tc.SR, 4)
    wav = out_dir / f"voice_{slug}.wav"
    tc._write_wav(wav, track)
    m4a = out_dir / f"voice_{slug}.m4a"
    encode_m4a(wav, m4a, tc.SR)

    payload = {
        "voice": voice, "slug": slug, "label": spec.get("label", slug),
        "sampleRate": tc.SR,
        "chain": "references/audio-and-render.md §2",
        "lead": float(spec.get("lead", 0.55)), "tail": float(spec.get("tail", 1.1)),
        "from_cache": bool(args.from_cache),
        "duration": total,
        "scenes": scenes,
        "lines": meta,
    }
    tl = out_dir / f"voice_timeline_{slug}.json"
    tl.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # _true_peak 返回线性幅度，必须过 db() 才是 dBFS（见 tts_chain._limit 的用法）
    peak = tc.db(tc._true_peak(track))
    print(f"  -> {wav}  {total:.2f}s  真峰值 {peak:.2f} dBFS")
    print(f"  -> {m4a}")
    print(f"  -> {tl}")
    if peak > -0.1:
        print("  ⚠ 旁白峰值逼近 0 dBFS，混音叠加后容易削顶 —— 先降限幅目标再重润")
    for m in meta:
        print(f"     {m['start']:6.2f}-{m['end']:6.2f}  [{m['scene']}] {m['display'] if 'display' in m else m['text']}")


if __name__ == "__main__":
    asyncio.run(main())
