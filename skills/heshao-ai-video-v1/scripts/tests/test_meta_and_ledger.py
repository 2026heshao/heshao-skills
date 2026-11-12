"""render.mjs 的 meta 指纹 + feedback.mjs 的 promoted 落地校验。

两条都是"防呆网本身"的用例：
- --encode-only / --audio-only 只读 meta.json，没有指纹就会出现「timeline.js 改了、
  事件表还是旧的」的静默错混音（字幕与音效落点全对不上新画面）。
- 经验记成 promoted 但 changes 是空的 / CHANGELOG 没有版本段落，等于宣布升级却没落地。
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
RENDER = os.path.join(SKILL, "scripts", "render.mjs")
FEEDBACK = os.path.join(SKILL, "scripts", "feedback.mjs")
FIXTURE_PAGE = os.path.join(HERE, "fixture", "preview.html")


class TestMetaFingerprint(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="promo-meta-")
        shutil.copy(FIXTURE_PAGE, os.path.join(self.root, "preview.html"))
        self.final = os.path.join(self.root, "out", "final")
        os.makedirs(self.final, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _meta(self, fingerprint):
        m = {"total": 1.0, "fps": 30, "audio": {"voice": "v.m4a", "sfxDir": "s/", "gains": {}},
             "sfx": [], "srcFingerprint": fingerprint}
        with open(os.path.join(self.final, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(m, fh)
        return m

    def run_mode(self, mode, extra=()):
        return subprocess.run(["node", RENDER, "--root", self.root, "--out-dir",
                               os.path.join(self.final), mode] + list(extra),
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_stale_meta_is_refused(self):
        self._meta("0" * 16)          # 与当前页面/素材必然不符
        r = self.run_mode("--audio-only")
        self.assertEqual(r.returncode, 1, "旧 meta 必须拒绝")
        out = r.stdout + r.stderr
        self.assertIn("输入指纹", out)
        self.assertIn("--force-stale-meta", out, "必须把出路说清楚")

    def test_force_stale_meta_bypasses_the_check(self):
        self._meta("0" * 16)
        r = self.run_mode("--audio-only", ["--force-stale-meta"])
        self.assertNotIn("会照旧事件表混音", r.stdout + r.stderr, "显式放行后不该再拦")

    def test_meta_only_writes_fingerprint(self):
        r = self.run_mode("--meta-only")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr[-400:])
        with open(os.path.join(self.final, "meta.json"), encoding="utf-8") as fh:
            m = json.load(fh)
        self.assertIn("srcFingerprint", m, "meta 必须带输入指纹，否则下次无从比对")
        self.assertEqual(len(m["srcFingerprint"]), 16)


class TestPromotedLedger(unittest.TestCase):
    """feedback.mjs：promoted 必须能证明"改了东西"。"""

    def _write_entry(self, name, data):
        exp = os.path.join(SKILL, "experiences")
        p = os.path.join(exp, name)
        body = "```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```\n\n正文略。\n"
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("# %s\n\n%s" % (name[:-3], body))
        return p

    def _reindex(self):
        # --validate 是从生成的 INDEX 枚举条目的，探针文件必须先重建索引才会被检查
        subprocess.run(["node", FEEDBACK, "--index"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")

    def _validate(self):
        self._reindex()
        return subprocess.run(["node", FEEDBACK, "--validate"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def test_promoted_without_changes_fails(self):
        p = self._write_entry("2099-01-01-probe-promoted.md", {
            "date": "2026-11-05", "project": "probe", "recipe": "manual", "format": "4:3",
            "duration": None, "score": None, "verdict": "unrated", "hardFail": False,
            "tags": [], "generalizable": True, "promotion": "promoted",
            "promotionBasis": "explicit-request", "summary": "探针", "userQuote": "以后都这样",
            "changes": [], "reverted": False})
        try:
            r = self._validate()
            self.assertIn("2099-01-01-probe-promoted.md", r.stdout + r.stderr)
            self.assertIn("changes", r.stdout + r.stderr)
            self.assertNotEqual(r.returncode, 0, "promoted 却没写 changes 必须变红")
        finally:
            os.unlink(p)
            self._reindex()

    def test_promoted_with_missing_path_fails(self):
        p = self._write_entry("2099-01-01-probe-path.md", {
            "date": "2026-11-05", "project": "probe", "recipe": "manual", "format": "4:3",
            "duration": None, "score": None, "verdict": "unrated", "hardFail": False,
            "tags": [], "generalizable": True, "promotion": "promoted",
            "promotionBasis": "explicit-request", "summary": "探针", "userQuote": "以后都这样",
            "changes": ["no-such-dir/ghost.md"], "reverted": False})
        try:
            r = self._validate()
            self.assertIn("不存在", r.stdout + r.stderr)
            self.assertNotEqual(r.returncode, 0)
        finally:
            os.unlink(p)
            self._reindex()

    def test_real_ledger_still_passes(self):
        r = self._validate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
