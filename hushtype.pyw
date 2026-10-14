"""雙擊或捷徑啟動用（不開 terminal 視窗）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hushtype.__main__ import main  # noqa: E402

sys.exit(main())
