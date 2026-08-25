from __future__ import annotations

import argparse
import json

from kch_contractual_rigor import FIELD_DEFAULTS, MODES, clamp, resolve
from kch_native_state import connect, set_setting, setting


def read_overrides(db):
    raw = setting(db, "rigor_field_overrides_json")
    return json.loads(raw) if raw else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="KCH Contractual Rigor Fader admin")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    mode = sub.add_parser("set-mode")
    mode.add_argument("mode", choices=MODES)
    default = sub.add_parser("set-default")
    default.add_argument("intensity", type=int)
    field = sub.add_parser("set-field")
    field.add_argument("field", choices=sorted(FIELD_DEFAULTS))
    field.add_argument("intensity", type=int)
    clear = sub.add_parser("clear-field")
    clear.add_argument("field", choices=sorted(FIELD_DEFAULTS))
    args = parser.parse_args()

    db = connect()
    try:
        if args.command == "set-mode":
            set_setting(db, "rigor_mode", args.mode)
        elif args.command == "set-default":
            set_setting(db, "rigor_default_intensity", str(clamp(args.intensity)))
        elif args.command in {"set-field", "clear-field"}:
            overrides = read_overrides(db)
            if args.command == "set-field":
                overrides[args.field] = clamp(args.intensity)
            else:
                overrides.pop(args.field, None)
            set_setting(db, "rigor_field_overrides_json", json.dumps(overrides, sort_keys=True))
        print(json.dumps(resolve(db), ensure_ascii=False, indent=2))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
