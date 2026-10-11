from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True, type=Path)
    args, passthrough = parser.parse_known_args()
    original = pd.to_datetime

    def mixed_iso_to_datetime(arg, *positional, **kwargs):
        kwargs.setdefault("format", "mixed")
        return original(arg, *positional, **kwargs)

    pd.to_datetime = mixed_iso_to_datetime
    sys.argv = [str(args.script), *passthrough]
    try:
        runpy.run_path(str(args.script), run_name="__main__")
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
