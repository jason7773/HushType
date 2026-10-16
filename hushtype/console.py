"""主控台模式（除錯用）：在 terminal 顯示引擎事件。"""

from __future__ import annotations

from .engine import Engine

_STATES = {"recording": "● 錄音中…", "processing": "  處理中…"}


def _print_event(kind: str, data: dict) -> None:
    if kind == "state" and data["state"] in _STATES:
        print(_STATES[data["state"]], flush=True)
    elif kind == "result":
        detail = data.get("text") or f"{data['chars']} 字"
        print(f"  ✓ 已輸入 {detail}（{data['latency']:.1f} 秒）", flush=True)
    elif kind == "skipped":
        print(f"  略過：{data['reason']}", flush=True)
    elif kind == "error":
        print(f"  ✗ {data['message']}", flush=True)


def run(config: dict) -> None:
    import time

    engine = Engine(config, _print_event)
    if engine.setup_error:
        print(f"設定有問題：{engine.setup_error}")
    engine.bind()
    how = "按住" if config["hotkey"]["mode"] == "hold" else "按一下開始、再按一下結束"
    print(f"Hushtype 已啟動：{how}「{config['hotkey']['key']}」說話。按 Ctrl+C 結束。", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        engine.unbind()
