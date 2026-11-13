"""check_assets.py 自身的回归测试。

为什么这条重要：素材台账是唯一拦住「影视截图当素材」「图上有人脸没授权」
「同一张底图跨镜复用」的闸门。它一旦静默通过，SKILL.md §5 的 QA 清单会一路绿灯，
而风险已经进了成片。所以这里每一个用例都要求它**能变红** —— 只测"正常样本能过"
等于没测。
"""
import importlib.util
import json
import os
import shutil
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location(
    "check_assets", os.path.join(SKILL, "scripts", "check_assets.py"))
ca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ca)

TMP = Path(HERE) / "_tmp_assets"


def setUpModule():
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)


def tearDownModule():
    if TMP.exists():
        shutil.rmtree(TMP)


def put(name, data=b"fake-bytes"):
    p = TMP / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return name


def asset(**kw):
    a = {
        "id": "img-a",
        "path": put("img-a.jpg", b"aaa"),
        "kind": "image",
        "role": "space",
        "source": {"type": "stock", "url": "https://example.com/p/1", "retrievedAt": "2026-11-13"},
        "license": {"id": "pexels-license", "commercialUse": True, "attributionRequired": False},
        "sha256": "",
    }
    a.update(kw)
    return a


def run(assets, **kw):
    data = {"schemaVersion": 1, "projectId": "t", "assets": assets}
    issues, stamped = ca.check_manifest(data, str(TMP), **kw)
    return {i.code for i in issues}, {i.code for i in issues if i.level == "FAIL"}, stamped


class TestClean(unittest.TestCase):
    def test_good_asset_passes_modulo_hash(self):
        codes, fails, stamped = run([asset()])
        self.assertEqual(fails - {"E020"}, set(), f"除缺 hash 外不该有 FAIL，实际 {fails}")
        self.assertIn("E020", fails, "缺 sha256 必须报出来，不能默认放行")
        self.assertIn("img-a", stamped, "缺 hash 时应提供回填值")

    def test_empty_assets_is_warn_not_fail(self):
        codes, fails, _ = run([])
        self.assertEqual(fails, set())
        self.assertIn("W001", codes)

    def test_self_made_needs_no_url(self):
        a = asset(source={"type": "self", "retrievedAt": "2026-11-13"})
        _, fails, _ = run([a])
        self.assertNotIn("E012", fails, "自制素材不该被要求 url")

    def test_hash_matches_after_stamp(self):
        a = asset()
        real = ca.sha256_of(str(TMP / a["path"]))
        a["sha256"] = real
        codes, fails, _ = run([a])
        self.assertEqual(fails, set())


class TestSourcing(unittest.TestCase):
    def test_missing_url_fails(self):
        a = asset(source={"type": "stock", "retrievedAt": "2026-11-13"})
        _, fails, _ = run([a])
        self.assertIn("E012", fails)

    def test_bad_date_fails(self):
        a = asset(source={"type": "stock", "url": "https://x/1", "retrievedAt": "11/13/2026"})
        _, fails, _ = run([a])
        self.assertIn("E013", fails)

    def test_bad_source_type_fails(self):
        a = asset(source={"type": "screenshot", "url": "https://x/1", "retrievedAt": "2026-11-13"})
        _, fails, _ = run([a])
        self.assertIn("E011", fails)

    def test_missing_file_fails(self):
        _, fails, _ = run([asset(path="nope/ghost.jpg")])
        self.assertIn("E008", fails)


