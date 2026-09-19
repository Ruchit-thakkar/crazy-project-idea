# BG REMOVE — PyInstaller build script
# Usage:
#   pip install pyinstaller
#   python build.py
"""Build a standalone .exe for BG REMOVE using PyInstaller."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", "BGRemove",
        "--collect-all", "PySide6",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "scipy.ndimage",
        "--hidden-import", "scipy.special",
        "--paths", str(ROOT),
        str(ROOT / "main.py"),
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())