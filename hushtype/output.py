"""把文字送進目前游標所在的應用程式。"""

from __future__ import annotations

import time


def insert_text(text: str, *, method: str = "paste", restore_clipboard: bool = True) -> None:
    import keyboard

    if method == "type":
        keyboard.write(text, delay=0.002)
        return

    import pyperclip

    previous = None
    if restore_clipboard:
        try:
            previous = pyperclip.paste()
        except pyperclip.PyperclipException:
            previous = None
    pyperclip.copy(text)
    time.sleep(0.05)
    keyboard.send("ctrl+v")
    if previous is not None:
        # 等目標程式讀完剪貼簿再還原
        time.sleep(0.4)
        pyperclip.copy(previous)
