"""自動學新詞：比對「貼上的文字」和「使用者在同一個輸入框改過之後的文字」。

例如貼上「我用拍森寫的」，使用者把它改成「我用 Python 寫的」，就學到「Python」。
比對完全在本機進行；輸入框的內容只在記憶體裡比對，不會儲存或送出。
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+#'_&-]*|[㐀-鿿豈-﫿]|[^\s]")
_WORDISH = re.compile(r"[A-Za-z0-9㐀-鿿豈-﫿]")
_CJK = re.compile(r"[㐀-鿿豈-﫿]")

MAX_TERM_CHARS = 30
MAX_PER_PASTE = 3


def _tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(), m.start(), m.end()) for m in _TOKEN.finditer(text)]


def _is_word(tok: str) -> bool:
    return bool(_WORDISH.match(tok))


def _span(text: str, toks: list[tuple[str, int, int]]) -> str:
    return text[toks[0][1] : toks[-1][2]] if toks else ""


def find_corrections(pasted: str, field: str) -> list[tuple[str, str]]:
    """回傳 (原本的寫法, 改過的寫法)。找不到貼上的那段，或使用者大幅改寫時回傳空清單。"""
    a, b = _tokens(pasted), _tokens(field)
    if len(a) < 2 or not b:
        return []
    sm = SequenceMatcher(None, [t[0] for t in a], [t[0] for t in b], autojunk=False)
    equal = sum(size for *_, size in sm.get_matching_blocks())
    if equal < 0.6 * len(a):
        return []  # 輸入框裡已經找不到這段文字，或改寫太多
    changed = 0
    pairs: list[tuple[str, str]] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        changed += i2 - i1
        if op != "replace":
            continue  # 單純增刪是在改內容，不是改寫法
        new = b[j1:j2]
        if i1 == 0:  # 貼上的開頭被改了：輸入框這一側還包含前面原本就有的文字，只取緊鄰的那個詞
            new = _trailing_run(new)
        if i2 == len(a):
            new = _leading_run(new)
        if not new or len(new) > (i2 - i1) + 3:
            continue
        pairs.append((_span(pasted, a[i1:i2]), _span(field, new)))
    if changed > 0.4 * len(a):
        return []
    return [(w, r) for w, r in pairs if _learnable(w, r)][:MAX_PER_PASTE]


def _trailing_run(toks):
    run = []
    for t in reversed(toks):
        if not _is_word(t[0]):
            break
        run.insert(0, t)
    return run


def _leading_run(toks):
    run = []
    for t in toks:
        if not _is_word(t[0]):
            break
        run.append(t)
    return run


def _learnable(wrong: str, right: str) -> bool:
    if not wrong or not right or wrong == right:
        return False
    if len(right) > MAX_TERM_CHARS or not _WORDISH.search(right):
        return False
    if right.replace(".", "").replace(",", "").isdigit():
        return False  # 數字是在改內容
    cjk = len(_CJK.findall(right))
    if cjk == len(right) and cjk < 2:
        return False  # 單一個中文字（的／得、他／她）多半是改用字，不是新詞
    if wrong.lower() == right.lower() and not any(c.isupper() for c in right):
        return False
    return True


def merge(learned: list[str], words: list[str], *, known: list[str], ignored: list[str], limit: int = 200) -> list[str]:
    """把新學到的詞放到最前面；已經學過、已在字典裡或被使用者刪過的不加。"""
    skip = {w.lower() for w in [*known, *ignored, *learned]}
    out = list(learned)
    for w in words:
        if w.lower() in skip:
            continue
        skip.add(w.lower())
        out.insert(0, w)
    return out[:limit]
