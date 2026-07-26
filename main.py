#!/usr/bin/env python3
"""MeshViewer application entry point."""

import sys
from pathlib import Path


src_path = Path(__file__).resolve().parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from meshviewer.main import main


if __name__ in {"__main__", "__mp_main__"}:
    main()
