#!/usr/bin/env python3
"""Compatibility entry point; the installed package owns the implementation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mathcoffee.synthesis import *  # noqa: F403
if __name__ == "__main__":
    result = main()  # noqa: F405
    raise SystemExit(result)
