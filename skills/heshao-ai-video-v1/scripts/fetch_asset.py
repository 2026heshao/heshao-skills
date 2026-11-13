#!/usr/bin/env python3
"""按明确来源下载一条素材，并自动登记进 asset-manifest.json。

为什么只做「按 URL 下」而不做「爬站搜索」：
Pexels ToS 明确禁止 bulk / large-scale / systematic copying 与自动化数据采集；Unsplash API
强制热链接、不得转存（video 渲染必须落地成文件，正撞这条）。写个爬图库网页的脚本等于把
违规路径固化进 skill。所以分工是：
  · 找素材（模糊搜索、判断贴不贴产品）→ 会话里由 agent 联网搜，人确认
  · 拿到明确 URL 之后 → 本脚本下载 + 算哈希 + 登记 + 过闸门
  · 有 Pexels key 时可用 --pexels-search 走官方 API 检索（合规路径），不用爬

用法：
    # 单条：给直链 + 来源页 + 许可
    python scripts/fetch_asset.py --url https://images.pexels.com/photos/1/x.jpg \
        --out assets/img/hall-desk.jpg --id hall-desk --role space \
        --license pexels-license --source-type stock \
        --source-url https://www.pexels.com/photo/xxx --attribution "Photo by X on Pexels"

    # 只看会写什么，不下载
    python scripts/fetch_asset.py ... --dry-run

    # Pexels 官方 API 检索候选（需 PEXELS_API_KEY），只列不下
    python scripts/fetch_asset.py --pexels-search "warehouse night" --list-only

    # 检索后按 id 下载其中一张
    python scripts/fetch_asset.py --pexels-id 12345678 --out assets/img/hall.jpg --id hall --role space
退出码：0 成功；1 下载/登记失败；2 参数错误。
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MAX_MB = 200
UA = "heshao-ai-video-skill/2.8 (+https://github.com/; asset-fetch)"
PEXELS_SEARCH = "https://api.pexels.com/v1/search"
PEXELS_PHOTO = "https://api.pexels.com/v1/photos/"


def die(msg, code=2):
    print("❌ " + msg, file=sys.stderr)
    sys.exit(code)


def http_get(url, headers=None, max_mb=MAX_MB):
    """只允许 http/https；限制体积；UA 不能省（不少 CDN 会拒默认 urllib UA）。"""
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https"):
        die(f"只接受 http/https，收到 {p.scheme!r}：{url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            ctype = r.headers.get("Content-Type", "")
            if "text/html" in ctype:
                die(f"这是网页不是素材文件（Content-Type: {ctype}）。\n"
                    f"   要的是图片/视频直链，通常以 .jpg/.png/.mp4 结尾。")
            buf, got = [], 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                got += len(chunk)
                if got > max_mb * 1024 * 1024:
                    die(f"文件超过 {max_mb}MB 上限，拒绝下载（避免误拉整片）")
                buf.append(chunk)
            return b"".join(buf), ctype
    except urllib.error.HTTPError as e:
        die(f"HTTP {e.code}：{url}")
    except urllib.error.URLError as e:
        die(f"网络不可达：{e.reason}（{url}）")


def safe_rel(path, root):
    """跨盘符时 os.path.relpath 抛 ValueError（Windows 上 C: 与 D: 之间）。

    与 frames_from_video.safe_rel 同实现 —— 这两个脚本各自独立可跑，不为 8 行函数
    引入共享模块；改动时两边一起改。今天第三次撞这个坑（check_assets 的 root 推导、
    frames_from_video 的工程片段、这里），根因都是一句话：临时素材常在 C:，工程在 D:。
    """
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:
        return path.replace(os.sep, "/")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sniff(body):
    """按 magic bytes 判容器，不信 Content-Type。

    真实踩过的坑：CDN 防盗链页、登录墙、404 页都可能带 image/jpeg 头。
    只信头就会把 300KB 的 HTML 存成 .jpg，一直等到渲染才炸。
    """
    if body[:8] == b"\x89PNG\r\n\x1a\n":
        return "image"
    if body[:3] == b"\xff\xd8\xff":
        return "image"
    if body[:6] in (b"GIF87a", b"GIF89a"):
        return "image"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image"
    if body[4:8] == b"ftyp":                       # mp4 / mov
        return "video"
    if body[:4] == b"\x1aE\xdf\xa3":               # matroska / webm
        return "video"
    if body[:3] == b"ID3" or body[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio"
    if body[:4] in (b"wOFF", b"wOF2", b"OTTO", b"true", b"\x00\x01\x00\x00"):
        return "font"
    return None


def load_manifest(path):
    if not os.path.exists(path):
        return {"schemaVersion": 1, "projectId": os.path.basename(os.path.dirname(os.path.dirname(path))) or "project",
                "commercial": False, "assets": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pexels_call(url, key):
    body, _ = http_get(url, headers={"Authorization": key})
    return json.loads(body.decode("utf-8"))


def pexels_to_candidates(data, limit):
    out = []
    for p in (data.get("photos") or [])[:limit]:
        src = p.get("src") or {}
        out.append({
            "id": p.get("id"),
            "w": p.get("width"), "h": p.get("height"),
            "photographer": p.get("photographer"),
            "page": p.get("url"),
            "download": src.get("large2x") or src.get("original") or src.get("large"),
            "alt": (p.get("alt") or "")[:60],
        })
    return out


def build_entry(a, ctype, digest, rel_path):
    return {
        "id": a.id,
        "path": rel_path,
        "kind": a.kind,
        "role": a.role,
        "source": {
            "type": a.source_type,
            "url": a.source_url or a.url or "",
            "provider": a.provider or "",
            "retrievedAt": a.retrieved_at,
        },
        "license": {
            "id": a.license,
            "commercialUse": not a.non_commercial,
            "attributionRequired": bool(a.attribution),
            "attributionText": a.attribution or "",
        },
        "sha256": digest,
        "notes": a.notes or f"content-type: {ctype}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="素材直链（图片/视频）")
    ap.add_argument("--file", help="已在本地下载好的素材（复制进 assets/ 并登记，零网络依赖）")
    ap.add_argument("--out", help="落地路径，相对 --root")
    ap.add_argument("--id", help="manifest 里的 id（缺省取文件名）")
    ap.add_argument("--role", default="space",
                    help="space/identity/prop/environment/texture/voice/sfx/bgm/typeface")
    ap.add_argument("--kind", default="image", help="image/sequence/video/audio/font/model3d")
    ap.add_argument("--license", help="许可 id（见 asset-sourcing.md §7 白名单）")
    ap.add_argument("--source-type", default="stock",
                    help="self/owned/stock/public-domain/ai/screen-record")
    ap.add_argument("--source-url", help="来源页（不是直链），写进台账供溯源")
    ap.add_argument("--attribution", help="署名文本；许可要求署名时必填")
    ap.add_argument("--non-commercial", action="store_true", help="该素材仅限非商用")
    ap.add_argument("--provider", help="provider 名称，如 ImageGen / Pexels")
    ap.add_argument("--retrieved-at", default=None, help="YYYY-MM-DD，默认今天")
    ap.add_argument("--notes", help="备注")
    ap.add_argument("--root", default=".", help="工程根（manifest 在 <root>/assets/asset-manifest.json）")
    ap.add_argument("--manifest", help="显式指定 manifest 路径")
    ap.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的目标文件")
    ap.add_argument("--dry-run", action="store_true", help="不下载不写盘，只打印")
    ap.add_argument("--pexels-search", help="用 Pexels 官方 API 检索（需 PEXELS_API_KEY）")
    ap.add_argument("--pexels-id", type=int, help="按 Pexels photo id 取图（需 PEXELS_API_KEY）")
    ap.add_argument("--list-only", action="store_true", help="只列候选，不下载")
    ap.add_argument("--per-page", type=int, default=12)
    ap.add_argument("--orientation", default="landscape", help="landscape/portrait/square")
    a = ap.parse_args()

    key = os.environ.get("PEXELS_API_KEY", "").strip()
    a.retrieved_at = a.retrieved_at or __import__("datetime").date.today().isoformat()

    # ---- 模式 1：Pexels 官方 API 检索 ----
    if a.pexels_search or a.pexels_id:
        if not key:
            die("Pexels API 需要 PEXELS_API_KEY。\n"
                "   注册（免费，即时给 key）：https://www.pexels.com/api/\n"
                "   然后：export PEXELS_API_KEY=xxxx\n"
                "   不想接 API 就用 --url 模式，把网页上拿到的直链给进来。")
        if a.pexels_search:
            q = urllib.parse.urlencode({"query": a.pexels_search, "per_page": a.per_page,
                                        "orientation": a.orientation})
            cands = pexels_to_candidates(pexels_call(f"{PEXELS_SEARCH}?{q}", key), a.per_page)
            if not cands:
                print("没有结果。换个关键词，或去掉 --orientation 限制。")
                return 0
            print(f"Pexels 候选 {len(cands)} 条（w×h 决定能不能撑 1440×1080）：\n")
            for c in cands:
                ok = "✅" if (c["w"] or 0) >= 1600 and (c["h"] or 0) >= 1080 else "⚠ "
                print(f"{ok} id={c['id']}  {c['w']}×{c['h']}  {c['alt']}")
                print(f"    {c['page']}")
            print("\n挑一条：--pexels-id <id> --out <路径> --id <素材id> --role <role>")
            print("注意：Pexels API 要求展示 “Photos provided by Pexels” 并尽量署名摄影师。")
            return 0
        # 按 id：先拿元信息，再从它的 src 取直链
        d = pexels_call(f"{PEXELS_PHOTO}{a.pexels_id}", key)
        src = d.get("src") or {}
        a.url = src.get("large2x") or src.get("original")
        a.source_url = a.source_url or d.get("url")
        a.license = a.license or "pexels-license"
        a.provider = a.provider or "Pexels"
        a.attribution = a.attribution or f"Photo by {d.get('photographer')} on Pexels"
        if not a.url:
            die("该 photo 没有可用的 src 字段，API 返回结构可能变了")

    # ---- 校验必填 ----
    if not (a.url or a.file or a.pexels_id or a.pexels_search):
        die("必须给 --url、--file，或用 --pexels-search / --pexels-id")
    if a.url:
        scheme = urllib.parse.urlparse(a.url).scheme
        if scheme not in ("http", "https"):
            die(f"只接受 http/https 直链，收到 {scheme!r}。本地文件用 --file，不要塞进 --url。")
    if a.file and not os.path.isfile(a.file):
        die(f"找不到本地文件 {a.file}")
    if not a.out:
        die("必须给 --out")
    if not a.license:
        die("必须给 --license（见 references/asset-sourcing.md §7 白名单）。\n"
            "   不填许可是本 skill 明确禁止的：没授权的素材等于没出处。")

    root = os.path.abspath(a.root)
    manifest_path = os.path.abspath(a.manifest) if a.manifest else os.path.join(root, "assets", "asset-manifest.json")
    dest = os.path.abspath(os.path.join(root, a.out))
    if os.path.commonpath([root, dest]) != root:
        die("目标路径跑出工程根了，拒绝写入")

    aid = a.id or os.path.splitext(os.path.basename(dest))[0]
    rel = os.path.relpath(dest, root).replace(os.sep, "/")

    print(f"来源页：{a.source_url or '（未填，非自制素材必须填）'}")
    print(f"取得：{'本地 ' + a.file if a.file else a.url}")
    print(f"落地：{rel}")
    print(f"许可：{a.license}" + (f" · 署名：{a.attribution}" if a.attribution else ""))

    if os.path.exists(dest) and not a.overwrite:
        die(f"{rel} 已存在。换文件名，或加 --overwrite。")

    if a.dry_run:
        print("\n（--dry-run，未下载、未写 manifest）")
        return 0

    if a.file:
        if os.path.exists(dest) and os.path.samefile(a.file, dest):
            die("--file 和目标路径是同一个文件，没必要复制")
        size = os.path.getsize(a.file)
        if size > MAX_MB * 1024 * 1024:
            die(f"文件 {size / 1024 / 1024:.0f}MB 超过 {MAX_MB}MB 上限")
        with open(a.file, "rb") as f:
            body = f.read()
        ctype = "local-file"          # 不做 MIME 判断，交给下面的 magic bytes
    else:
        body, ctype = http_get(a.url)
    actual = sniff(body)
    if actual is None:
        die(f"下载到的内容不是已知的图片/视频/音频/字体容器（前 16 字节 {body[:16]!r}）。\n"
            f"   Content-Type 声称是 {ctype or '未提供'}，但 magic bytes 不认。\n"
            f"   常见原因：防盗链占位页、登录墙、404 页；SVG 请先转 PNG。", 1)
    if a.kind in ("image", "video", "audio", "font") and actual != a.kind:
        die(f"声明 kind={a.kind}，实际内容是 {actual}。改 --kind 或换链接。", 1)
    digest = sha256_bytes(body)
    size = len(body)
    human = f"{size / 1024:.0f} KB" if size >= 1024 else f"{size} B"
    verb = "已读取" if a.file else "已下载"
    print(f"{verb} {human} · {ctype or '无 Content-Type'} · sha256 {digest[:12]}…")

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, dest)

    data = load_manifest(manifest_path)
    assets = data.setdefault("assets", [])
    entry = build_entry(a, ctype, digest, rel)
    entry["id"] = aid

    # 同一 id 覆盖、同一内容拦截
    for i, old in enumerate(assets):
        if old.get("id") == aid:
            print(f"manifest 里已有 id={aid}，替换该条")
            assets[i] = entry
            break
        if (old.get("sha256") or "").lower() == digest:
            die(f"这段内容和已有素材 [{old.get('id')}] 完全相同 —— 跨镜复用同一素材，"
                f"九轴单镜原则不成立。确需复用请手工编辑 manifest 并在 notes 写理由。", 1)
    else:
        assets.append(entry)

    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"已登记 → {safe_rel(manifest_path, os.getcwd())}")

    # 立刻过闸门：许可、商用、哈希、状态全部当场验，别等出片前才发现
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from check_assets import check_manifest
    issues, _ = check_manifest(data, root, commercial=data.get("commercial") is True)
    fails = [i for i in issues if i.level == "FAIL"]
    if fails:
        print("\n台账闸门未通过：")
        for i in fails:
            print("  " + str(i))
        print("\n仍已写入 manifest（不丢已下载的文件），但请按上面提示补齐后重跑："
              f"\n  python scripts/check_assets.py --manifest {os.path.relpath(manifest_path, os.getcwd())}")
        return 1
    print("✅ 台账闸门通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
