#!/usr/bin/env python3
"""素材台账闸门：把「素材从哪来、能不能用、用了几次」变成可判 PASS/FAIL 的检查。

为什么需要它：SKILL.md 长期只有一句「保留素材来源、授权、生成入口」。
口号没有强制字段，就等于没有。实测路径（图片序列、AI 场景板）能跑，但没有任何
东西拦住一张"从影视截图里抠的"或"图上有人脸但没 model release"的素材进成片。

本脚本只做离线可判的四类事实：
  1 可溯源    source.url / retrievedAt 是否填得出来（自制除外）
  2 可商用    license.id 在白名单内、commercialUse 与工程性质一致
  3 可核对    文件存在、sha256 与实际内容一致
  4 不重复    同一 sha256 只在一个镜头成立（跨镜复用同一底图会被判视觉贫乏）

不做：图片内容识别、人脸检测、条款实时查询。许可条款会变，
所以记录 retrievedAt 而不是背下条款；核对靠人，留痕靠这个脚本。

用法：
    python scripts/check_assets.py --manifest <项目>/assets/asset-manifest.json
    python scripts/check_assets.py --manifest <路径> --commercial      # 商用工程
    python scripts/check_assets.py --manifest <路径> --stamp           # 回填缺失的 sha256
    python scripts/check_assets.py --manifest <路径> --json            # 机器可读
退出码：0 通过（可带 WARN）；1 有 FAIL；2 参数/文件错误。

契约与来源清单：references/asset-sourcing.md §6–§8。
"""
import argparse
import hashlib
import json
import os
import re
import sys

try:  # Windows 控制台默认 GBK，打印 ❌/中文/箭头会直接炸
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# §7 白名单。不在表里的许可一律 FAIL：cc-by-nc / editorial-only / rights-managed
# 混进商用片是真实的赔付风险，不是形式问题。
LICENSES = {
    "own": (True, False),
    "self": (True, False),
    "pexels-license": (True, False),
    "unsplash-license": (True, False),
    "pixabay-content-license": (True, False),
    "cc0-1.0": (True, False),
    "cc-by-4.0": (True, True),
    "cc-by-sa-4.0": (True, True),
    "ofl-1.1": (True, False),
    "apache-2.0": (True, False),
    "provider-terms": (False, False),   # AI 生成物：按 provider 条款，商用需逐条核
}
# 商用状态未知、需人确认的许可：工程声明 commercial 时仍判 FAIL，避免默认放行
KINDS = {"image", "sequence", "video", "audio", "font", "model3d"}
ROLES = {"space", "identity", "prop", "environment", "texture",
         "voice", "sfx", "bgm", "typeface"}
SRC_TYPES = {"self", "owned", "stock", "public-domain", "ai", "screen-record"}
SELF_TYPES = {"self", "owned"}          # 自制：不要求 url
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Issue:
    __slots__ = ("level", "code", "aid", "msg")

    def __init__(self, level, code, aid, msg):
        self.level, self.code, self.aid, self.msg = level, code, aid, msg

    def __str__(self):
        who = f"[{self.aid}] " if self.aid else ""
        return f"{self.level} {self.code} {who}{self.msg}"


def default_root(manifest_path):
    """manifest 固定在 <project>/assets/asset-manifest.json，path 相对 <project> 解析。

    早期版本把 root 当成 manifest 所在目录，用标准布局时所有 path 都多拼一层 assets/
    从而全员 E008。这里按目录名判断：父目录叫 assets 就再上一层。
    """
    d = os.path.dirname(os.path.abspath(manifest_path))
    if os.path.basename(d).lower() == "assets":
        return os.path.dirname(d)
    return d


