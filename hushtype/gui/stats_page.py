"""「統計」頁：今天／本月／累計、每日長條圖、使用時段、每月表格。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from ..stats import load_summary, open_html_report
from .widgets import BarChart, Card, StatTile, label

METRICS = [("minutes", "說話分鐘", "分鐘"), ("count", "次數", "次"), ("chars", "字數", "字")]


def _minutes(m: float) -> tuple[str, str]:
    return (f"{m / 60:,.1f}", "小時") if m >= 60 else (f"{m:,.1f}" if m < 10 else f"{m:,.0f}", "分鐘")


class StatsPage(QScrollArea):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setWidgetResizable(True)
        root = QWidget()
        root.setObjectName("page")
        self.setWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(28, 24, 28, 28)
        lay.setSpacing(16)

        head = QHBoxLayout()
        head.addWidget(label("使用統計", "h1"), 1)
        refresh = QPushButton("重新整理")
        refresh.clicked.connect(self.refresh)
        html = QPushButton("匯出成網頁報表")
        html.clicked.connect(lambda: open_html_report(self.window.engine.config))
        head.addWidget(refresh)
        head.addWidget(html)
        lay.addLayout(head)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.tiles = {
            name: StatTile(title)
            for name, title in [
                ("today", "今天說話時間"),
                ("month", "本月說話時間"),
                ("chars", "本月輸出字數"),
                ("saved", "本月估計省下"),
                ("latency", "平均回應時間"),
                ("streak", "連續使用"),
            ]
        }
        for i, tile in enumerate(self.tiles.values()):
            grid.addWidget(tile, i // 3, i % 3)
        lay.addLayout(grid)

        daily = Card()
        row = QHBoxLayout()
        self.daily_title = label("近 30 天", "h2")
        row.addWidget(self.daily_title, 1)
        self.metric_group = QButtonGroup(self)
        self.metric_group.setExclusive(True)
        seg = QHBoxLayout()
        seg.setSpacing(0)
        for i, (_, name, _) in enumerate(METRICS):
            b = QPushButton(name)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setChecked(i == 0)
            self.metric_group.addButton(b, i)
            seg.addWidget(b)
        self.metric_group.idClicked.connect(lambda _: self._draw_daily())
        row.addLayout(seg)
        daily.body.addLayout(row)
        self.daily_chart = BarChart(220)
        daily.body.addWidget(self.daily_chart)
        lay.addWidget(daily)

        hourly = Card("一天中的使用時段（次數）")
        self.hourly_chart = BarChart(180)
        hourly.body.addWidget(self.hourly_chart)
        lay.addWidget(hourly)

        apps = Card("在哪些程式使用（次數）")
        self.apps_chart = BarChart(200)
        apps.body.addWidget(self.apps_chart)
        self.apps_empty = label("還沒有資料。新版開始記錄你在哪個程式使用語音輸入（只記程式名稱）。", "muted", wrap=True)
        apps.body.addWidget(self.apps_empty)
        lay.addWidget(apps)

        monthly = Card("每月統計")
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["月份", "次數", "說話（分鐘）", "字數", "省下（分鐘）", "平均回應（秒）", "失敗"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        monthly.body.addWidget(self.table)
        lay.addWidget(monthly)

        self.footnote = label("", "muted", wrap=True)
        lay.addWidget(self.footnote)
        lay.addStretch(1)
        self.summary: dict | None = None

    def refresh(self) -> None:
        cfg = self.window.engine.config
        s = self.summary = load_summary(cfg)
        t, m, total = s["today"], s["month"], s["total"]
        self.tiles["today"].set(*_minutes(t["minutes"]), f"{t['count']:,} 次・{t['chars']:,} 字")
        self.tiles["month"].set(*_minutes(m["minutes"]), f"{m['count']:,} 次")
        self.tiles["chars"].set(f"{m['chars']:,}", "字", f"累計 {total['chars']:,} 字")
        self.tiles["saved"].set(*_minutes(m["saved_minutes"]), "累計 " + " ".join(_minutes(total["saved_minutes"])))
        latency = m["avg_latency"] if m["avg_latency"] is not None else total["avg_latency"]
        self.tiles["latency"].set("—" if latency is None else f"{latency:.1f}", "秒", "放開按鍵到文字出現")
        self.tiles["streak"].set(f"{s['streak_days']}", "天", f"累計 {total['count']:,} 次")
        self._draw_daily()
        self.hourly_chart.set_data(
            [{"h": h, "c": c} for h, c in enumerate(s["hourly"])],
            value=lambda d: d["c"],
            label=lambda d: str(d["h"]),
            tip=lambda d: f"{d['h']}:00–{d['h']}:59\n{d['c']:,} 次",
            label_width=30,
        )
        top_apps = [a for a in s["apps"] if a["app"] != "未知"][:8]
        self.apps_empty.setVisible(not top_apps)
        self.apps_chart.setVisible(bool(top_apps))
        self.apps_chart.set_data(
            top_apps,
            value=lambda d: d["count"],
            label=lambda d: d["app"],
            tip=lambda d: f"{d['app']}\n{d['count']:,} 次・{d['chars']:,} 字・{d['minutes']:.1f} 分鐘",
            label_width=70,
        )
        self.table.setRowCount(len(s["monthly"]))
        for r, row in enumerate(s["monthly"]):
            values = [
                row["month"],
                f"{row['count']:,}",
                f"{row['minutes']:,.1f}",
                f"{row['chars']:,}",
                f"{row['saved_minutes']:,.1f}",
                "—" if row["avg_latency"] is None else f"{row['avg_latency']:.1f}",
                f"{row['errors']:,}",
            ]
            for c, v in enumerate(values):
                item = QTableWidgetItem(v)
                item.setTextAlignment((Qt.AlignLeft if c == 0 else Qt.AlignRight) | Qt.AlignVCenter)
                self.table.setItem(r, c, item)
        self.table.setFixedHeight(40 + 34 * max(len(s["monthly"]), 1))
        enabled = "" if cfg["stats"]["enabled"] else "目前已關閉使用統計，新的使用不會被記錄。"
        self.footnote.setText(
            f"「省下時間」以每分鐘打 {s['typing_cpm']} 字估算（打字所需時間減去說話與等待時間）。"
            f"統計只記錄時間與字數，不記錄任何說話內容，資料只存在這台電腦。{enabled}"
        )

    def _draw_daily(self) -> None:
        if not self.summary:
            return
        key, name, unit = METRICS[self.metric_group.checkedId()]
        daily = self.summary["daily"]
        self.daily_title.setText(f"近 {len(daily)} 天每日{name}")
        self.daily_chart.set_data(
            daily,
            value=lambda d: d[key],
            label=lambda d: d["date"][5:].replace("-", "/"),
            tip=lambda d: f"{d['date']}\n{d['minutes']:.1f} 分鐘・{d['count']:,} 次・{d['chars']:,} 字",
        )
