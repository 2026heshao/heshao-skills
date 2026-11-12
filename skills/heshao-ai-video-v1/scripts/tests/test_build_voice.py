"""build_voice.py / tts_chain.py 的回归测试。

锁的是 SKILL.md Phase 4 里最容易静默坏掉的三条承诺：

1. 口播归一化表真的生效 —— 漏一条，`MCP` 就被读成英文整词，正片才发现，
   而时间轴已经钉死，重跑要重新对齐所有卡点。
2. `--from-cache` 只重润不改时长 —— 润音链改了但句子时间轴漂了，
   timeline.js / 字幕 / 音效落点会全部错位。
3. `polish_voice` 不改样本数 —— 这是上一条的前提。

不联网：TTS 调用点用 monkeypatch 挡住，只测路由与数学。
"""
import asyncio
import importlib.util
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)          # tts_chain 之间是平铺 import


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bv = _load("build_voice")
tc = _load("tts_chain")


class TestNormalize(unittest.TestCase):
    TABLE = {"说明": "注释键不参与替换", "MCP": "M C P", "DSH": "D S H", "sha256": "sha 二五六"}

    def test_each_key_is_applied(self):
        self.assertEqual(bv.apply_normalize("接入 MCP 与 DSH", self.TABLE), "接入 M C P 与 D S H")
        self.assertEqual(bv.apply_normalize("按 sha256 比对", self.TABLE), "按 sha 二五六 比对")

    def test_comment_key_and_non_string_are_ignored(self):
        self.assertEqual(bv.apply_normalize("说明：保持原样", self.TABLE), "说明：保持原样")
        self.assertEqual(bv.apply_normalize("x", {"n": 5, "说明": "y"}), "x")

    def test_display_is_untouched_by_normalize(self):
        """上屏文本与口播文本可以不同：display 必须原样保留缩写。"""
        lines = bv.to_lines({"slug": "u", "voice": "v", "lines": [
            {"display": "接入 MCP 与 DSH", "tts": "接入 M C P 与 D S H"}]})
        self.assertEqual(lines[0].display, "接入 MCP 与 DSH")
        self.assertEqual(lines[0].text, "接入 M C P 与 D S H")

    def test_empty_display_fails_fast(self):
        with self.assertRaises(SystemExit):
            bv.to_lines({"slug": "u", "voice": "v", "lines": [{"scene": "s00"}]})


class TestPolish(unittest.TestCase):
    def test_length_is_preserved(self):
        x = (np.random.default_rng(7).standard_normal(tc.SR * 2) * 0.1).astype(np.float32)
        y = tc.polish_voice(x)
        self.assertEqual(len(y), len(x), "润音链不许改样本数 —— 否则时间轴会漂")

    def test_true_peak_respects_ceiling(self):
        x = (np.random.default_rng(11).standard_normal(tc.SR) * 0.4).astype(np.float32)
        y = tc.polish_voice(x)
        self.assertLessEqual(tc.db(tc._true_peak(y)), tc.VOICE_TP_DB + 0.05)

    def test_rms_alignment_not_peak_alignment(self):
        """短句不该被顶到同一峰值：两条不同响度的输入，输出 RMS 应彼此靠近。"""
        rng = np.random.default_rng(3)
        loud = (rng.standard_normal(tc.SR) * 0.3).astype(np.float32)
        quiet = (rng.standard_normal(tc.SR // 2) * 0.01).astype(np.float32)
        r1 = float(np.sqrt(np.mean(tc.polish_voice(loud).astype(np.float64) ** 2)))
        r2 = float(np.sqrt(np.mean(tc.polish_voice(quiet).astype(np.float64) ** 2)))
        self.assertLess(abs(tc.db(r1) - tc.db(r2)), 3.0, "RMS 对齐后两者差距应 <3 dB")


class TestCacheRouting(unittest.TestCase):
    """--from-cache 必须走本地 mp3，一次都不联网。"""

    def test_use_cache_skips_edge_tts(self):
        import tempfile
        from pathlib import Path

        calls = {"net": 0, "cache": 0}
        orig_line, orig_cached = tc.synth_line, tc.synth_cached

        async def fake_line(line, voice, out_mp3):
            calls["net"] += 1
            raise AssertionError("use_cache=True 时不该联网")

        async def fake_cached(out_mp3):
            calls["cache"] += 1
            return (np.ones(int(tc.SR * 0.5), dtype=np.float32) * 0.05), None

        tc.synth_line, tc.synth_cached = fake_line, fake_cached
        try:
            with tempfile.TemporaryDirectory() as td:
                work = Path(td)
                lines = [tc.Line(text="甲", display="甲", rate="+0%", pitch="+0Hz",
                                 volume="+0%", gap_after=0.2),
                         tc.Line(text="乙", display="乙", rate="+0%", pitch="+0Hz",
                                 volume="+0%", gap_after=0.2)]
                for i in range(len(lines)):
                    (work / f"line_{i:03d}.mp3").write_bytes(b"ID3fake")
                track, meta = asyncio.run(tc.render_lines(lines, "v", work, lead=0.4,
                                                          tail=0.9, use_cache=True))
        finally:
            tc.synth_line, tc.synth_cached = orig_line, orig_cached

        self.assertEqual(calls["net"], 0, "缓存路径不能碰 TTS")
        self.assertEqual(calls["cache"], len(lines))
        self.assertAlmostEqual(meta[0]["start"], 0.4, places=4)
        self.assertGreater(meta[1]["start"], meta[0]["end"], "第二句必须排在第一句之后")
        self.assertEqual(len(track), int(round(track.size)), "track 是样本数组")


if __name__ == "__main__":
    unittest.main(verbosity=2)
