"""fetch_asset.py 的回归测试。

为什么这条重要：它是"素材进工程"的入口，也是唯一会**写盘 + 联网**的脚本。
两类错最贵：① 把网页当图片存下来（拿到 300KB 的 HTML 当成 jpg，渲染时才炸）；
② 同一素材被登记两次（跨镜复用），闸门事后才发现。
这里用本地 http 服务器测，不碰外网 —— 测的是逻辑，不是别人的站点可用性。
"""
import hashlib
import http.server
import importlib.util
import json
import os
import shutil
import threading
import unittest
from functools import partial
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location(
    "fetch_asset", os.path.join(SKILL, "scripts", "fetch_asset.py"))
fa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fa)

TMP = Path(HERE) / "_tmp_fetch"
SRV = None
PORT = 0

PNG = bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 200       # 假 PNG 头，够算哈希
HTML = b"<!doctype html><html><body>not an image</body></html>"


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def setUpModule():
    global SRV, PORT
    if TMP.exists():
        shutil.rmtree(TMP)
    (TMP / "www").mkdir(parents=True)
    (TMP / "www" / "pic.png").write_bytes(PNG)
    (TMP / "www" / "pic2.png").write_bytes(PNG)          # 同内容，用于重复检测
    (TMP / "www" / "page.jpg").write_bytes(HTML)         # 名字像图，内容却是 HTML
    handler = partial(Handler, directory=str(TMP / "www"))
    SRV = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    PORT = SRV.server_address[1]
    threading.Thread(target=SRV.serve_forever, daemon=True).start()


def tearDownModule():
    if SRV:
        SRV.shutdown()
        SRV.server_close()
    if TMP.exists():
        shutil.rmtree(TMP)


def url(name):
    return f"http://127.0.0.1:{PORT}/{name}"


def project(name):
    p = TMP / name
    (p / "assets").mkdir(parents=True, exist_ok=True)
    return p


class Cli:
    """跑 main() 并吞掉它 print 出来的噪声，只留退出码和异常。"""

    @staticmethod
    def run(*argv):
        old = __import__("sys").argv
        __import__("sys").argv = ["fetch_asset.py", *argv]
        try:
            return fa.main()
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 2
        finally:
            __import__("sys").argv = old


