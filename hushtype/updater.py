"""程式內更新：查 GitHub 上最新的 Release，下載安裝檔，安靜安裝後自動重新開啟。

只連 api.github.com 與 GitHub 的下載網址，不送出任何使用資料。
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

from . import __version__

REPO = "jason7773/hushtype"
LEGACY_REPO = "jason7773/dictate"  # 改名前的 repo；GitHub 會自動轉址


def _latest_url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}/releases/latest"
INSTALLER = re.compile(r"^Hushtype-setup-([\d.]+)\.exe$", re.IGNORECASE)


class UpdateError(RuntimeError):
    pass


@dataclass
class Release:
    version: str
    url: str  # 安裝檔下載網址
    size: int
    sha256: str  # GitHub 提供的檔案雜湊；舊的 Release 可能沒有
    page: str  # Release 網頁


def parse_version(text: str) -> tuple[int, ...]:
    """"0.4.0" → (0, 4, 0)；開發版（含 -dev）只取前面的數字。"""
    nums = re.match(r"v?(\d+(?:\.\d+)*)", text.strip())
    return tuple(int(n) for n in nums.group(1).split(".")) if nums else ()


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def can_self_update() -> bool:
    """只有用安裝檔裝的版本（打包過的 exe）才能自己更新。"""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def latest_release(timeout: float = 10) -> Release:
    try:
        for repo in (REPO, LEGACY_REPO):
            resp = requests.get(_latest_url(repo), headers={"Accept": "application/vnd.github+json"}, timeout=timeout)
            if resp.status_code != 404:
                break
    except requests.RequestException as e:
        raise UpdateError(f"無法連線到 GitHub：{e}") from e
    if resp.status_code == 404:
        raise UpdateError("找不到 Release（repo 可能還沒公開）")
    if resp.status_code != 200:
        raise UpdateError(f"GitHub 回應 {resp.status_code}")
    data = resp.json()
    for asset in data.get("assets", []):
        if INSTALLER.match(asset.get("name", "")):
            digest = asset.get("digest") or ""
            return Release(
                version=data.get("tag_name", "").lstrip("v"),
                url=asset["browser_download_url"],
                size=int(asset.get("size") or 0),
                sha256=digest.removeprefix("sha256:") if digest.startswith("sha256:") else "",
                page=data.get("html_url", ""),
            )
    raise UpdateError("最新的 Release 裡沒有安裝檔")


def download(release: Release, progress: Callable[[int, int], None] | None = None) -> Path:
    """下載到暫存資料夾並核對雜湊，回傳安裝檔路徑。"""
    target = Path(tempfile.gettempdir()) / f"Hushtype-setup-{release.version}.exe"
    sha = hashlib.sha256()
    done = 0
    try:
        with requests.get(release.url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length") or release.size or 0)
            with open(target, "wb") as f:
                for chunk in resp.iter_content(1 << 16):
                    f.write(chunk)
                    sha.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except (requests.RequestException, OSError) as e:
        raise UpdateError(f"下載失敗：{e}") from e
    if release.size and done != release.size:
        target.unlink(missing_ok=True)
        raise UpdateError("下載的檔案不完整，請再試一次")
    if release.sha256 and sha.hexdigest() != release.sha256.lower():
        target.unlink(missing_ok=True)
        raise UpdateError("下載的檔案和 GitHub 上的不一致，已刪除")
    return target


def launch_installer(path: Path) -> None:
    """安靜安裝；安裝程式會先關掉程式，裝完再自動開啟。呼叫後程式應立即結束。"""
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [str(path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH"],
        creationflags=flags if os.name == "nt" else 0,
        close_fds=True,
    )