def sha256_of(path):
    """文件取内容哈希；sequence 目录按文件名排序拼接，能反映增删与内容变化。"""
    h = hashlib.sha256()
    if os.path.isdir(path):
        names = sorted(n for n in os.listdir(path) if n.lower().endswith((".png", ".jpg", ".jpeg")))
        if not names:
            return None
        for n in names:
            h.update(n.encode("utf-8"))
            with open(os.path.join(path, n), "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
        return h.hexdigest()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_manifest(data, root, commercial=False, allow_license=(), allow_reuse=False):
    """纯校验，不打印、不写盘。返回 (issues, stamped) —— 测试直接调这个。

    root: manifest 所在目录，path 相对它解析。
    stamped: {asset_id: sha256} 需要回填的项（--stamp 用）。
    """
    issues, stamped = [], {}
    assets = data.get("assets")
    if not isinstance(assets, list):
        return [Issue("FAIL", "E001", None, "assets 必须是数组")], stamped
    if not assets:
        issues.append(Issue("WARN", "W001", None,
                            "assets 为空 —— 纯代码绘制的片子不需要此文件；若用了外部素材则是漏登记"))
        return issues, stamped

    seen_id, seen_hash = {}, {}
    for i, a in enumerate(assets):
        if not isinstance(a, dict):
            issues.append(Issue("FAIL", "E002", f"#{i}", "条目不是对象"))
            continue
        aid = a.get("id") or f"#{i}"
        add = lambda lv, code, msg: issues.append(Issue(lv, code, aid, msg))

        # ---- 身份 ----
        if not a.get("id"):
            add("FAIL", "E003", "缺 id（derivedFrom 无法解析）")
        elif a["id"] in seen_id:
            add("FAIL", "E004", "id 重复")
        else:
            seen_id[a["id"]] = a

        # ---- 分类 ----
        if a.get("kind") not in KINDS:
            add("FAIL", "E005", f"kind={a.get('kind')!r} 不在 {sorted(KINDS)}")
        if a.get("role") not in ROLES:
            add("FAIL", "E006", f"role={a.get('role')!r} 不在 {sorted(ROLES)}")

        # ---- 文件 ----
        rel = a.get("path")
        abspath = os.path.normpath(os.path.join(root, rel)) if rel else None
        exists = bool(abspath) and os.path.exists(abspath)
        if not rel:
            add("FAIL", "E007", "缺 path")
        elif not exists:
            add("FAIL", "E008", f"文件不存在：{rel}")
        elif a.get("kind") == "sequence" and not os.path.isdir(abspath):
            add("FAIL", "E009", "kind=sequence 但 path 不是目录")
        elif a.get("kind") == "sequence" and os.path.isdir(abspath):
            pngs = [n for n in os.listdir(abspath) if n.lower().endswith(".png")]
            if not pngs:
                add("FAIL", "E010", "sequence 目录里没有 PNG 帧")
            else:
                # frameCount 是重抽后最容易过期的字段：序列变了、manifest 没变，
                # 工程按旧帧数算时序，末帧被重复夹取，画面不会报错只会卡住。
                fc = a.get("frameCount")
                if fc is not None:
                    try:
                        if int(fc) != len(pngs):
                            add("FAIL", "E025",
                                f"frameCount={fc} 但目录里有 {len(pngs)} 帧 —— 重抽过？更新 manifest")
                    except (TypeError, ValueError):
                        add("FAIL", "E025", f"frameCount={fc!r} 不是整数")

        # ---- 可溯源 ----
        src = a.get("source") or {}
        st = src.get("type")
        if st not in SRC_TYPES:
            add("FAIL", "E011", f"source.type={st!r} 不在 {sorted(SRC_TYPES)}")
        if st not in SELF_TYPES and not (src.get("url") or "").strip():
            add("FAIL", "E012", "非自制素材必须填 source.url，填不出来就不许上屏")
        if not DATE_RE.match(str(src.get("retrievedAt") or "")):
            add("FAIL", "E013", "source.retrievedAt 缺失或不是 YYYY-MM-DD（条款会变，日期即证据）")

        # ---- 可商用 ----
        lic = a.get("license") or {}
        lid = lic.get("id")
        if not lid:
            add("FAIL", "E014", "缺 license.id")
        elif lid not in LICENSES and lid not in allow_license:
            add("FAIL", "E015", f"license.id={lid!r} 不在白名单（确需放行用 --allow-license {lid} 并在 notes 写理由）")
        elif lid in LICENSES:
            ok_commercial, need_attr = LICENSES[lid]
            if commercial and not ok_commercial and lid != "provider-terms":
                add("FAIL", "E016", f"{lid} 不允许商用，而工程声明 commercial=true")
            if need_attr and not (lic.get("attributionText") or "").strip():
                add("FAIL", "E017", f"{lid} 要求署名，attributionText 为空")
            if lid == "cc-by-sa-4.0":
                add("WARN", "W003", "cc-by-sa 要求衍生作品同许可，商用片慎用")
        if commercial and lic.get("commercialUse") is not True:
            add("FAIL", "E018", "工程声明 commercial=true，但 commercialUse 不是 true")
        if lic.get("attributionRequired") is True and not (lic.get("attributionText") or "").strip():
            add("FAIL", "E019", "attributionRequired=true 但 attributionText 为空")

        # ---- 可核对 ----
        want = (a.get("sha256") or "").strip()
        if exists:
            real = sha256_of(abspath)
            if not want:
                stamped[aid] = real
                add("FAIL", "E020", "缺 sha256（加 --stamp 自动回填）")
            elif real and want.lower() != real.lower():
                add("FAIL", "E021", f"sha256 与实际内容不符（实际 {real[:12]}…）")
            if want:
                if want.lower() in seen_hash:
                    other = seen_hash[want.lower()]
                    if not allow_reuse:
                        add("FAIL", "E022", f"与 [{other}] 内容相同 —— 同一素材跨镜复用，九轴单镜原则不成立")
                else:
                    seen_hash[want.lower()] = aid

        # ---- 派生 ----
        df = a.get("derivedFrom")
        if df:
            if df == a.get("id"):
                add("FAIL", "E023", "derivedFrom 指向自己")
        if a.get("kind") == "video":
            add("WARN", "W002", "kind=video：直接嵌 MP4 有 −52 帧风险，建议抽帧成 sequence")

    # 派生关系要能解析（放在全表扫完后判，允许前向引用）
    for a in assets:
        if not isinstance(a, dict):
            continue
        df = a.get("derivedFrom")
        if df and df not in seen_id:
            issues.append(Issue("FAIL", "E024", a.get("id"), f"derivedFrom={df!r} 解不到任何 id"))
    return issues, stamped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--root", help="工程根目录（默认由 manifest 位置推导：<project>/assets/ → <project>）")
    ap.add_argument("--commercial", action="store_true", help="工程用于商业发布")
    ap.add_argument("--stamp", action="store_true", help="回填缺失的 sha256 并写回文件")
    ap.add_argument("--allow-license", action="append", default=[], help="放行白名单外的许可 id（可多次）")
    ap.add_argument("--allow-reuse", action="store_true", help="允许同一素材跨镜复用")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    a = ap.parse_args()

    if not os.path.exists(a.manifest):
        print(f"❌ 找不到 {a.manifest}", file=sys.stderr)
        return 2
    try:
        with open(a.manifest, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ manifest 不是合法 JSON：{e}", file=sys.stderr)
        return 2

    root = os.path.abspath(a.root) if a.root else default_root(a.manifest)
    commercial = a.commercial or data.get("commercial") is True
    issues, stamped = check_manifest(data, root, commercial, a.allow_license, a.allow_reuse)

    if a.stamp and stamped:
        for x in data["assets"]:
            if isinstance(x, dict) and x.get("id") in stamped:
                x["sha256"] = stamped[x["id"]]
        with open(a.manifest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        # 回填后重跑，让 WARN/FAIL 反映最终状态（E020 不该残留在输出里）
        issues, _ = check_manifest(data, root, commercial, a.allow_license, a.allow_reuse)
        print(f"已回填 sha256：{len(stamped)} 项 → {a.manifest}")

    fails = [i for i in issues if i.level == "FAIL"]
    warns = [i for i in issues if i.level == "WARN"]

    if a.json:
        print(json.dumps({"ok": not fails,
                          "commercial": commercial,
                          "count": len(data.get("assets") or []),
                          "stamped": len(stamped),
                          "issues": [{"level": i.level, "code": i.code,
                                      "asset": i.aid, "msg": i.msg} for i in issues]},
                         ensure_ascii=False, indent=2))
    else:
        n = len(data.get("assets") or [])
        print(f"素材台账：{n} 项 · 商用={commercial} · FAIL {len(fails)} · WARN {len(warns)}")
        for i in issues:
            print(("  " if i.level == "FAIL" else "  ") + str(i))
        if fails:
            print("\n❌ 不通过：素材来源/授权/一致性有硬失败，不许进入成片。"
                  "\n   规则见 references/asset-sourcing.md §6–§8。")
        else:
            print("\n✅ 通过" + (f"（{len(warns)} 条提醒）" if warns else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
