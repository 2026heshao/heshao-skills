"""qa_mp4.py 自身的回归测试。

为什么这条最重要：逐帧回捞是唯一抓到「落版被压灰 20%」的工具。它自己一旦静默失效
（尺寸不同时只比左上角交集、空帧判据被平均亮度带偏、偏移测不出已知位移），
报告就会一路绿灯，而 SKILL.md §5 正是靠它兜底。安全网必须能被证明"能变红"。
"""
import importlib.util
import os
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location("qa_mp4", os.path.join(SKILL, "scripts", "qa_mp4.py"))
qa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qa)

TMP = Path(HERE) / "_tmp_qa"


def mkimg(name, arr):
    TMP.mkdir(parents=True, exist_ok=True)
    p = TMP / name
    Image.fromarray(arr.astype("uint8"), mode="L").save(p)
    return p


class TestDiff(unittest.TestCase):
    def test_identical_frames_are_zero(self):
        a = np.full((60, 80), 128, dtype=np.uint8)
        mean, large = qa.diff(mkimg("a.png", a), mkimg("b.png", a))
        self.assertEqual((mean, large), (0.0, 0.0))

    def test_known_block_difference_is_detected(self):
        base = np.full((100, 100), 90, dtype=np.uint8)
        other = base.copy()
        other[0:50, 0:100] = 200          # 上半屏差 110 灰阶 = 50% 面积
        mean, large = qa.diff(mkimg("c.png", base), mkimg("d.png", other))
        self.assertAlmostEqual(mean, 55.0, delta=1.0, msg="均值应≈ 0.5×110")
        self.assertAlmostEqual(large, 0.5, delta=0.01, msg="大幅差占比应≈ 50%")

    def test_size_mismatch_raises_instead_of_silent_crop(self):
        p1 = mkimg("e.png", np.full((100, 100), 90, dtype=np.uint8))
        p2 = mkimg("f.png", np.full((100, 120), 90, dtype=np.uint8))
        with self.assertRaises(ValueError):
            qa.diff(p1, p2)


class TestBlankDetection(unittest.TestCase):
    def test_dark_but_structured_is_not_blank(self):
        """实验台/蓝图/塔台都是 #05–#08 暗底：判据必须看结构，不能看平均亮度。"""
        x = np.full((120, 160), 6, dtype=np.uint8)
        x[40:70, 60:100] = 235           # 暗底上一小块亮主体（贴近真实暗底场景）
        p = mkimg("g.png", x)
        mean, std, bright = qa.frame_content(p)
        self.assertLess(mean, 40, "均值确实很低（暗底为主）")
        self.assertGreater(std, 6.0)
        self.assertFalse(qa.frame_is_blank(p))

    def test_pure_black_is_blank(self):
        self.assertTrue(qa.frame_is_blank(mkimg("h.png", np.zeros((120, 160), dtype=np.uint8))))

    def test_flat_uniform_bright_is_flagged(self):
        """整幅一个色号 = 没有内容；当前判据靠 std，这里锁住现有语义。"""
        p = mkimg("i.png", np.full((120, 160), 200, dtype=np.uint8))
        _mean, std, _bright = qa.frame_content(p)
        self.assertLess(std, 6.0)
        self.assertTrue(qa.frame_is_blank(p))


class TestEnvelopeOffset(unittest.TestCase):
    def _env(self, spike_at, n=400):
        e = np.ones(n) * 0.2
        e[spike_at:spike_at + 6] = 3.0
        e[spike_at + 60:spike_at + 66] = 2.2
        return e

    def test_zero_offset(self):
        e = self._env(120)
        self.assertAlmostEqual(qa.envelope_offset(e, e), 0.0, places=6)

    def test_known_shift_is_measured(self):
        a, b = self._env(120), self._env(123)      # b 比 a 晚 3 帧 = 30ms
        self.assertAlmostEqual(abs(qa.envelope_offset(a, b)), 30.0, places=6)

    def test_mismatched_lengths_raise(self):
        with self.assertRaises(ValueError):
            qa.envelope_offset(self._env(120), self._env(120, n=300))


if __name__ == "__main__":
    unittest.main(verbosity=2)
