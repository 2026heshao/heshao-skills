#!/usr/bin/env python3
"""把视频素材抽成 PNG 序列 —— 绕开「嵌 MP4 不帧精确」的唯一确定路径。

为什么需要它：直接 `<video>` 嵌 MP4 实测 0 ~ −1 帧偏差，GOP 180 未等待时恶化到
−52 帧（≈1.73s），且 render.mjs 只告警不拦。图片序列是已实测帧精确的那条路
（无声最小工程 60/60 帧、MAD 0.97–1.37），但把视频变成序列一直只有一行 ffmpeg
命令写在文档里，没人跑就会漏参数、漏裁切、漏断号。

本脚本负责四件事，且只负责这四件事：
  1 抽帧     任意帧率规整到工程 fps，按 4:3 裁切或加边
  2 校验     序号是否连续（断号会被 Math.floor 索引到错帧且不报错）
  3 对账     实际帧数 vs 期望帧数（少一帧不报错，只是末帧被重复夹取）
  4 留痕     吐出 manifest 片段（kind=sequence + 目录哈希），供 asset-manifest.json 粘贴

不做：视频解码正确性判断、色彩管理、音频抽取（声音走 build_voice / build_sfx）。

用法：
    # 标准：30fps、4:3 覆盖裁切到 1440×1080
    python scripts/frames_from_video.py --input clip.mp4 --out assets/seq/clip-a

    # 只取 2.4s–6.0s 那段
    python scripts/frames_from_video.py --input clip.mp4 --out assets/seq/clip-b --start 2.4 --end 6.0

    # 加边不裁切 / 保持原尺寸 / 只看命令不执行
    python scripts/frames_from_video.py --input clip.mp4 --out q --fit contain
    python scripts/frames_from_video.py --input clip.mp4 --out q --fit none
    python scripts/frames_from_video.py --input clip.mp4 --out q --dry-run
退出码：0 成功（可带 WARN）；1 抽帧失败或序号断号；2 参数/输入错误。

帧精确的工程用法见 references/asset-sourcing.md §5；台账契约见同文件 §6。
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

try:  # Windows 控制台默认 GBK，打印 ❌/中文会直接炸
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

W, H = 1440, 1080                    # 工程舞台尺寸（4:3）
DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")
SIZE_RE = re.compile(r"Video:.*?(\d{2,5})x(\d{2,5})")
FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps")


def find_ffmpeg(explicit=None):
    """--ffmpeg → PROMO_FFMPEG → PATH → 剪映自带。与 qa_mp4.py 同一顺序。"""
    cands = [explicit] if explicit else []
    env = os.environ.get("PROMO_FFMPEG")
    if env:
        cands.append(env)
    cands.append(shutil.which("ffmpeg") or "")
    local = os.path.join(os.path.expanduser("~"), "AppData", "Local", "JianyingPro", "apps")
    if os.path.isdir(local):
        cands += sorted(glob.glob(os.path.join(local, "*", "ffmpeg.exe")), reverse=True)
    for c in cands:
        if c and os.path.isfile(c):
            return c
    raise SystemExit(
        "找不到 ffmpeg。已尝试 --ffmpeg、PROMO_FFMPEG、PATH、剪映自带目录。\n"
        "请设 PROMO_FFMPEG 指向 ffmpeg.exe，或用 --ffmpeg <路径>。")


def parse_info(stderr):
    """从 ffmpeg -i 的 stderr 解析时长/分辨率/帧率。不用 ffprobe：精简构建常常没带。"""
    d = {"duration": None, "width": None, "height": None, "fps": None}
    m = DUR_RE.search(stderr)
    if m:
        d["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = SIZE_RE.search(stderr)
    if m:
        d["width"], d["height"] = int(m.group(1)), int(m.group(2))
    m = FPS_RE.search(stderr)
    if m:
        d["fps"] = float(m.group(1))
    return d


def build_filter(fps, fit, width=W, height=H):
    """fps 规整 + 画幅处理。cover 裁切填满，contain 加边保完整，none 不动。"""
    parts = [f"fps={fps}"]
    if fit == "cover":
        parts.append(f"scale={width}:{height}:force_original_aspect_ratio=increase")
        parts.append(f"crop={width}:{height}")
    elif fit == "contain":
        parts.append(f"scale={width}:{height}:force_original_aspect_ratio=decrease")
        parts.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black")
    return ",".join(parts)


def expected_frames(duration, fps, start=0.0, end=None):
    """期望帧数。取 round 而非 floor：fps 滤镜对尾巴超过半帧的会补一帧。"""
    stop = duration if end is None else min(end, duration)
    span = max(0.0, stop - start)
    return int(round(span * fps))


def scan_seq(dirpath):
    """返回 (帧数, 断号列表, 首号, 末号)。断号是最阴的失败：不报错，画面卡一下。"""
    nums = []
    for n in os.listdir(dirpath):
        m = re.fullmatch(r"f_(\d+)\.png", n)
        if m:
            nums.append(int(m.group(1)))
    if not nums:
        return 0, [], None, None
    nums.sort()
    gaps = [i for i in range(nums[0], nums[-1] + 1) if i not in set(nums)]
    return len(nums), gaps, nums[0], nums[-1]


def safe_rel(path, root):
    """跨盘符时 os.path.relpath 会抛 ValueError（Windows 上 C: 与 D: 之间）。

    素材常在 C: 的临时目录、工程在 D:，这不是异常情况，回退成绝对路径即可。
    """
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:
        return path.replace(os.sep, "/")


def build_cmd(ff, src, outdir, fps, fit, start, end, overwrite):
    cmd = [ff, "-hide_banner", "-nostdin"]
    if overwrite:
        cmd.append("-y")
    else:
        cmd += ["-n"]
    if start:
        cmd += ["-ss", f"{start}"]
    cmd += ["-i", src]
    if end is not None:
        cmd += ["-t", f"{max(0.0, end - start)}"]
    cmd += ["-vf", build_filter(fps, fit), "-start_number", "1",
            "-q:v", "2", os.path.join(outdir, "f_%04d.png")]
    return cmd


def manifest_snippet(asset_id, rel_path, fps, count, src_url, sha):
    """给出可直接粘进 asset-manifest.json 的条目（字段契约见 asset-sourcing.md §6）。"""
    return {
        "id": asset_id,
        "path": rel_path,
        "kind": "sequence",
        "role": "space",
        "source": {"type": "stock", "url": src_url or "", "retrievedAt": ""},
        "license": {"id": "", "commercialUse": False, "attributionRequired": False},
        "sha256": sha,
        "frameCount": count,
        "fps": fps,
        "notes": "抽帧自视频；role/source/license 待填",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="源视频")
    ap.add_argument("--out", required=True, help="输出目录（生成 f_0001.png …）")
    ap.add_argument("--fps", type=int, default=30, help="工程帧率，默认 30")
    ap.add_argument("--fit", choices=["cover", "contain", "none"], default="cover",
                    help="cover=裁切填满 4:3（默认）；contain=加边；none=保持原尺寸")
    ap.add_argument("--start", type=float, default=0.0, help="起（秒）")
    ap.add_argument("--end", type=float, default=None, help="止（秒，不含）")
    ap.add_argument("--overwrite", action="store_true", help="清空输出目录里已有的 f_*.png")
    ap.add_argument("--ffmpeg", help="ffmpeg 路径")
    ap.add_argument("--dry-run", action="store_true", help="只打印命令，不执行")
    ap.add_argument("--emit-manifest", action="store_true", help="额外打印 manifest 片段")
    ap.add_argument("--asset-id", help="manifest 条目的 id（默认取输出目录名）")
    ap.add_argument("--root", help="工程根，用于计算 manifest 里的相对 path（默认当前目录）")
    a = ap.parse_args()

    if not os.path.isfile(a.input):
        print(f"❌ 找不到源视频 {a.input}", file=sys.stderr)
        return 2
    if a.end is not None and a.end <= a.start:
        print("❌ --end 必须大于 --start", file=sys.stderr)
        return 2
    if a.fps <= 0:
        print("❌ --fps 必须为正", file=sys.stderr)
        return 2

    ff = find_ffmpeg(a.ffmpeg)

    # 先读元信息：没有它就不知道期望多少帧，也就没法对账
    try:
        probe = subprocess.run([ff, "-hide_banner", "-i", a.input],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"❌ 无法执行 ffmpeg：{e}", file=sys.stderr)
        return 2
    info = parse_info(probe.stderr or "")
    if info["duration"] is None:
        print("❌ 读不出源视频时长，文件可能损坏或不是视频。ffmpeg 输出：\n"
              + (probe.stderr or "")[-800:], file=sys.stderr)
        return 2

    outdir = os.path.abspath(a.out)
    cmd = build_cmd(ff, a.input, outdir, a.fps, a.fit, a.start, a.end, a.overwrite)

    print(f"源：{a.input}")
    print(f"  时长 {info['duration']:.2f}s · {info['width']}×{info['height']} · {info['fps']}fps")
    print(f"出：{a.out} · {a.fps}fps · fit={a.fit}")
    if a.fit == "none" and (info["width"], info["height"]) != (W, H):
        print(f"  ⚠ fit=none 但源是 {info['width']}×{info['height']}，舞台是 {W}×{H}，"
              f"工程里需要自己缩放，否则直接贴上去会错位")
    print("命令：" + " ".join(f'"{c}"' if " " in c else c for c in cmd))

    if a.dry_run:
        print("\n（--dry-run，未执行）")
        return 0

    # 输出目录：已有帧时必须显式 --overwrite，否则新旧帧混在一起
    if os.path.isdir(outdir) and glob.glob(os.path.join(outdir, "f_*.png")):
        if not a.overwrite:
            print(f"\n❌ {a.out} 里已有帧。换目录，或加 --overwrite 清掉重抽。\n"
                  f"   混批是本 skill 记录过的真实事故（中断进程留下 388 帧，下个进程静默混批）。",
                  file=sys.stderr)
            return 2
        old = glob.glob(os.path.join(outdir, "f_*.png"))
        for p in old:
            os.remove(p)
        print(f"\n已清掉旧帧 {len(old)} 张")
    os.makedirs(outdir, exist_ok=True)

    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("❌ 抽帧失败。ffmpeg 尾部输出：\n" + (r.stderr or "")[-1200:], file=sys.stderr)
        return 1

    count, gaps, first, last = scan_seq(outdir)
    want = expected_frames(info["duration"], a.fps, a.start, a.end)
    span = (min(a.end, info["duration"]) if a.end is not None else info["duration"]) - a.start

    print(f"\n抽出 {count} 帧（f_{first:04d} … f_{last:04d}）· 覆盖 {span:.2f}s @ {a.fps}fps")
    print(f"期望 {want} 帧")

    rc = 0
    if count == 0:
        print("❌ 一帧都没出。检查 --start/--end 是否超出源时长。", file=sys.stderr)
        return 1
    if gaps:
        print(f"❌ 序号断号 {len(gaps)} 处（首个 {gaps[0]}）：断号不会被渲染器发现，"
              f"只会让画面在 t 处卡一下。重抽。", file=sys.stderr)
        rc = 1
    if first != 1:
        print(f"⚠ 首帧是 f_{first:04d} 而不是 0001；工程索引按 1 起算，确认渲染器是否对齐。")
    if abs(count - want) > 1:
        print(f"⚠ 实际 {count} 帧，期望 {want} 帧，差 {count - want:+d}。"
              f"常见原因：源帧率低于工程帧率（重复帧）、尾帧不足半帧被丢。"
              f"以实际 {count} 帧为准写时序，不要按 {want} 算。")

    # 工程用法（写清楚，省得下一个人自己推）
    print(f"\n工程里这样取帧：")
    print(f"  const seq = {{ dir: '{safe_rel(outdir, os.getcwd())}', "
          f"count: {count}, fps: {a.fps} }};")
    print(f"  const i = Math.min(seq.count - 1, Math.floor(t * seq.fps));")
    print(f"  img.src = `${{seq.dir}}/f_${{String(i + 1).padStart(4, '0')}}.png`;  // 记得 await img.decode()")

    if a.emit_manifest:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from check_assets import sha256_of          # 同一套目录哈希，避免两处算法分叉
        root = os.path.abspath(a.root or os.getcwd())
        aid = a.asset_id or os.path.basename(outdir.rstrip(os.sep))
        rel = safe_rel(outdir, root)
        print("\nmanifest 片段（粘进 assets/asset-manifest.json 后补 role/source/license）：")
        print(json.dumps(manifest_snippet(aid, rel, a.fps, count, "", sha256_of(outdir)),
                         ensure_ascii=False, indent=2))

    return rc


if __name__ == "__main__":
    sys.exit(main())
