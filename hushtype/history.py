"""辨識結果的歷史紀錄。

預設只放在記憶體，關閉程式就消失。使用者選擇保留天數後才寫入硬碟：
存在 %APPDATA%\\Hushtype\\history.db，每一筆文字都用 Windows DPAPI 加密，
只有同一個 Windows 帳號在這台電腦上才能解開。
"""

from __future__ import annotations

import sqlite3
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

RETENTIONS = [
    ("只保留到關閉程式", "session"),
    ("1 天", "1d"),
    ("1 週", "7d"),
    ("1 個月", "30d"),
    ("永久", "forever"),
]
_DAYS = {"1d": 1, "7d": 7, "30d": 30}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    app TEXT NOT NULL DEFAULT '',
    seconds REAL NOT NULL DEFAULT 0,
    text BLOB NOT NULL            -- DPAPI 加密後的 UTF-8 文字
)
"""


@dataclass
class Entry:
    created_at: datetime
    text: str
    app: str = ""
    seconds: float = 0.0
    id: int | None = None


# ---- 加密（Windows DPAPI，綁定目前使用者）----


def _blob(data: bytes):
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf, DATA_BLOB


def _dpapi(data: bytes, encrypt: bool) -> bytes:
    import ctypes

    blob_in, _keep, DATA_BLOB = _blob(data)
    blob_out = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    fn = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out))  # UI_FORBIDDEN
    if not ok:
        raise OSError("DPAPI 失敗")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def protect(text: str) -> bytes:
    return _dpapi(text.encode("utf-8"), True)


def unprotect(data: bytes) -> str:
    return _dpapi(bytes(data), False).decode("utf-8")


def disk_supported() -> bool:
    return sys.platform == "win32"


# ---- 紀錄 ----


class History:
    def __init__(self, path: Path, retention: str = "session", *, crypt=None):
        self.path = Path(path)
        self.entries: list[Entry] = []  # 新的在前
        self._lock = threading.Lock()
        self._protect, self._unprotect = crypt or (protect, unprotect)
        self.retention = "session"
        self.set_retention(retention)

    @property
    def on_disk(self) -> bool:
        return self.retention != "session"

    def set_retention(self, retention: str) -> None:
        """改保留期限。改成「只保留到關閉程式」時，會刪掉硬碟上的紀錄。"""
        if retention != "session" and self._protect is protect and not disk_supported():
            retention = "session"
        was_on_disk = self.on_disk
        self.retention = retention
        if self.on_disk:
            if not was_on_disk:
                # 先把記憶體裡的紀錄寫進去，再載入硬碟上的舊紀錄
                pending = list(reversed(self.entries))
                with self._lock:
                    self.entries = []
                for e in pending:
                    self._write(e)
            self._purge()
            self._load()
        elif was_on_disk:
            self._wipe_disk()

    def add(self, text: str, *, app: str = "", seconds: float = 0.0) -> Entry:
        entry = Entry(datetime.now().replace(microsecond=0), text, app, seconds)
        if self.on_disk:
            self._write(entry)
        with self._lock:
            self.entries.insert(0, entry)
            del self.entries[2000:]
        return entry

    def delete(self, entry: Entry) -> None:
        with self._lock:
            self.entries = [e for e in self.entries if e is not entry]
        if self.on_disk and entry.id is not None:
            with self._connect() as db:
                db.execute("DELETE FROM history WHERE id = ?", (entry.id,))

    def clear(self) -> None:
        with self._lock:
            self.entries = []
        if self.path.exists():
            self._wipe_disk()

    def purge(self) -> None:
        """刪除超過保留期限的紀錄。"""
        days = _DAYS.get(self.retention)
        if days is None:
            return
        cutoff = datetime.now() - timedelta(days=days)
        with self._lock:
            self.entries = [e for e in self.entries if e.created_at >= cutoff]
        if self.on_disk:
            self._purge()

    # ---- 硬碟 ----

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        db.execute(_SCHEMA)
        return db

    def _write(self, entry: Entry) -> None:
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO history (created_at, app, seconds, text) VALUES (?, ?, ?, ?)",
                (entry.created_at.isoformat(), entry.app, entry.seconds, self._protect(entry.text)),
            )
            entry.id = cur.lastrowid

    def _purge(self) -> None:
        days = _DAYS.get(self.retention)
        if days is None:
            return
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._connect() as db:
            db.execute("DELETE FROM history WHERE created_at < ?", (cutoff,))

    def _load(self) -> None:
        loaded = []
        with self._connect() as db:
            rows = db.execute("SELECT id, created_at, app, seconds, text FROM history ORDER BY created_at DESC, id DESC LIMIT 2000")
            for rid, created, app, seconds, blob in rows:
                try:
                    text = self._unprotect(blob)
                except Exception:
                    continue  # 別的帳號或別台電腦加密的，解不開就略過
                loaded.append(Entry(datetime.fromisoformat(created), text, app, seconds, rid))
        with self._lock:
            self.entries = loaded

    def _wipe_disk(self) -> None:
        try:
            with sqlite3.connect(self.path) as db:
                db.execute("DROP TABLE IF EXISTS history")
            with sqlite3.connect(self.path) as db:
                db.execute("VACUUM")  # 讓刪掉的內容不留在檔案裡
        except sqlite3.Error:
            pass
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
