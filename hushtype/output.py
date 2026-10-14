"""把文字送進目前游標所在的應用程式。"""

from __future__ import annotations

import threading
import time

# 貼上後還原剪貼簿是在背景做的；下一次貼上要等上一次還原完
_clipboard = threading.Lock()


def insert_text(text: str, *, method: str = "paste", restore_clipboard: bool = True) -> None:
    import keyboard

    if method == "type":
        keyboard.write(text, delay=0.002)
        return

    import pyperclip

    _clipboard.acquire()
    previous = None
    try:
        if restore_clipboard:
            try:
                previous = pyperclip.paste()
            except pyperclip.PyperclipException:
                previous = None
        pyperclip.copy(text)
        time.sleep(0.03)
        keyboard.send("ctrl+v")
    except BaseException:
        _clipboard.release()
        raise
    if previous is None:
        _clipboard.release()
        return

    def restore():
        try:
            time.sleep(0.4)  # 等目標程式讀完剪貼簿
            pyperclip.copy(previous)
        except Exception:
            pass
        finally:
            _clipboard.release()

    threading.Thread(target=restore, daemon=True).start()
