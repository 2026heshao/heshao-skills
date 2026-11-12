"""两个新闸门的回归测试：舞台层纪律检查器 + 节奏报告。

这两个脚本本身是"防呆网"，网破了就没人知道 —— 所以必须有用例证明它们能变红。
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
CHECKER = os.path.join(SKILL, "scripts", "check_engine_discipline.mjs")
PACING = os.path.join(SKILL, "scripts", "pacing_report.py")
FIX = os.path.join(HERE, "fixtures-discipline")


def load_py(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEngineDiscipline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(CHECKER):
            raise unittest.SkipTest("缺 check_engine_discipline.mjs")

    def run_ck(self, engine):
        return subprocess.run(["node", CHECKER, "--engine", engine],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_good_engine_passes(self):
        r = self.run_ck(os.path.join(FIX, "good_engine.js"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bad_engine_fails_and_names_dim(self):
        """坏例复刻 2026-11-05 的落版压灰 bug：检查器必须点名 dim。"""
        r = self.run_ck(os.path.join(FIX, "bad_engine.js"))
        self.assertEqual(r.returncode, 1, "漏复位 + 漏签名必须变红")
        out = r.stdout + r.stderr
        self.assertIn("dim", out)
        self.assertIn("没复位", out)
        self.assertIn("signature", out)

    def test_missing_engine_exits_2(self):
        r = self.run_ck(os.path.join(FIX, "does_not_exist.js"))
        self.assertEqual(r.returncode, 2)

    def test_no_args_exits_2(self):
        r = subprocess.run(["node", CHECKER], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


def make_timeline(per_scene=3, line_len=2.0, gap=0.2, lead=0.2, open_lead=0.5,
                  tail=1.0, dur=None):
    """按节奏参数生成一条**自洽且合规**的时间轴，再让用例单项破坏。

    以前这里手写 15 个数字，结果 fixture 自己就不合规（句间 0.50、幕首 lead 0.9、
    占时比 75%），三条用例被误判成闸门 bug。参数化生成才能保证"单因失败"是真的单因。
    """
    n = per_scene * 5
    lines = []
    t = open_lead
    for _ in range(n):
        lines.append({"start": round(t, 4), "end": round(t + line_len, 4)})
        t += line_len + gap
    scenes = []
    for i in range(5):
        seg = lines[i * per_scene:(i + 1) * per_scene]
        a = round(seg[0]["start"] - lead, 4)
        b = round(seg[-1]["end"] + gap, 4)
        scenes.append({"id": "s0%d" % i, "title": ["一", "二", "三", "四", "落版"][i],
                       "start": max(0.0, a), "end": b})
    total = dur if dur is not None else round(scenes[-1]["end"] + tail, 4)
    scenes[-1]["end"] = total
    return {"dur": total, "fps": 30, "lines": lines, "scenes": scenes}


class TestPacingGate(unittest.TestCase):
    def run_pr(self, tl, extra=()):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump({"promo": tl}, fh, ensure_ascii=False)
            path = fh.name
        try:
            return subprocess.run([sys.executable, PACING, "--timeline", path] + list(extra),
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
        finally:
            os.unlink(path)

    def test_compliant_timeline_passes(self):
        r = self.run_pr(make_timeline())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("✅", r.stdout)

    def _tail_case(self):
        """单因失败：只把片尾空场拉到 2.5s，其余指标保持合规。"""
        return make_timeline(tail=2.5)

    def test_long_tail_air_fails(self):
        r = self.run_pr(self._tail_case())
        self.assertEqual(r.returncode, 1)
        self.assertIn("片尾空场", r.stdout + r.stderr)

    def test_wide_line_gap_fails(self):
        tl = make_timeline()
        tl["lines"][1]["start"] = 6.0          # 句间空白 3.5s
        r = self.run_pr(tl)
        self.assertEqual(r.returncode, 1)
        self.assertIn("句间空白", r.stdout + r.stderr)

    def test_low_speech_ratio_fails(self):
        tl = make_timeline()
        for l in tl["lines"]:
            l["end"] = l["start"] + 0.3        # 旁白只占很小比例
        r = self.run_pr(tl)
        self.assertEqual(r.returncode, 1)
        self.assertIn("旁白占时比", r.stdout + r.stderr)

    def test_thresholds_are_overridable(self):
        r = self.run_pr(self._tail_case(), ["--tail-air", "3.0"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("✅", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
