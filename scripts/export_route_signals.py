#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from app.services.route_signal_service import RouteSignalService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()
    count = RouteSignalService(db_path=args.db).export_jsonl(args.output)
    print(f"exported {count} route events")


if __name__ == "__main__":
    main()
