#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -X utf8 -u "$ROOT/launcher/run_super_mcp.py"
