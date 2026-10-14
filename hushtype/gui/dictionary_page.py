"""「字典」頁：專有名詞（提示給辨識與整理模型）和固定替換，改了立即生效。"""

from __future__ import annotations

import copy

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .widgets import Card, FlowLayout, GlassFrame, HeroTitle, divider, icon_label, label


class Chip(GlassFrame):
    def __init__(self, text: str, on_remove, *, learned: bool = False):
        super().__init__(radius=13, spotlight=False)
        self.setObjectName("chip")
        row = QHBoxLayout(self)
        row.setContentsMargins(11, 6, 6, 6)
        row.setSpacing(7)
        if learned:
            mark = label("自動", "badge")
            mark.setToolTip("從你修改過的文字自動學到")
        else:
            mark = icon_label("sparkle", theme.current["accent"], 12)
        row.addWidget(mark, 0, Qt.AlignVCenter)
        row.addWidget(label(text))
        remove = QPushButton()
        remove.setIcon(theme.glyph_icon("close", theme.current["text_muted"]))
        remove.setIconSize(QSize(16, 16))
        remove.setObjectName("chipRemove")
        remove.setToolTip("刪除")
        remove.setCursor(Qt.PointingHandCursor)
        remove.clicked.connect(on_remove)
        row.addWidget(remove)


