"""build_timeline.py 的时刻解析器回归测试（纯函数，不碰音频、不开浏览器）。

这里锁的是 SKILL.md §2 Phase 3/4 依赖的几条硬性质：
- 幕起点由 atLine + pad 推，第一幕恒为 0；
- 六种时刻表达式（line / line+end / sceneStart / global / total / plus）都按文档解析；
- 越界、反向、未知键必须当场 SystemExit —— 静默错一个时刻，正片所有卡点就全歪。
"""
import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))

spec = importlib.util.spec_from_file_location("build_timeline",
                                              os.path.join(SKILL, "scripts", "build_timeline.py"))
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

VT = {
    "slug": "unit", "duration": 10.0,
    "lines": [
        {"start": 0.50, "end": 2.00, "text": "甲"},
        {"start": 2.30, "end": 4.00, "text": "乙"},
        {"start": 4.50, "end": 6.00, "text": "丙"},
        {"start": 6.40, "end": 8.00, "text": "丁"},
    ],
}


def base_spec(**over):
    s = {
        "title": "unit", "fps": 30, "size": [1440, 1080],
        "voice": "v.m4a", "sfxDir": "s/", "gains": {"voice": 1.0, "sfx": 0.62},
        "tailPad": 1.5,
        "scenes": [
            {"id": "s00", "title": "一", "code": "A", "atLine": 0, "pad": 0,
             "cues": {"head": {"line": 0, "plus": 0.1}, "tail": {"line": 1, "end": True, "plus": 0.2}}},
            {"id": "s01", "title": "二", "code": "B", "atLine": 2, "pad": -0.3,
             "cues": {"here": {"sceneStart": True, "scene": "s01", "plus": 0.05},
                      "glob": {"global": 5.0}, "endref": {"total": True, "minus": 1.0}}},
        ],
        "captions": [{"line": 0, "startPlus": 0.1, "endPlus": 0.1, "text": "甲字", "kw": "甲"}],
        "sfx": [{"t": 0.02, "name": "snap", "g": 0.5},
                 {"at": {"line": 1, "plus": -0.06}, "name": "relay", "g": 0.4}],
        "pulse": None,
    }
    s.update(over)
    return s


class TestResolver(unittest.TestCase):
    def test_scene_starts_and_first_is_zero(self):
        promo = bt.build(base_spec(), VT)["promo"]
        self.assertEqual(promo["scenes"][0]["start"], 0.0)
        self.assertAlmostEqual(promo["scenes"][1]["start"], 4.50 - 0.30, places=2)
        self.assertEqual(promo["scenes"][0]["end"], promo["scenes"][1]["start"], "幕必须首尾相接")
        self.assertEqual(promo["scenes"][1]["end"], promo["dur"], "最后一幕收到成片末尾")

    def test_six_time_expressions(self):
        cues = bt.build(base_spec(), VT)["promo"]["scenes"]
        self.assertAlmostEqual(cues[0]["cues"]["head"], 0.60, places=2)      # line + plus
        self.assertAlmostEqual(cues[0]["cues"]["tail"], 4.20, places=2)      # line end + plus
        self.assertAlmostEqual(cues[1]["cues"]["here"], 4.25, places=2)      # sceneStart + plus
        self.assertAlmostEqual(cues[1]["cues"]["glob"], 5.00, places=2)      # global
        self.assertAlmostEqual(cues[1]["cues"]["endref"], round(promo_dur() - 1.0, 2), places=2)

    def test_total_and_duration(self):
        built = bt.build(base_spec(), VT)
        # total = max(voice+0.55, last_end + tailPad)
        self.assertAlmostEqual(built["total"], max(10.55, 8.00 + 1.5), places=2)

    def test_sfx_sorted_and_frame_quantizable(self):
        promo = bt.build(base_spec(), VT)["promo"]
        ts = [e["t"] for e in promo["sfx"]]
        self.assertEqual(ts, sorted(ts), "sfx 必须按时刻排序")
        for e in promo["sfx"]:
            self.assertEqual(round(e["t"], 3), e["t"], "时刻保留 3 位小数")
            # timeline.js 里存的是未量化时刻；预览与 ffmpeg 混音各自用 ceil(t*fps)/fps 量化，
            # 所以契约是「量化后必须落在帧边界且两边一致」，不是「存进来就已量化」。
            q = bt.quantize(e["t"], 30, "ceil")
            self.assertAlmostEqual(q * 30 % 1, 0.0, places=6, msg="量化后必须落在帧边界")
            self.assertGreaterEqual(q, e["t"] - 1e-9, "量化只能往后，不能提前抢拍")


class TestFailFast(unittest.TestCase):
    """这四类必须报错，不能静默出个错时刻。"""

    def test_atline_out_of_range(self):
        s = base_spec()
        s["scenes"][1]["atLine"] = 99
        with self.assertRaises(SystemExit):
            bt.build(s, VT)

    def test_caption_line_out_of_range(self):
        s = base_spec()
        s["captions"] = [{"line": 42, "text": "x"}]
        with self.assertRaises(SystemExit):
            bt.build(s, VT)

    def test_reversed_caption_window(self):
        s = base_spec()
        s["captions"] = [{"line": 1, "startPlus": 0.2, "endPlus": -3.0, "text": "x"}]
        with self.assertRaises(SystemExit):
            bt.build(s, VT)

    def test_sfx_beyond_total(self):
        s = base_spec()
        s["sfx"] = [{"t": 999.0, "name": "snap"}]
        with self.assertRaises(SystemExit):
            bt.build(s, VT)

    def test_unknown_time_key(self):
        s = base_spec()
        s["scenes"][0]["cues"] = {"bad": {"minute": 3}}
        with self.assertRaises(SystemExit):
            bt.build(s, VT)

    def test_scenestart_without_scene_name(self):
        s = base_spec()
        s["scenes"][0]["cues"] = {"bad": {"sceneStart": True, "scene": "nope"}}
        with self.assertRaises(SystemExit):
            bt.build(s, VT)


def promo_dur():
    return bt.build(base_spec(), VT)["total"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
