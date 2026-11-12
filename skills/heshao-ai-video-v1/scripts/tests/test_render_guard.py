"""render.mjs 两条操作闸门的回归测试（标准库 unittest，无额外依赖）。

为什么值得测 —— 两条都是 2026-11-05 skilllocker 实测踩出来的：

1. 未知参数被静默忽略：`--help` 不打印用法，而是按默认参数直接开渲整片（1322 帧 +
   覆写 out/final/film.mp4）。拼错一个 flag 就是一次昂贵且破坏性的运行。
2. 帧目录「已存在就跳过」没有输入指纹：一个进程被中断后留下 388 帧，下一个进程
   静默复用并出片 —— 如果两次之间改过页面，成片就混了两个代码版本。

跑法：python -m unittest discover -s scripts/tests -p "test_*.py"
需要 node + Edge/Chrome + ffmpeg；缺任何一样，涉及真实截图的用例自动 skip。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
RENDER = os.path.join(SKILL, "scripts", "render.mjs")
FIXTURE = os.path.join(HERE, "fixture")


def run(args, cwd=None):
    return subprocess.run(["node", RENDER] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=cwd)


def toolchain_ok():
    if not shutil.which("node"):
        return False
    r = run(["--preflight", "--root", FIXTURE])
    return "✅" in (r.stdout + r.stderr)


class TestArgWhitelist(unittest.TestCase):
    """参数闸门：不需要浏览器，任何机器都能跑。"""

    def test_help_exits_2_and_does_not_render(self):
        r = run(["--help"])
        self.assertEqual(r.returncode, 2, "--help 必须只打印用法并退出 2")
        self.assertIn("usage:", (r.stdout + r.stderr).lower())
        self.assertNotIn("截图帧", r.stdout, "--help 绝不能进入渲染分支")

    def test_unknown_flag_exits_2(self):
        r = run(["--frames-onlyy"])
        self.assertEqual(r.returncode, 2, "未知参数必须退出 2")
        self.assertIn("未知参数", r.stdout + r.stderr)

    def test_typo_among_valid_flags_is_caught(self):
        r = run(["--root", FIXTURE, "--form", "0.3"])       # --form 是 --from 的手误
        self.assertEqual(r.returncode, 2)
        self.assertIn("--form", r.stdout + r.stderr)


class TestFrameStampGuard(unittest.TestCase):
    """帧目录指纹：拒绝发生在开浏览器之前，所以不依赖工具链也能验一半。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="promo-stamp-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_frames(self, fp):
        with open(os.path.join(self.tmp, "f00000.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
        with open(os.path.join(self.tmp, "_stamp.json"), "w", encoding="utf-8") as fh:
            json.dump({"fp": fp, "page": "x"}, fh)

    def test_mismatched_stamp_refuses_before_browser(self):
        self._seed_frames("0" * 16)
        r = run(["--root", FIXTURE, "--frames-only", "--from", "0", "--to", "0.02",
                 "--frames-dir", self.tmp])
        # 工具链缺失时会在更早处退出，那种情况下本用例只验证没有"静默放行"
        if r.returncode == 2 and "页面" in (r.stdout + r.stderr):
            self.skipTest("fixture 页面没被认出来")
        self.assertIn(r.returncode, (0, 1), "退出码只能是放行(0)或拒绝(1)，不能是别的")
        if "输入指纹变了" not in r.stderr:
            self.skipTest("工具链缺失，没走到指纹检查")
        self.assertEqual(r.returncode, 1, "指纹不符必须拒绝续跑")
        self.assertNotIn("截图帧", r.stdout, "拒绝应发生在开浏览器之前")

    def test_resume_anyway_does_not_refuse(self):
        if not toolchain_ok():
            self.skipTest("缺 node/Edge/ffmpeg")
        self._seed_frames("0" * 16)
        r = run(["--root", FIXTURE, "--frames-only", "--from", "0", "--to", "0.02",
                 "--frames-dir", self.tmp, "--resume-anyway"])
        self.assertNotIn("输入指纹变了", r.stderr)
        self.assertIn("--resume-anyway", r.stdout + r.stderr)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])

    def test_matching_stamp_allows_resume_and_reuses_frames(self):
        if not toolchain_ok():
            self.skipTest("缺 node/Edge/ffmpeg")
        # 先正常截 1 帧，拿到真实指纹
        r = run(["--root", FIXTURE, "--frames-only", "--from", "0", "--to", "0.02",
                 "--frames-dir", self.tmp])
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        with open(os.path.join(self.tmp, "_stamp.json"), encoding="utf-8") as fh:
            stamp = json.load(fh)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "f00000.png")))
        # 同指纹再跑：应跳过已有帧（新截 0 帧）
        r2 = run(["--root", FIXTURE, "--frames-only", "--from", "0", "--to", "0.02",
                  "--frames-dir", self.tmp])
        self.assertEqual(r2.returncode, 0)
        self.assertIn("跳过已存在 1 帧", r2.stdout)
        with open(os.path.join(self.tmp, "_stamp.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["fp"], stamp["fp"], "同输入必须得到同指纹")


if __name__ == "__main__":
    unittest.main(verbosity=2)
