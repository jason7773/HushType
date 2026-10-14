from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import autostart
from .config import config_path, load_config, migrate_legacy_data


def main() -> int:
    parser = argparse.ArgumentParser(prog="hushtype", description="語音輸入：按住快捷鍵說話，放開後貼上整理好的文字")
    parser.add_argument("--config", help="設定檔路徑（預設為 %%APPDATA%%\\Hushtype\\config.toml）")
    parser.add_argument("--minimized", action="store_true", help="啟動時只顯示系統匣圖示（開機自動啟動用）")
    parser.add_argument("--console", action="store_true", help="不開視窗，在 terminal 執行（除錯用）")
    parser.add_argument("--file", help="不啟動快捷鍵，直接處理一個 WAV 檔並印出結果（測試用）")
    parser.add_argument("--stats", action="store_true", help="產生 HTML 使用統計報表並用瀏覽器開啟")
    args = parser.parse_args()

    if not args.config:
        migrate_legacy_data()  # 改名前（dictate）的資料搬過來
    autostart.migrate_legacy()
    path = Path(args.config) if args.config else config_path()

    if not (args.console or args.file or args.stats):
        from .gui import run

        return run(path, minimized=args.minimized)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    config = load_config(path if path.exists() else None)

    if args.stats:
        from .stats import open_html_report

        print(f"報表：{open_html_report(config)}")
        return 0

    if args.file:
        from .pipeline import build_pipeline

        print(build_pipeline(config).run(Path(args.file).read_bytes()))
        return 0

    from .console import run

    run(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
