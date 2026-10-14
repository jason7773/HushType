"""本機使用紀錄。只存時間、數量（幾秒、幾個字）與在哪個程式使用，從不存語音或文字內容。"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,      -- 本地時間 ISO 格式
    audio_seconds REAL NOT NULL,   -- 說話長度
    chars INTEGER NOT NULL,        -- 輸出字數
    latency_seconds REAL NOT NULL, -- 放開按鍵到文字貼上的時間
    status TEXT NOT NULL,          -- ok / empty / error
    app TEXT NOT NULL DEFAULT ''   -- 貼上時前景程式的名稱，例如 chrome.exe
)
"""


class UsageLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(_SCHEMA)
            columns = {r[1] for r in db.execute("PRAGMA table_info(sessions)")}
            if "app" not in columns:  # 舊版資料庫
                db.execute("ALTER TABLE sessions ADD COLUMN app TEXT NOT NULL DEFAULT ''")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def record(
        self,
        *,
        started_at: datetime,
        audio_seconds: float,
        chars: int,
        latency_seconds: float,
        status: str,
        app: str = "",
    ) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO sessions (started_at, audio_seconds, chars, latency_seconds, status, app)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (started_at.isoformat(timespec="seconds"), audio_seconds, chars, latency_seconds, status, app),
            )

    def rows(self) -> list[tuple]:
        """(開始時間, 秒數, 字數, 延遲, 狀態, 程式)"""
        with self._connect() as db:
            cur = db.execute(
                "SELECT started_at, audio_seconds, chars, latency_seconds, status, app"
                " FROM sessions ORDER BY started_at"
            )
            return [(datetime.fromisoformat(r[0]), *r[1:]) for r in cur]


def _bucket() -> dict:
    return {"count": 0, "seconds": 0.0, "chars": 0, "latency": 0.0, "errors": 0}


def _add(b: dict, seconds: float, chars: int, latency: float, status: str) -> None:
    if status == "error":
        b["errors"] += 1
        return
    b["count"] += 1
    b["seconds"] += seconds
    b["chars"] += chars
    b["latency"] += latency


# 常見程式的顯示名稱
APP_NAMES = {
    "chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "brave.exe": "Brave",
    "arc.exe": "Arc", "opera.exe": "Opera", "winword.exe": "Word", "excel.exe": "Excel",
    "powerpnt.exe": "PowerPoint", "outlook.exe": "Outlook", "olk.exe": "Outlook", "onenote.exe": "OneNote",
    "teams.exe": "Teams", "ms-teams.exe": "Teams", "line.exe": "LINE", "slack.exe": "Slack",
    "discord.exe": "Discord", "telegram.exe": "Telegram", "whatsapp.exe": "WhatsApp", "notion.exe": "Notion",
    "obsidian.exe": "Obsidian", "code.exe": "VS Code", "cursor.exe": "Cursor", "notepad.exe": "記事本",
    "windowsterminal.exe": "終端機", "chatgpt.exe": "ChatGPT", "claude.exe": "Claude", "explorer.exe": "檔案總管",
}


def app_label(exe: str) -> str:
    if not exe:
        return "未知"
    return APP_NAMES.get(exe.lower(), exe.rsplit(".", 1)[0])


def summarize(rows, *, today: date | None = None, days: int = 30, typing_cpm: float = 40) -> dict:
    """把原始紀錄彙總成儀表板需要的數字。"""
    today = today or date.today()
    by_day: dict[date, dict] = defaultdict(_bucket)
    by_month: dict[str, dict] = defaultdict(_bucket)
    by_app: dict[str, dict] = defaultdict(_bucket)
    by_hour = [0] * 24
    total = _bucket()
    for started, seconds, chars, latency, status, *rest in rows:
        d = started.date()
        app = app_label(rest[0] if rest else "")
        for b in (by_day[d], by_month[started.strftime("%Y-%m")], total, by_app[app]):
            _add(b, seconds, chars, latency, status)
        if status != "error":
            by_hour[started.hour] += 1

    def finish(b: dict) -> dict:
        speak_min = b["seconds"] / 60
        typing_min = b["chars"] / typing_cpm if typing_cpm else 0
        return {
            "count": b["count"],
            "minutes": round(speak_min, 1),
            "chars": b["chars"],
            "avg_latency": round(b["latency"] / b["count"], 2) if b["count"] else None,
            "saved_minutes": round(max(typing_min - speak_min - b["latency"] / 60, 0), 1),
            "errors": b["errors"],
        }

    streak = 0
    d = today if by_day.get(today, {}).get("count") else today - timedelta(days=1)
    while by_day.get(d, {}).get("count"):
        streak += 1
        d -= timedelta(days=1)

    active = sorted(d for d, b in by_day.items() if b["count"])
    longest = run = 0
    for i, d in enumerate(active):
        run = run + 1 if i and d - active[i - 1] == timedelta(days=1) else 1
        longest = max(longest, run)

    speak_min = total["seconds"] / 60

    this_month = today.strftime("%Y-%m")
    return {
        "generated_at": datetime.now().isoformat(timespec="minutes"),
        "today": finish(by_day.get(today, _bucket())),
        "month": finish(by_month.get(this_month, _bucket())),
        "total": finish(total),
        "streak_days": streak,
        "longest_streak": longest,
        "active_days": len(active),
        "chars_per_minute": round(total["chars"] / speak_min) if speak_min else 0,
        "heatmap": {d.isoformat(): b["count"] for d, b in by_day.items() if b["count"]},
        "apps": sorted(
            ({"app": a, **finish(b)} for a, b in by_app.items() if b["count"]),
            key=lambda x: x["count"],
            reverse=True,
        ),
        "daily": [
            {"date": (today - timedelta(days=i)).isoformat(), **finish(by_day.get(today - timedelta(days=i), _bucket()))}
            for i in range(days - 1, -1, -1)
        ],
        "monthly": [{"month": m, **finish(b)} for m, b in sorted(by_month.items(), reverse=True)],
        "hourly": by_hour,
        "typing_cpm": typing_cpm,
    }


def usage_db_path(config: dict) -> Path:
    from .config import data_dir

    return Path(config["stats"]["path"] or data_dir() / "usage.db")


def load_summary(config: dict) -> dict:
    db = usage_db_path(config)
    rows = UsageLog(db).rows() if db.exists() else []
    return summarize(rows, typing_cpm=config["stats"]["typing_cpm"])


def open_html_report(config: dict) -> Path:
    import webbrowser

    from .dashboard import write_dashboard

    out = write_dashboard(load_summary(config), usage_db_path(config).with_name("dashboard.html"))
    webbrowser.open(out.resolve().as_uri())
    return out
