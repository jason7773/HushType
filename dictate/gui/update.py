"""在背景檢查與下載新版，把結果用 Signal 送回介面執行緒。"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from .. import __version__, updater


class UpdateController(QObject):
    checked = Signal(object, str)  # (Release 或 None, 說明文字)
    progress = Signal(int)  # 0–100
    failed = Signal(str)
    installing = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.release: updater.Release | None = None
        self.busy = False

    def check(self) -> None:
        if self.busy:
            return
        self.busy = True

        def work():
            try:
                rel = updater.latest_release()
            except updater.UpdateError as e:
                self.busy = False
                self.checked.emit(None, f"無法檢查更新：{e}")
                return
            self.busy = False
            if updater.is_newer(rel.version):
                self.release = rel
                self.checked.emit(rel, f"有新版 {rel.version}（目前 {__version__}）")
            else:
                self.release = None
                self.checked.emit(None, f"已經是最新版（{__version__}）")

        threading.Thread(target=work, daemon=True).start()

    def install(self) -> None:
        """下載並啟動安裝程式；成功時送出 installing，介面應立即結束程式。"""
        rel = self.release
        if rel is None or self.busy:
            return
        if not updater.can_self_update():
            self.failed.emit("開發版不能自動更新，請用安裝檔安裝的版本")
            return
        self.busy = True

        def work():
            try:
                path = updater.download(rel, lambda done, total: total and self.progress.emit(done * 100 // total))
                updater.launch_installer(path)
            except (updater.UpdateError, OSError) as e:
                self.busy = False
                self.failed.emit(str(e))
                return
            self.installing.emit()

        threading.Thread(target=work, daemon=True).start()
