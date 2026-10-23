#!/usr/bin/env python3
"""Inspect a versioned local renderer timeline before rendering it."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mathcoffee.renderer_contract import validate_timeline  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = validate_timeline(json.loads(args.manifest.read_text()), args.assets)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "assets"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
