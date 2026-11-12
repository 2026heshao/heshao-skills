#!/usr/bin/env python3
"""节奏闸门：把「1× 就要是舒服的速度」变成可判 PASS/FAIL 的五个量。

阈值来源：2026-11-05 skilllocker 实测 —— 旁白占时 87.2%（字数不缺），慢的是留白；
但留白里有三种是**设计需要的呼吸**，不能当缺陷报：开场 lead、幕首 lead、换幕呼吸。
所以分开量、分开给上限：

  开场 lead      ≤ 0.60s   （第一句之前的静默）
  幕首 lead      ≤ 0.45s   （换幕后到该幕第一句，含硬切呼吸）
  句间空白       ≤ 0.30s   （同一幕内相邻句之间；narration 的 gap_after 默认 0.16–0.22）
  跨幕空场       ≤ 0.55s   （上一幕最后一句结束 → 下一幕第一句开始，真正的"没人说话也没动作"）
  片尾空场       ≤ 1.20s   （最后一句结束 → 成片结束，含淡出与 CTA hold）
  旁白占时比     ≥ 0.80

用法：
    python scripts/pacing_report.py --timeline <项目>/assets/timeline.json
退出码：0 通过；1 超标；2 参数/文件错误。

注意：阈值目前只有 1 个项目（skilllocker）的实测支撑，第 2 个项目复现后再收紧；
调阈值要同时改 references/story-rhythm.md §1。
"""
import argparse
import json
import os
import sys

try:  # Windows 控制台默认 GBK，打印 ❌/中文会直接炸；显式转 UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LIMITS = {
    "open_lead": 0.60,
    "scene_lead": 0.45,
    "line_gap": 0.30,
    "cross_scene_air": 0.55,
    "tail_air": 1.20,
    "speech_min": 0.80,
}


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["promo"] if "promo" in d else d


def lines_of(scene, lines):
    return [l for l in lines if scene["start"] - 1e-6 <= l["start"] < scene["end"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", required=True)
    for k in LIMITS:
        ap.add_argument("--" + k.replace("_", "-"), type=float, default=LIMITS[k])
    a = ap.parse_args()
    if not os.path.exists(a.timeline):
        print(f"❌ 找不到 {a.timeline}", file=sys.stderr)
        return 2

    P = load(a.timeline)
    lines, scenes, dur = P["lines"], P["scenes"], P["dur"]
    speech = sum(l["end"] - l["start"] for l in lines)
    ratio = speech / dur if dur else 0.0
    bad = []
    if ratio < a.speech_min:
        bad.append(f"旁白占时比 {ratio*100:.1f}% < {a.speech_min*100:.0f}% —— 信息密度不够，不是留白问题")

    print(f"成片 {dur:.2f}s  旁白 {speech:.2f}s  占时比 {ratio*100:.1f}%  (下限 {a.speech_min*100:.0f}%)")

    def check(name, val, limit, where):
        mark = "OK" if val <= limit + 1e-6 else "超标"
        print(f"  {name:<12} {where:<10} {val:5.2f}s / 上限 {limit:.2f}s   {mark}")
        if val > limit + 1e-6:
            bad.append(f"{name}（{where}）{val:.2f}s > {limit:.2f}s")
        return val

    for i, sc in enumerate(scenes):
        seg = lines_of(sc, lines)
        if not seg:
            bad.append(f"{sc['id']} {sc['title']} 整幕没有旁白")
            continue
        last = (i == len(scenes) - 1)
        if i == 0:
            check("开场 lead", seg[0]["start"] - sc["start"], a.open_lead, sc["id"])
        else:
            prev = lines_of(scenes[i - 1], lines)
            if prev:
                check("跨幕空场", seg[0]["start"] - prev[-1]["end"], a.cross_scene_air,
                      f"{scenes[i-1]['id']}→{sc['id']}")
            check("幕首 lead", seg[0]["start"] - sc["start"], a.scene_lead, sc["id"])
        gaps = [seg[j + 1]["start"] - seg[j]["end"] for j in range(len(seg) - 1)]
        if gaps:
            check("句间空白", max(gaps), a.line_gap, sc["id"])
        if last:
            check("片尾空场", dur - seg[-1]["end"], a.tail_air, sc["id"])

    if bad:
        print("\n❌ 节奏闸门未过：")
        for b in bad:
            print("   · " + b)
        print("   修法：压 narration.json 的 gap_after 与 timeline-spec 的幕间 pad / tailPad；"
              "落版除 CTA hold 外不要留空场。禁止用拉长镜头凑时长，也不要默认用户会开倍速。")
        return 1
    print("\n✅ 节奏闸门通过：1× 播放不需要倍速")
    return 0


if __name__ == "__main__":
    sys.exit(main())