class TestLicense(unittest.TestCase):
    def test_unknown_license_fails(self):
        a = asset(license={"id": "cc-by-nc-4.0", "commercialUse": True, "attributionRequired": True,
                           "attributionText": "x"})
        _, fails, _ = run([a])
        self.assertIn("E015", fails, "cc-by-nc 不许静默放行")

    def test_allow_license_escape_hatch(self):
        a = asset(license={"id": "rights-managed", "commercialUse": True, "attributionRequired": False})
        _, fails, _ = run([a], allow_license=("rights-managed",))
        self.assertNotIn("E015", fails)

    def test_commercial_project_rejects_noncommercial_asset(self):
        a = asset(license={"id": "pexels-license", "commercialUse": False, "attributionRequired": False})
        _, fails, _ = run([a], commercial=True)
        self.assertIn("E018", fails)

    def test_cc_by_requires_attribution_text(self):
        a = asset(license={"id": "cc-by-4.0", "commercialUse": True, "attributionRequired": True})
        _, fails, _ = run([a])
        self.assertIn("E017", fails)

    def test_attribution_flag_needs_text(self):
        a = asset(license={"id": "pexels-license", "commercialUse": True,
                           "attributionRequired": True, "attributionText": "  "})
        _, fails, _ = run([a])
        self.assertIn("E019", fails)

    def test_provider_terms_not_blocked_by_commercial_flag(self):
        a = asset(source={"type": "ai", "url": "internal:imagegen", "retrievedAt": "2026-11-13"},
                  license={"id": "provider-terms", "commercialUse": True, "attributionRequired": False})
        _, fails, _ = run([a], commercial=True)
        self.assertNotIn("E016", fails, "AI 生成物按 provider 条款，不在白名单层拦")


class TestIntegrity(unittest.TestCase):
    def test_hash_mismatch_fails(self):
        a = asset(sha256="0" * 64)
        _, fails, _ = run([a])
        self.assertIn("E021", fails)

    def test_duplicate_content_fails(self):
        same = put("dup.jpg", b"same")
        a1 = asset(id="a1", path=same)
        a2 = asset(id="a2", path=same)
        h = ca.sha256_of(str(TMP / same))
        a1["sha256"] = a2["sha256"] = h
        _, fails, _ = run([a1, a2])
        self.assertIn("E022", fails, "同一张图跨镜复用必须被抓到")

    def test_allow_reuse_escapes(self):
        same = put("dup2.jpg", b"same2")
        h = ca.sha256_of(str(TMP / same))
        a1, a2 = asset(id="b1", path=same, sha256=h), asset(id="b2", path=same, sha256=h)
        _, fails, _ = run([a1, a2], allow_reuse=True)
        self.assertNotIn("E022", fails)

    def test_duplicate_id_fails(self):
        _, fails, _ = run([asset(), asset(path=put("other.jpg", b"bbb"))])
        self.assertIn("E004", fails)

    def test_dangling_derived_from_fails(self):
        _, fails, _ = run([asset(derivedFrom="ghost-raw")])
        self.assertIn("E024", fails)

    def test_self_reference_fails(self):
        _, fails, _ = run([asset(derivedFrom="img-a")])
        self.assertIn("E023", fails)