class TestDownload(unittest.TestCase):
    def test_downloads_and_registers(self):
        p = project("ok")
        rc = Cli.run("--url", url("pic.png"), "--out", "assets/img/a.png", "--id", "a",
                     "--license", "pexels-license", "--source-type", "stock",
                     "--source-url", "https://example.com/photo/1", "--root", str(p))
        self.assertEqual(rc, 0)
        dest = p / "assets" / "img" / "a.png"
        self.assertTrue(dest.is_file(), "文件要真的落盘")
        self.assertEqual(hashlib.sha256(dest.read_bytes()).hexdigest(), hashlib.sha256(PNG).hexdigest())
        m = json.loads((p / "assets" / "asset-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(m["assets"]), 1)
        e = m["assets"][0]
        self.assertEqual((e["id"], e["path"], e["kind"], e["role"]), ("a", "assets/img/a.png", "image", "space"))
        self.assertEqual(e["source"]["url"], "https://example.com/photo/1")
        self.assertEqual(len(e["sha256"]), 64)

    def test_html_page_is_rejected_not_saved_as_image(self):
        p = project("html")
        rc = Cli.run("--url", url("page.jpg"), "--out", "assets/img/x.jpg", "--id", "x",
                     "--license", "pexels-license", "--root", str(p))
        self.assertEqual(rc, 1, "把网页当图片存下来必须当场失败")
        self.assertFalse((p / "assets" / "img" / "x.jpg").exists())
        self.assertFalse((p / "assets" / "asset-manifest.json").exists(), "失败不许留下半条台账")

    def test_kind_mismatch_rejected(self):
        """声明 image 但内容其实是 png —— 不，这里声明 video 但给 png。"""
        p = project("kindmis")
        rc = Cli.run("--url", url("pic.png"), "--out", "assets/img/v.mp4", "--id", "v",
                     "--kind", "video", "--license", "pexels-license", "--root", str(p))
        self.assertEqual(rc, 1)
        self.assertFalse((p / "assets" / "img" / "v.mp4").exists())

    def test_no_license_refuses(self):
        p = project("nolic")
        rc = Cli.run("--url", url("pic.png"), "--out", "assets/img/y.png", "--root", str(p))
        self.assertEqual(rc, 2, "没许可不许进台账")

    def test_path_escape_refused(self):
        p = project("esc")
        rc = Cli.run("--url", url("pic.png"), "--out", "../outside.png", "--id", "o",
                     "--license", "pexels-license", "--root", str(p))
        self.assertEqual(rc, 2)
        self.assertFalse((TMP / "outside.png").exists())

    def test_dry_run_writes_nothing(self):
        p = project("dry")
        rc = Cli.run("--url", url("pic.png"), "--out", "assets/img/z.png", "--id", "z",
                     "--license", "pexels-license", "--root", str(p), "--dry-run")
        self.assertEqual(rc, 0)
        self.assertFalse((p / "assets" / "img" / "z.png").exists())
        self.assertFalse((p / "assets" / "asset-manifest.json").exists())

    def test_existing_file_refused_without_overwrite(self):
        p = project("exists")
        (p / "assets" / "img").mkdir(parents=True)
        (p / "assets" / "img" / "a.png").write_bytes(b"old")
        rc = Cli.run("--url", url("pic.png"), "--out", "assets/img/a.png", "--id", "a",
                     "--license", "pexels-license", "--root", str(p))
        self.assertEqual(rc, 2)
        self.assertEqual((p / "assets" / "img" / "a.png").read_bytes(), b"old", "不许静默覆盖")


class TestDedup(unittest.TestCase):
    def test_same_content_second_id_is_blocked(self):
        p = project("dup")
        args = ["--license", "pexels-license", "--root", str(p)]
        self.assertEqual(Cli.run("--url", url("pic.png"), "--out", "assets/img/a.png",
                                 "--id", "a", *args), 0)
        rc = Cli.run("--url", url("pic2.png"), "--out", "assets/img/b.png", "--id", "b", *args)
        self.assertEqual(rc, 1, "同内容换个 id 再下 = 跨镜复用，必须拦")
        m = json.loads((p / "assets" / "asset-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(m["assets"]), 1, "被拦下的那条不许进台账")

    def test_same_id_replaces_entry(self):
        p = project("replace")
        args = ["--license", "pexels-license", "--root", str(p)]
        Cli.run("--url", url("pic.png"), "--out", "assets/img/a.png", "--id", "a", *args)
        rc = Cli.run("--url", url("pic.png"), "--out", "assets/img/a.png", "--id", "a",
                     *args, "--overwrite")
        self.assertEqual(rc, 0)
        m = json.loads((p / "assets" / "asset-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(m["assets"]), 1, "同 id 应替换而不是追加")


class TestGateAfterFetch(unittest.TestCase):
    def test_attribution_required_without_text_fails_gate(self):
        """cc-by 要求署名。下载能成功，但闸门要拦，且要提示怎么修。"""
        p = project("attr")
        (p / "assets" / "asset-manifest.json").write_text(
            json.dumps({"projectId": "p", "commercial": False, "assets": []}), encoding="utf-8")
        rc = Cli.run("--url", url("pic.png"), "--out", "assets/img/c.png", "--id", "c",
                     "--license", "cc-by-4.0", "--root", str(p))
        self.assertEqual(rc, 1, "cc-by 缺 attributionText 应被闸门拦下")
        self.assertTrue((p / "assets" / "img" / "c.png").is_file(), "文件不该因为台账不合规被删")

    def test_clean_fetch_passes_gate(self):
        p = project("clean")
        rc = Cli.run("--url", url("pic.png"), "--out", "assets/img/d.png", "--id", "d",
                     "--license", "pexels-license", "--source-url", "https://example.com/p",
                     "--root", str(p))
        self.assertEqual(rc, 0, "来源+许可齐全时应一次通过")


class TestLocalFile(unittest.TestCase):
    """--file 模式：Pexels 停发新 key、Openverse 504 的时候，这是唯一不依赖 API 状态的路径。"""

    def test_copies_and_registers(self):
        p = project("file-ok")
        src = TMP / "www" / "pic.png"
        rc = Cli.run("--file", str(src), "--out", "assets/img/f.png", "--id", "f",
                     "--license", "pexels-license", "--source-type", "stock",
                     "--source-url", "https://www.pexels.com/photo/1", "--root", str(p))
        self.assertEqual(rc, 0)
        self.assertTrue((p / "assets" / "img" / "f.png").is_file())
        self.assertTrue(src.is_file(), "复制不是移动，原件必须留着")
        m = json.loads((p / "assets" / "asset-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["assets"][0]["path"], "assets/img/f.png")

    def test_html_disguised_file_rejected(self):
        p = project("file-html")
        src = TMP / "www" / "page.jpg"          # 内容是 HTML，扩展名是 jpg
        rc = Cli.run("--file", str(src), "--out", "assets/img/h.jpg", "--id", "h",
                     "--license", "pexels-license", "--root", str(p))
        self.assertEqual(rc, 1, "本地文件也要嗅探，别把网页存成 jpg")
        self.assertFalse((p / "assets" / "img" / "h.jpg").exists())

    def test_missing_file_returns_2(self):
        p = project("file-miss")
        rc = Cli.run("--file", str(TMP / "nope.png"), "--out", "assets/a.png", "--id", "a",
                     "--license", "pexels-license", "--root", str(p))
        self.assertEqual(rc, 2)

    def test_source_url_required_for_non_self(self):
        """本地文件最容易丢溯源。非自制但没 --source-url，闸门必须拦。"""
        p = project("file-nosrc")
        rc = Cli.run("--file", str(TMP / "www" / "pic.png"), "--out", "assets/img/g.png",
                     "--id", "g", "--license", "pexels-license", "--root", str(p))
        self.assertEqual(rc, 1, "缺来源页应被台账闸门拦下")
        m = json.loads((p / "assets" / "asset-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["assets"][0]["source"]["url"], "", "缺来源就该留空并被拦")

    def test_self_made_file_needs_no_source_url(self):
        p = project("file-self")
        rc = Cli.run("--file", str(TMP / "www" / "pic.png"), "--out", "assets/img/s.png",
                     "--id", "s", "--license", "own", "--source-type", "self", "--root", str(p))
        self.assertEqual(rc, 0, "自制素材不需要来源页")


class TestNoApiKey(unittest.TestCase):
    def test_pexels_without_key_explains_how_to_get_one(self):
        old = os.environ.pop("PEXELS_API_KEY", None)
        try:
            rc = Cli.run("--pexels-search", "warehouse", "--list-only")
        finally:
            if old is not None:
                os.environ["PEXELS_API_KEY"] = old
        self.assertEqual(rc, 2, "没 key 不许静默降级成爬网页")

    def test_bad_scheme_refused(self):
        rc = Cli.run("--url", "file:///etc/passwd", "--out", "assets/x", "--id", "x",
                     "--license", "cc0-1.0", "--root", str(TMP))
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
