# -*- coding: utf-8 -*-
"""
上传本地文件为 GitHub Release 附件（走 uploads.github.com，绕过 github.com 不可达）。

用法：
  改下面的 TOKEN / OWNER / REPO / RELEASE_TAG / FILE 后直接运行。
  或命令行：python upload_release_asset.py <owner> <repo> <release_tag> <本地文件路径>

要点（实测）：
  - uploads.github.com 与 github.com 是不同域名，github.com 不通时它通常仍可达
  - 进度日志每 5% 打一次；打太密会产生海量 stdout 把进程冲死
  - 失败就重试；单个 50MB 文件在国内网络下一次成功率较高，留 7 次重试足够
  - HTTP 422 "already_exists" 往往是附件其实已建好（重复上传被拒），以 API 查 assets 为准
"""
import http.client
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

TOKEN = "REPLACE_WITH_TOKEN"          # 或设环境变量 GITHUB_TOKEN
OWNER = "2026heshao"
REPO = "wangyuhe-tools-src"
RELEASE_TAG = "launchdeck-v2.2.4"
FILE = r"D:\path\to\LaunchDeck_v2.2.4.zip"
ASSET_NAME = None                     # None = 用文件名


def api(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request("https://api.github.com" + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token()}",
                                          "Accept": "application/vnd.github+json",
                                          "User-Agent": "wb", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def token():
    return TOKEN if TOKEN != "REPLACE_WITH_TOKEN" else os.environ["GITHUB_TOKEN"]


def main():
    args = sys.argv[1:]
    owner, repo, tag, path = (args + [OWNER, REPO, RELEASE_TAG, FILE])[:4]
    name = ASSET_NAME or os.path.basename(path)
    size = os.path.getsize(path)
    print(f"目标: {owner}/{repo} @ {tag}  <-  {name}  ({size/1048576:.2f} MB)")

    rel = api("GET", f"/repos/{owner}/{repo}/releases/tags/{tag}")
    rel_id = rel["id"]
    for a in rel["assets"]:
        if a["name"] == name:
            print("附件已存在，跳过:", a["browser_download_url"])
            return

    print("探测 uploads.github.com ...", end=" ", flush=True)
    socket.create_connection(("uploads.github.com", 443), timeout=15).close()
    print("可达")

    url_path = f"/repos/{owner}/{repo}/releases/{rel_id}/assets?name={name}"
    for attempt in range(1, 8):
        print(f"--- 第 {attempt} 次上传 ---")
        conn = None
        try:
            conn = http.client.HTTPSConnection("uploads.github.com", timeout=120)
            conn.putrequest("POST", url_path, skip_accept_encoding=True)
            conn.putheader("Authorization", f"Bearer {token()}")
            conn.putheader("Accept", "application/vnd.github+json")
            conn.putheader("Content-Type", "application/zip")
            conn.putheader("Content-Length", str(size))
            conn.putheader("User-Agent", "wb")
            conn.endheaders()
            sent, last = 0, -1
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    conn.send(chunk)
                    sent += len(chunk)
                    pct = int(sent * 100 / size)
                    if pct // 5 != last // 5:      # 每 5% 一行
                        last = pct
                        print(f"    {pct}%  ({sent/1048576:.1f}/{size/1048576:.1f} MB)", flush=True)
            resp = conn.getresponse()
            body = resp.read().decode("utf-8", "replace")
            print("    HTTP", resp.status)
            if resp.status in (200, 201):
                print("    成功:", json.loads(body)["browser_download_url"])
                return
            print("    响应:", body[:300])
        except (OSError, http.client.HTTPException) as e:
            print("    异常:", type(e).__name__, e)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
        time.sleep(5)
    raise SystemExit("重试耗尽，上传失败")


if __name__ == "__main__":
    main()
