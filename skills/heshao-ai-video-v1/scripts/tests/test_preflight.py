"""render.mjs --preflight 的工具链体检回归测试（标准库 unittest，无额外依赖）。

为什么值得测 —— 旁白/音效/QA 全在 Python 侧（numpy / scipy / Pillow / edge-tts），
以前缺包要跑到 Phase 4 才炸，而且是裸 ModuleNotFoundError。preflight 必须在开工前
把 Node 版本、Python 版本与这四个包一起报出来；缺任何一项都必须非零退出，
不能出现"嘴上报缺、身体放行"。

跑法：python -m unittest discover -s scripts/tests -p "test_*.py"
"""
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
RENDER = os.path.join(SKILL, "scripts", "render.mjs")
FIXTURE = os.path.join(HERE, "fixture")
# 单测可能清空 PATH 来模拟缺 Python，所以 node 必须先解析成绝对路径
NODE = shutil.which("node") or "node"


def run(args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([NODE, RENDER] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=e)


class TestPreflightReport(unittest.TestCase):
    def test_lists_node_python_and_python_deps(self):
        r = run(["--preflight", "--root", FIXTURE])
        out = r.stdout + r.stderr
        for key in ("Node", "浏览器", "ffmpeg", "Python", "numpy", "scipy", "Pillow", "edge-tts", "页面"):
            self.assertIn(key, out, f"preflight 没报 {key}")
        self.assertIn(r.returncode, (0, 1), "preflight 只能返回 0（齐备）或 1（不全）")
        if "✅ 工具链与页面都齐备" in out:
            self.assertEqual(r.returncode, 0)
        else:
            self.assertEqual(r.returncode, 1, "没齐备却返回 0，等于嘴上报缺身体放行")

    def test_missing_python_fails_loudly(self):
        # PATH 清空 + PROMO_PYTHON 指向不存在的路径：python / python3 / py 都解析不到。
        # 浏览器与 ffmpeg 走绝对路径候选，所以失败点只会是 Python。
        r = run(["--preflight"], env={
            "PATH": "",
            "PROMO_PYTHON": os.path.join(tempfile.gettempdir(), "no-such-python-xyz"),
        })
        out = r.stdout + r.stderr
        self.assertIn("Python  ❌", out)
        self.assertIn("只截帧不需要", out, "要说明只截图不需要 Python，别把人吓退")
        self.assertEqual(r.returncode, 1, "缺 Python 必须非零退出")

    def test_bogus_promo_python_falls_back(self):
        r = run(["--preflight", "--root", FIXTURE],
                env={"PROMO_PYTHON": os.path.join(tempfile.gettempdir(), "no-such-python-xyz")})
        out = r.stdout + r.stderr
        self.assertIn("preflight", out)
        self.assertIn(r.returncode, (0, 1), "PROMO_PYTHON 指错时应回退到 python/python3，不能直接崩")


if __name__ == "__main__":
    unittest.main(verbosity=2)