class DictionaryPage(QScrollArea):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setWidgetResizable(True)
        root = QWidget()
        root.setObjectName("page")
        self.setWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(28, 26, 28, 32)
        lay.setSpacing(16)

        lay.addWidget(HeroTitle("字典", 32))
        lay.addWidget(
            label("專有名詞會提示給辨識與整理模型，讓人名、術語寫對；固定替換會在最後把錯字換掉。改了立即生效。", "secondary", wrap=True)
        )

        bar = QHBoxLayout()
        bar.setSpacing(0)
        self.tab_group = QButtonGroup(self)
        for i, name in enumerate(("專有名詞", "固定替換")):
            b = QPushButton(name)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setChecked(i == 0)
            self.tab_group.addButton(b, i)
            bar.addWidget(b)
        bar.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜尋")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(lambda _: self.refresh())
        bar.addWidget(self.search)
        lay.addLayout(bar)

        self.stack = QStackedWidget()
        self.tab_group.idClicked.connect(self._switch)

        # 專有名詞
        terms = Card()
        add = QHBoxLayout()
        self.term_input = QLineEdit()
        self.term_input.setPlaceholderText("新增單字，例如：YouBike、陳禹誌（可用逗號一次加好幾個）")
        self.term_input.returnPressed.connect(self.add_terms)
        add.addWidget(self.term_input, 1)
        add_btn = QPushButton("新增")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self.add_terms)
        add.addWidget(add_btn)
        terms.body.addLayout(add)
        self.chips_box = QWidget()
        self.chips = FlowLayout(self.chips_box)
        terms.body.addWidget(self.chips_box)
        self.terms_empty = label("還沒有專有名詞。", "muted")
        terms.body.addWidget(self.terms_empty)

        terms.body.addWidget(divider())
        head = QHBoxLayout()
        head.addWidget(label("自動學到的詞", "h2"))
        head.addStretch(1)
        self.auto_learn = QCheckBox("自動學新詞")
        self.auto_learn.toggled.connect(self.set_auto_learn)
        head.addWidget(self.auto_learn)
        terms.body.addLayout(head)
        terms.body.addWidget(label(
            "貼上文字後，如果你在同一個輸入框把詞改掉（例如把「拍森」改成「Python」），"
            "就會把改好的寫法加進字典。比對只在這台電腦進行，輸入框的內容不會儲存或送出；密碼欄一律不讀。"
            "刪掉的詞不會再自動加回來。",
            "muted", wrap=True,
        ))
        self.learned_box = QWidget()
        self.learned_chips = FlowLayout(self.learned_box)
        terms.body.addWidget(self.learned_box)
        self.learned_empty = label("還沒有學到新詞。", "muted")
        terms.body.addWidget(self.learned_empty)
        self.stack.addWidget(terms)

        # 固定替換
        reps = Card()
        add = QHBoxLayout()
        self.wrong_input = QLineEdit()
        self.wrong_input.setPlaceholderText("常被辨識成，例如：拍森")
        self.right_input = QLineEdit()
        self.right_input.setPlaceholderText("換成，例如：Python")
        self.right_input.returnPressed.connect(self.add_replacement)
        add.addWidget(self.wrong_input, 1)
        add.addWidget(icon_label("arrow", theme.current["text_muted"], 16))
        add.addWidget(self.right_input, 1)
        add_btn = QPushButton("新增")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self.add_replacement)
        add.addWidget(add_btn)
        reps.body.addLayout(add)
        self.reps_box = QVBoxLayout()
        self.reps_box.setSpacing(6)
        reps.body.addLayout(self.reps_box)
        self.stack.addWidget(reps)

        lay.addWidget(self.stack)
        self.note = label("", "muted")
        lay.addWidget(self.note)
        lay.addStretch(1)
        self.refresh()

    # ---- 資料 ----

    @property
    def vocab(self) -> dict:
        return self.window.engine.config["vocabulary"]

    def _save(self, terms: list[str], replacements: dict[str, str], **changes) -> None:
        cfg = copy.deepcopy(self.window.engine.config)
        cfg["vocabulary"]["terms"] = terms
        cfg["vocabulary"]["replacements"] = replacements
        cfg["vocabulary"].update(changes)
        error = self.window.save_settings(cfg, {}, None)
        self.note.setText(error or "已儲存，立即生效")
        self.refresh()

    def add_terms(self) -> None:
        words = [w.strip() for w in self.term_input.text().replace("，", ",").replace("、", ",").split(",")]
        terms = list(self.vocab["terms"])
        for w in words:
            if w and w not in terms:
                terms.append(w)
        self.term_input.clear()
        self._save(terms, dict(self.vocab["replacements"]))

    def remove_learned(self, word: str) -> None:
        learned = [w for w in self.vocab["learned"] if w != word]
        ignored = [w for w in self.vocab["ignored"] if w.lower() != word.lower()] + [word]
        self._save(list(self.vocab["terms"]), dict(self.vocab["replacements"]), learned=learned, ignored=ignored)

    def set_auto_learn(self, on: bool) -> None:
        if on != self.vocab["auto_learn"]:
            self._save(list(self.vocab["terms"]), dict(self.vocab["replacements"]), auto_learn=on)

    def remove_term(self, term: str) -> None:
        self._save([t for t in self.vocab["terms"] if t != term], dict(self.vocab["replacements"]))

    def add_replacement(self) -> None:
        wrong, right = self.wrong_input.text().strip(), self.right_input.text().strip()
        if not wrong:
            return
        reps = dict(self.vocab["replacements"])
        reps[wrong] = right
        self.wrong_input.clear()
        self.right_input.clear()
        self.wrong_input.setFocus()
        self._save(list(self.vocab["terms"]), reps)

    def remove_replacement(self, wrong: str) -> None:
        reps = {k: v for k, v in self.vocab["replacements"].items() if k != wrong}
        self._save(list(self.vocab["terms"]), reps)

    # ---- 顯示 ----

    def _switch(self, i: int) -> None:
        self.stack.setCurrentIndex(i)
        self.refresh()

    def refresh(self) -> None:
        query = self.search.text().strip().lower()
        while self.chips.count():
            w = self.chips.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        terms = [t for t in self.vocab["terms"] if query in t.lower()]
        for t in terms:
            self.chips.addWidget(Chip(t, lambda _=False, t=t: self.remove_term(t)))
        self.terms_empty.setVisible(not terms)
        self.terms_empty.setText("找不到符合的單字。" if query and self.vocab["terms"] else "還沒有專有名詞。")
        self.chips_box.updateGeometry()

        while self.learned_chips.count():
            w = self.learned_chips.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        learned = [t for t in self.vocab["learned"] if query in t.lower()]
        for t in learned:
            self.learned_chips.addWidget(Chip(t, lambda _=False, t=t: self.remove_learned(t), learned=True))
        self.learned_empty.setVisible(not learned)
        self.learned_empty.setText("找不到符合的單字。" if query and self.vocab["learned"] else "還沒有學到新詞。")
        self.auto_learn.blockSignals(True)
        self.auto_learn.setChecked(self.vocab["auto_learn"])
        self.auto_learn.blockSignals(False)
        self.learned_box.updateGeometry()

        while self.reps_box.count():
            w = self.reps_box.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        reps = [(k, v) for k, v in self.vocab["replacements"].items() if query in k.lower() or query in v.lower()]
        for wrong, right in reps:
            row = GlassFrame(radius=14)
            row.setObjectName("entry")
            h = QHBoxLayout(row)
            h.setContentsMargins(14, 8, 8, 8)
            h.addWidget(label(wrong), 1)
            h.addWidget(icon_label("arrow", theme.current["text_muted"], 16))
            h.addWidget(label(right or "（刪除）"), 1)
            remove = QPushButton("刪除")
            remove.setObjectName("ghost")
            remove.clicked.connect(lambda _=False, w=wrong: self.remove_replacement(w))
            h.addWidget(remove)
            self.reps_box.addWidget(row)
        if not reps:
            self.reps_box.addWidget(label("還沒有固定替換。", "muted"))
