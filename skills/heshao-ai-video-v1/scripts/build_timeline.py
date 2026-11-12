#!/usr/bin/env python3
"""heshao-ai-video-v1 · 句子时间轴 → 画面数据 + 字幕文件

吃 build_voice.py 产出的 voice_timeline_*.json，按一份镜头规格生成：

  timeline.js       window.PROMO，播放器与逐帧渲染共用的唯一时间源（契约见
                    references/preview-contract.md §2）
  narration.vtt/.srt 整句口播字幕 —— 平台外挂字幕、静音自动播放、无障碍用这个
  captions.vtt/.srt   上屏关键词字幕（只有关键词，不逐句复读）
  timeline.json       同一份数据的机器可读版，便于回归比对

一切时刻都由句子起止推导：改一句旁白 → 重跑 build_voice.py → 重跑本脚本，画面卡点、
字幕、音效落点全部跟着走，不需要手改任何秒数。

用法：
  python scripts/build_timeline.py --voice-timeline assets/audio/voice_timeline_demo.json \
      --spec film.json --out-dir assets
  python scripts/build_timeline.py --make-spec   # 镜头规格模板
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:  # Windows 控制台默认 GBK，打印 ⚠/❌/中文会直接炸；显式转 UTF-8
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TEMPLATE = {
    "title": "my-film",
    "fps": 30,
    "size": [1440, 1080],
    "voice": "assets/audio/voice_demo.m4a",
    "sfxDir": "assets/sfx/",
    "gains": {"voice": 1.0, "sfx": 0.62},
    "tailPad": 1.85,
    "scenes": [
        {"id": "s00", "title": "入库口", "code": "INTAKE", "atLine": 0, "pad": -0.30,
         "cues": {"head": {"line": 0, "plus": 0.10}, "stamp": {"line": 1, "plus": -0.06}}},
        {"id": "s01", "title": "建账", "code": "LEDGER", "atLine": 2, "pad": -0.32,
         "cues": {"sheet": {"sceneStart": True, "plus": 0.10}}},
    ],
    "captions": [
        {"line": 0, "startPlus": 0.15, "endPlus": 0.05, "text": "你还记得几件？", "kw": "几件"},
    ],
    "sfx": [
        {"t": 0.02, "name": "shutter", "g": 0.55, "pan": 0.0},
        {"at": {"line": 1, "plus": -0.06}, "name": "stamp", "g": 0.82, "pan": 0.0},
    ],
    "pulse": None,
}

TIME_KEYS = {"line", "plus", "end", "sceneStart", "scene", "global", "total", "minus"}


def ts(sec: float, Comma: str = ".") -> str:
    ms = int(round(sec * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{Comma}{ms:03d}"


def quantize(t: float, fps: int, mode: str = "nearest") -> float:
    """把秒数钉到帧边界。渲染端 adelay 用 ceil(t*fps)/fps，字幕两端分别向下/向上取整，
    就能保证字幕不早于、也不晚于它对应的帧，误差永远小于 1 帧。"""
    ticks = t * fps
    if mode == "ceil":
        idx = math.ceil(ticks - 1e-9)
    elif mode == "floor":
        idx = math.floor(ticks + 1e-9)
    else:
        idx = round(ticks)
    return idx / fps


class Resolver:
    def __init__(self, lines: list[dict], total: float, scenes: list[dict], fps: int):
        self.lines, self.total, self.scenes, self.fps = lines, total, scenes, fps

    def resolve(self, ref, default_plus: float = 0.0) -> float:
        if isinstance(ref, (int, float)):
            return float(ref)
        if isinstance(ref, dict):
            unknown = set(ref) - TIME_KEYS
            if unknown:
                raise SystemExit(f"时刻表达式含未知键：{sorted(unknown)}（可用 {sorted(TIME_KEYS)}）")
            t = 0.0
            if "global" in ref:
                t = float(ref["global"])
            elif "total" in ref:
                t = self.total - float(ref.get("minus", 0.0))
            elif "sceneStart" in ref and ref["sceneStart"]:
                sid = ref.get("scene")
                sc = next((s for s in self.scenes if s["id"] == sid), None) if sid else None
                if sc is None:
                    raise SystemExit(f"sceneStart 找不到幕 {sid}（此刻还不确定，请把 scene 写上）")
                t = sc["start"]
            elif "line" in ref:
                i = int(ref["line"])
                if not 0 <= i < len(self.lines):
                    raise SystemExit(f"line 下标越界：{i}，只有 {len(self.lines)} 句")
                t = self.lines[i]["end"] if ref.get("end") else self.lines[i]["start"]
            else:
                raise SystemExit(f"无法解析时刻：{ref}")
            return t + float(ref.get("plus", default_plus))
        raise SystemExit(f"无法解析时刻：{ref!r}")


def cue_value(r: Resolver, v):
    if isinstance(v, list):
        return [round(r.resolve(x), 2) for x in v]
    return round(r.resolve(v), 2)


def build(spec: dict, vt: dict) -> dict:
    lines = vt["lines"]
    fps = int(spec.get("fps", 30))
    voice_dur = float(vt["duration"])
    total = float(spec.get("total") or round(max(voice_dur + 0.55, lines[-1]["end"] + float(spec.get("tailPad", 1.85))), 2))

    scenes = []
    for i, s in enumerate(spec.get("scenes") or []):
        at = int(s.get("atLine", 0))
        if not 0 <= at < len(lines):
            raise SystemExit(f"幕 {s.get('id')} 的 atLine 越界：{at}，口播只有 {len(lines)} 句")
        start = 0.0 if i == 0 else round(max(0.0, lines[at]["start"] + float(s.get("pad", -0.30))), 2)
        scenes.append({"id": s["id"], "title": s.get("title", s["id"]), "code": s.get("code", s["id"].upper()),
                       "start": start, "end": None, "hud": s.get("hud", f"{i:02d} / {s.get('code', s['id'].upper())}"),
                       "cues": {}})
    for i, sc in enumerate(scenes):
        sc["end"] = scenes[i + 1]["start"] if i + 1 < len(scenes) else total

    r = Resolver(lines, total, scenes, fps)

    for src, sc in zip(spec.get("scenes") or [], scenes):
        sc["cues"] = {k: cue_value(r, v) for k, v in (src.get("cues") or {}).items()}

    captions = []
    for c in spec.get("captions") or []:
        i = int(c["line"])
        if not 0 <= i < len(lines):
            raise SystemExit(f"字幕指向的句子下标越界：line={i}，口播只有 {len(lines)} 句（0…{len(lines)-1}）")
        a = round(lines[i]["start"] + float(c.get("startPlus", 0.12)), 2)
        b = round(lines[i]["end"] + float(c.get("endPlus", 0.02)), 2)
        if b <= a:
            raise SystemExit(f"字幕窗口反了：第 {i} 句 {a} → {b}")
        captions.append([a, b, c.get("text") or lines[i]["text"], c.get("kw", "")])

    sfx = []
    for e in spec.get("sfx") or []:
        t = r.resolve(e["at"]) if "at" in e else float(e.get("t", 0.0))
        if t > total:
            raise SystemExit(f"音效 {e.get('name')} 落在 {t}s，超出成片 {total}s")
        sfx.append({"t": round(t, 3), "name": e["name"], "g": round(float(e.get("g", 0.5)), 3),
                    "pan": round(float(e.get("pan", 0.0)), 3)})
    sfx.sort(key=lambda x: x["t"])

    narration = [[round(lines[i]["start"], 2), round(lines[i]["end"], 2), lines[i]["text"]]
                 for i in range(len(lines))]

    promo = {
        "dur": total, "fps": fps, "size": spec.get("size", [1440, 1080]),
        "voice": spec.get("voice", ""), "sfxDir": spec.get("sfxDir", "assets/sfx/"),
        "gains": spec.get("gains", {"voice": 1.0, "sfx": 0.62}),
        "voiceRev": vt.get("slug", ""), "scenes": scenes,
        "lines": [{"start": l["start"], "end": l["end"], "text": l["text"]} for l in lines],
        "captions": captions, "sfx": sfx,
    }
    if spec.get("pulse"):
        promo["pulse"] = spec["pulse"]
    return {"promo": promo, "narration": narration, "total": total, "fps": fps, "voiceSlug": vt.get("slug", "")}


def write_vtt(path: Path, cues: list, fps: int, title: str, with_kw: bool = False) -> None:
    out = ["WEBVTT", "", f"NOTE {title} · 时刻已钉到 1/{fps}s 帧边界 · 由 scripts/build_timeline.py 生成，勿手改", ""]
    for i, c in enumerate(cues, 1):
        a = quantize(c[0], fps, "floor")
        b = quantize(c[1], fps, "ceil")
        if b <= a:
            b = round(a + 1.0 / fps, 6)
        text = c[2] if not with_kw or len(c) < 4 or not c[3] else f"{c[2]} <c>{c[3]}</c>"
        out += [str(i), f"{ts(a)} --> {ts(b)}", text, ""]
    path.write_text("\n".join(out), encoding="utf-8")


def write_srt(path: Path, cues: list, fps: int) -> None:
    out = []
    for i, c in enumerate(cues, 1):
        a = quantize(c[0], fps, "floor")
        b = quantize(c[1], fps, "ceil")
        if b <= a:
            b = round(a + 1.0 / fps, 6)
        out += [str(i), f"{ts(a, ',')} --> {ts(b, ',')}", c[2], ""]
    path.write_text("\n".join(out), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="镜头规格 json")
    ap.add_argument("--voice-timeline", help="build_voice.py 产出的 voice_timeline_*.json")
    ap.add_argument("--make-spec", action="store_true")
    ap.add_argument("--out-dir", default="assets")
    args = ap.parse_args()

    if args.make_spec:
        print(json.dumps(TEMPLATE, ensure_ascii=False, indent=2))
        return
    if not (args.spec and args.voice_timeline):
        raise SystemExit("需要 --spec 与 --voice-timeline（或先用 --make-spec 看模板）")

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    vt = json.loads(Path(args.voice_timeline).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    built = build(spec, vt)
    promo, narration, fps = built["promo"], built["narration"], built["fps"]

    (out_dir / "timeline.js").write_text(
        "/* 由 scripts/build_timeline.py 生成，勿手改。数据源：voice_timeline + 镜头规格 */\n"
        "window.PROMO = " + json.dumps(promo, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8")
    (out_dir / "timeline.json").write_text(json.dumps(built, ensure_ascii=False, indent=2), encoding="utf-8")
    write_vtt(out_dir / "narration.vtt", narration, fps, "整句口播字幕")
    write_srt(out_dir / "narration.srt", narration, fps)
    write_vtt(out_dir / "captions.vtt", promo["captions"], fps, "上屏关键词字幕", with_kw=True)
    write_srt(out_dir / "captions.srt", promo["captions"], fps)

    print(f"成片时长 {promo['dur']}s  fps={fps}  幕 {len(promo['scenes'])}  句 {len(narration)}  关键词字幕 {len(promo['captions'])}  音效 {len(promo['sfx'])}")
    for s in promo["scenes"]:
        print(f"  {s['id']} {s['start']:6.2f}-{s['end']:6.2f}  {s['title']}  cues={list(s['cues'])}")
    bad = [ (a, b) for a, b, *_ in [(c[0], c[1]) for c in promo["captions"]] if b <= a ]
    print("字幕窗口检查：", "OK" if not bad else f"❌ {bad}")
    if promo["captions"]:
        last = max(c[1] for c in promo["captions"])
        if last > promo["dur"]:
            print(f"  ⚠ 最后一条字幕 {last}s 超出成片 {promo['dur']}s")
    print(f"  -> {out_dir/'timeline.js'} / timeline.json / narration.vtt+.srt / captions.vtt+.srt")


if __name__ == "__main__":
    main()