class TestShapes(unittest.TestCase):
    def test_sequence_needs_png_frames(self):
        d = TMP / "seq-empty"
        d.mkdir(exist_ok=True)
        (d / "readme.txt").write_text("x", encoding="utf-8")
        _, fails, _ = run([asset(kind="sequence", role="space", path="seq-empty")])
        self.assertIn("E010", fails)

    def test_sequence_with_frames_ok(self):
        d = TMP / "seq-ok"
        d.mkdir(exist_ok=True)
        for i in range(1, 4):
            (d / f"f_{i:04d}.png").write_bytes(bytes([i]))
        a = asset(kind="sequence", path="seq-ok", sha256=ca.sha256_of(str(d)))
        _, fails, _ = run([a])
        self.assertEqual(fails, set())

    def test_frame_count_must_match_directory(self):
        """frameCount 是重抽后最容易过期的字段。序列变了 manifest 没变，画面只会卡住不报错。"""
        d = TMP / "seq-count"
        d.mkdir(exist_ok=True)
        for i in range(1, 4):
            (d / f"f_{i:04d}.png").write_bytes(bytes([i]))
        h = ca.sha256_of(str(d))
        a = asset(kind="sequence", path="seq-count", sha256=h, frameCount=99)
        _, fails, _ = run([a])
        self.assertIn("E025", fails)
        a_ok = asset(kind="sequence", path="seq-count", sha256=h, frameCount=3)
        _, fails_ok, _ = run([a_ok])
        self.assertNotIn("E025", fails_ok, "3 帧对 3 帧不该报")

    def test_frame_count_non_integer_fails(self):
        d = TMP / "seq-badfc"
        d.mkdir(exist_ok=True)
        (d / "f_0001.png").write_bytes(b"1")
        a = asset(kind="sequence", path="seq-badfc", sha256=ca.sha256_of(str(d)),
                  frameCount="sixty")
        _, fails, _ = run([a])
        self.assertIn("E025", fails)

    def test_video_warns_to_extract_frames(self):
        codes, fails, _ = run([asset(kind="video", path=put("clip.mp4", b"v"))])
        self.assertIn("W002", codes)
        self.assertEqual(fails - {"E020"}, set(), "video 除缺 hash 外不该 FAIL，只是提醒抽帧")

    def test_bad_kind_and_role_fail(self):
        _, fails, _ = run([asset(kind="sprite", role="mood")])
        self.assertTrue({"E005", "E006"} <= fails)

    def test_assets_not_list(self):
        data = {"assets": {"a": 1}}
        issues, _ = ca.check_manifest(data, str(TMP))
        self.assertIn("E001", {i.code for i in issues})


class TestCli(unittest.TestCase):
    def _write(self, payload, name="manifest.json"):
        p = TMP / name
        p.write_text(json.dumps(payload), encoding="utf-8")
        return p

    def test_stamp_backfills_and_recheck_clean(self):
        p = self._write({"projectId": "t", "assets": [asset()]})
        sys_argv = __import__("sys").argv
        __import__("sys").argv = ["check_assets.py", "--manifest", str(p), "--stamp"]
        try:
            rc = ca.main()
        finally:
            __import__("sys").argv = sys_argv
        self.assertEqual(rc, 0, "--stamp 后应通过")
        saved = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["assets"][0]["sha256"]), 64)

    def test_assets_layout_resolves_from_project_root(self):
        """标准布局 <project>/assets/asset-manifest.json 下，path 要相对 <project> 解析。

        回归用例：早期把 root 当成 manifest 所在目录，这种布局会全员误报 E008。
        """
        proj = TMP / "proj"
        (proj / "assets" / "img").mkdir(parents=True, exist_ok=True)
        (proj / "assets" / "img" / "x.jpg").write_bytes(b"xxx")
        payload = {"projectId": "p", "assets": [asset(id="x", path="assets/img/x.jpg")]}
        p = proj / "assets" / "asset-manifest.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        sys_argv = __import__("sys").argv
        __import__("sys").argv = ["check_assets.py", "--manifest", str(p), "--stamp"]
        try:
            rc = ca.main()
        finally:
            __import__("sys").argv = sys_argv
        self.assertEqual(rc, 0, "标准布局下应能解析到资产，不该报 E008")

    def test_missing_manifest_returns_2(self):
        sys_argv = __import__("sys").argv
        __import__("sys").argv = ["check_assets.py", "--manifest", str(TMP / "ghost.json")]
        try:
            rc = ca.main()
        finally:
            __import__("sys").argv = sys_argv
        self.assertEqual(rc, 2)

    def test_failing_manifest_returns_1(self):
        p = self._write({"projectId": "t",
                         "assets": [asset(license={"id": "cc-by-nc-4.0", "commercialUse": True,
                                                   "attributionRequired": False})]}, "bad.json")
        sys_argv = __import__("sys").argv
        __import__("sys").argv = ["check_assets.py", "--manifest", str(p), "--stamp"]
        try:
            rc = ca.main()
        finally:
            __import__("sys").argv = sys_argv
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
