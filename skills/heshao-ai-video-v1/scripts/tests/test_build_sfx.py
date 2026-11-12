"""build_sfx.py 的可复现性与高频闸门测试。

锁两件事：
1. 同 seed 必须逐字节相同，且每个材质一条独立随机流 —— SKILL.md §0 的「同配方号 = 同结果」
   和 render.mjs 的「旁白 + 事件表 → 钉帧混音」都依赖音效字节稳定。
2. 4.5kHz 以上占比 >0.30 的材质必须被点名（2026-11-05 实测 8 个材质超标，
   压在旁白下面被用户听成"杂音"；出表就要看得见，不要等反馈）。
"""
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(SKILL, "scripts", "build_sfx.py")

# 实测起音/整段 4.5k+ 占比 >0.3 的材质；加卡或调合成时若命中这些名字，必须仍然被点名
HOT = {"paper", "ratchet", "type", "snap", "shutter", "switch", "relay", "scan"}


def need_python():
    return True


def run(out_dir, seed):
    return subprocess.run([sys.executable, SCRIPT, "--out-dir", out_dir, "--seed", str(seed)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def digest(d):
    out = {}
    for f in sorted(glob.glob(os.path.join(d, "*.wav"))):
        with open(f, "rb") as fh:
            out[os.path.basename(f)] = hashlib.sha256(fh.read()).hexdigest()
    return out


@unittest.skipUnless(os.path.exists(SCRIPT), "缺 build_sfx.py")
class TestSfx(unittest.TestCase):
    def setUp(self):
        self.a = tempfile.mkdtemp(prefix="sfx-a-")
        self.b = tempfile.mkdtemp(prefix="sfx-b-")
        self.c = tempfile.mkdtemp(prefix="sfx-c-")

    def tearDown(self):
        for d in (self.a, self.b, self.c):
            shutil.rmtree(d, ignore_errors=True)

    def test_same_seed_is_byte_identical(self):
        r1, r2 = run(self.a, 20261104), run(self.b, 20261104)
        self.assertEqual(r1.returncode, 0, r1.stderr[-400:])
        self.assertEqual(r2.returncode, 0, r2.stderr[-400:])
        da, db = digest(self.a), digest(self.b)
        self.assertEqual(len(da), 13, "13 个材质都要产出")
        self.assertEqual(da, db, "同 seed 同参数必须逐字节相同")

    def test_different_seed_changes_noise_materials(self):
        run(self.a, 20261104)
        run(self.c, 20261105)
        da, dc = digest(self.a), digest(self.c)
        self.assertEqual(set(da), set(dc))
        diff = [k for k in da if da[k] != dc[k]]
        self.assertTrue(diff, "换 seed 必须至少改动一个噪声材质，否则 seed 没进熵源")

    def test_hot_materials_are_flagged(self):
        r = run(self.a, 20261104)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        line = [l for l in (r.stdout or "").splitlines() if "4.5k+ 占比 >" in l]
        self.assertTrue(line, "必须打印超标材质汇总行")
        named = set()
        for tok in line[0].split("：")[-1].split(","):
            tok = tok.strip()
            if tok:
                named.add(tok.split()[0])
        self.assertTrue(named & HOT, "已知高频材质必须被点名，例如 paper/ratchet/type")
        self.assertIn("母带", r.stdout, "必须给出可复制的母带链建议")

    def test_main_runs_once(self):
        """历史上文件末尾有过两个 __main__ 入口，导致 13 个材质被合成写盘两遍。"""
        with open(SCRIPT, encoding="utf-8") as fh:
            src = fh.read()
        self.assertEqual(src.count('if __name__ == "__main__"'), 1, "入口必须只有一个")
        r = run(self.a, 20261104)
        self.assertEqual(r.stdout.count("done →"), 1, "main 只能跑一遍")


if __name__ == "__main__":
    unittest.main(verbosity=2)
