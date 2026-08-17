#!/usr/bin/env python3
"""增量同步：拉取最新若干页，遇到整页已知即停。"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_lib import prepare, sync


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=3,
                    help="最多扫描的列表页数（默认 3，防止空库首跑全量）")
    args = ap.parse_args()
    cache = prepare()
    added, skipped = sync(cache, args.max_pages)
    print(f"DONE sync: added={added} skipped={skipped}")


if __name__ == "__main__":
    main()
