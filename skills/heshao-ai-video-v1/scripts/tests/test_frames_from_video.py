"""frames_from_video.py 的回归测试。

为什么这条重要：抽帧是「视频素材进工程」的唯一帧精确入口。它一旦静默出错，
错误不是崩，而是**序号断号**或**帧数与时长对不上**——渲染器照跑，画面在某一秒
卡一下，成片 QA 也查不出来（因为帧数、时长、编码全对）。所以这里既测纯函数，
也跑一次真实 ffmpeg（有 ffmpeg 才跑，缺了跳过而不是假装通过）。
"""
import importlib.util
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location(
    "frames_from_video", os.path.join(SKILL, "scripts", "frames_from_video.py"))
fv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fv)

TMP = Path(HERE) / "_tmp_frames"

REAL_STDERR = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'clip.mp4':
  Metadata:
    major_brand     : isom
  Duration: 00:00:06.04, start: 0.000000, bitrate: 2148 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709), 1920x1080 [SAR 1:1 DAR 16:9], 2050 kb/s, 30 fps, 30 tbr, 15360 tbn
"""


def _probe_ffmpeg():
    try:
        return fv.find_ffmpeg()
    except SystemExit:
        return None


FF = _probe_ffmpeg()


def setUpModule():
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)


def tearDownModule():
    if TMP.exists():
        shutil.rmtree(TMP)


class TestParseInfo(unittest.TestCase):
    def test_reads_duration_size_fps(self):
        d = fv.parse_info(REAL_STDERR)
        self.assertAlmostEqual(d["duration"], 6.04, places=2)
        self.assertEqual((d["width"], d["height"]), (1920, 1080))
        self.assertEqual(d["fps"], 30.0)

    def test_missing_duration_returns_none(self):
        d = fv.parse_info("clip.mp4: Invalid data found when processing input")
        self.assertIsNone(d["duration"], "读不出时长要能被上层识别为坏文件")

    def test_hour_long_input(self):
        d = fv.parse_info("  Duration: 01:02:03.50, start: 0.0, bitrate: 1 kb/s")
        self.assertAlmostEqual(d["duration"], 3723.5, places=2)


class TestFilter(unittest.TestCase):
    def test_cover_crops_to_stage(self):
        f = fv.build_filter(30, "cover")
        self.assertIn("fps=30", f)
        self.assertIn("force_original_aspect_ratio=increase", f)
        self.assertIn("crop=1440:1080", f)

    def test_contain_pads(self):
        f = fv.build_filter(30, "contain")
        self.assertIn("force_original_aspect_ratio=decrease", f)
        self.assertIn("pad=1440:1080", f)
        self.assertNotIn("crop", f)

    def test_none_only_normalizes_fps(self):
        self.assertEqual(fv.build_filter(30, "none"), "fps=30")


class TestExpectedFrames(unittest.TestCase):
    def test_whole_clip(self):
        self.assertEqual(fv.expected_frames(2.0, 30), 60)

    def test_subrange(self):
        self.assertEqual(fv.expected_frames(6.0, 30, 2.0, 4.0), 60)

    def test_end_beyond_duration_is_clamped(self):
        self.assertEqual(fv.expected_frames(3.0, 30, 0.0, 99.0), 90)

    def test_zero_span(self):
        self.assertEqual(fv.expected_frames(6.0, 30, 2.0, 2.0), 0)


class TestScanSeq(unittest.TestCase):
    def _mk(self, nums, name="s"):
        d = TMP / name
        d.mkdir(exist_ok=True)
        for n in nums:
            (d / f"f_{n:04d}.png").write_bytes(bytes([1]))
        return d

    def test_continuous(self):
        d = self._mk([1, 2, 3, 4], "ok")
        self.assertEqual(fv.scan_seq(str(d))[:2], (4, []))

    def test_gap_is_reported(self):
        d = self._mk([1, 2, 5, 6], "gap")
        count, gaps, first, last = fv.scan_seq(str(d))
        self.assertEqual((count, first, last), (4, 1, 6))
        self.assertEqual(gaps, [3, 4], "断号必须被点名，否则渲染器会索引到错帧")

    def test_empty(self):
        d = TMP / "empty"
        d.mkdir(exist_ok=True)
        self.assertEqual(fv.scan_seq(str(d)), (0, [], None, None))

    def test_ignores_non_png(self):
        d = self._mk([1, 2], "mixed")
        (d / "notes.txt").write_text("x", encoding="utf-8")
        self.assertEqual(fv.scan_seq(str(d))[0], 2)


class TestCmd(unittest.TestCase):
    def test_sequence_starts_at_one(self):
        cmd = fv.build_cmd("ff", "in.mp4", "out", 30, "cover", 0.0, None, False)
        self.assertIn("-start_number", cmd)
        self.assertEqual(cmd[cmd.index("-start_number") + 1], "1")

    def test_never_uses_shortest(self):
        cmd = fv.build_cmd("ff", "in.mp4", "out", 30, "cover", 0.0, None, False)
        self.assertNotIn("-shortest", cmd, "抽帧不是混音，-shortest 会截断")

    def test_subrange_becomes_dash_t(self):
        cmd = fv.build_cmd("ff", "in.mp4", "out", 30, "cover", 2.0, 5.5, False)
        self.assertEqual(cmd[cmd.index("-ss") + 1], "2.0")
        self.assertAlmostEqual(float(cmd[cmd.index("-t") + 1]), 3.5)

    def test_overwrite_flag(self):
        self.assertIn("-y", fv.build_cmd("ff", "i", "o", 30, "cover", 0, None, True))
        self.assertIn("-n", fv.build_cmd("ff", "i", "o", 30, "cover", 0, None, False))

    def test_output_pattern(self):
        cmd = fv.build_cmd("ff", "i", os.path.join("out", ""), 30, "cover", 0, None, False)
        self.assertTrue(cmd[-1].endswith(os.path.join("out", "f_%04d.png")), cmd[-1])


class TestSafeRel(unittest.TestCase):
    def test_forward_slashes(self):
        p = fv.safe_rel(os.path.join("a", "b"), os.getcwd())
        self.assertNotIn("\\", p)

    @unittest.skipUnless(os.name == "nt", "跨盘符只在 Windows 上成立")
    def test_cross_drive_falls_back_to_absolute(self):
        p = fv.safe_rel("C:/some/dir", "D:/other")
        self.assertTrue(p.startswith("C:"), "跨盘不能抛 ValueError，要回退绝对路径")


class TestManifestSnippet(unittest.TestCase):
    def test_fields_match_contract(self):
        s = fv.manifest_snippet("clip-a", "assets/seq/clip-a", 30, 60, "https://x/1", "a" * 64)
        for k in ("id", "path", "kind", "role", "source", "license", "sha256", "frameCount", "fps"):
            self.assertIn(k, s)
        self.assertEqual(s["kind"], "sequence")
        self.assertEqual(s["frameCount"], 60)

    def test_snippet_shape_accepted_by_check_assets(self):
        """片段要能直接被 asset-manifest 的校验器读懂（kind/role 合法、可 JSON 序列化）。"""
        spec = importlib.util.spec_from_file_location(
            "check_assets", os.path.join(SKILL, "scripts", "check_assets.py"))
        ca = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ca)
        s = fv.manifest_snippet("x", "assets/seq/x", 30, 2, "", "b" * 64)
        d = TMP / "seqx"
        d.mkdir(exist_ok=True)
        (d / "f_0001.png").write_bytes(b"1")
        (d / "f_0002.png").write_bytes(b"2")
        s["path"] = "seqx"
        issues, _ = ca.check_manifest({"assets": [s]}, str(TMP))
        codes = {i.code for i in issues}
        self.assertNotIn("E005", codes, "kind 不合法")
        self.assertNotIn("E006", codes, "role 不合法")
        json.dumps(s, ensure_ascii=False)   # 必须可序列化


class TestMainGuards(unittest.TestCase):
    @staticmethod
    def _run(*argv):
        old = __import__("sys").argv
        __import__("sys").argv = ["frames_from_video.py", *argv]
        try:
            return fv.main()
        finally:
            __import__("sys").argv = old

    def test_missing_input_returns_2(self):
        self.assertEqual(self._run("--input", str(TMP / "ghost.mp4"), "--out", str(TMP / "o")), 2)

    def test_bad_range_returns_2(self):
        src = TMP / "tiny.mp4"
        src.write_bytes(b"not-really-a-video")
        self.assertEqual(self._run("--input", str(src), "--out", str(TMP / "o"),
                                   "--start", "5", "--end", "3"), 2)

    def test_bad_fps_returns_2(self):
        src = TMP / "tiny2.mp4"
        src.write_bytes(b"x")
        self.assertEqual(self._run("--input", str(src), "--out", str(TMP / "o"), "--fps", "0"), 2)


@unittest.skipUnless(FF, "本机没有 ffmpeg，跳过真实抽帧用例（不算通过）")
class TestEndToEnd(unittest.TestCase):
    """2s / 24fps 源 → 30fps 序列。验证整条链路真的跑出 60 帧且序号连续。"""

    @classmethod
    def setUpClass(cls):
        cls.src = TMP / "src24.mp4"
        if not cls.src.exists():
            r = subprocess.run(
                [FF, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                 "-i", "testsrc=size=320x240:rate=24:duration=2",
                 "-c:v", "mpeg4", "-y", str(cls.src)],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode != 0:
                raise unittest.SkipTest("本机 ffmpeg 编不出测试视频：" + (r.stderr or "")[-200:])

    def test_extracts_continuous_30fps_sequence(self):
        out = TMP / "seq30"
        rc = TestMainGuards._run("--input", str(self.src), "--out", str(out),
                                 "--fps", "30", "--ffmpeg", FF)
        self.assertEqual(rc, 0, "抽帧应成功")
        count, gaps, first, last = fv.scan_seq(str(out))
        self.assertEqual(count, 60, f"2.00s@30fps 应为 60 帧，实际 {count}")
        self.assertEqual(gaps, [], "不许断号")
        self.assertEqual((first, last), (1, 60))

    def test_refuses_to_mix_with_existing_frames(self):
        out = TMP / "seq30"          # 复用上一个用例的输出目录
        if not (out / "f_0001.png").exists():
            self.skipTest("依赖上一个用例的产物")
        rc = TestMainGuards._run("--input", str(self.src), "--out", str(out),
                                 "--ffmpeg", FF)
        self.assertEqual(rc, 2, "已有帧且没加 --overwrite 时必须拒绝，防混批")


if __name__ == "__main__":
    unittest.main()
