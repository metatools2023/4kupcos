#!/usr/bin/env python3
"""历史回填：按页码区间抓取（幂等，已存在即跳过）。"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_lib import prepare, fetch_pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-page", type=int, required=True)
    ap.add_argument("--end-page", type=int, required=True)
    args = ap.parse_args()
    if args.start_page > args.end_page:
        ap.error("--start-page must be <= --end-page")
    cache = prepare()
    added, skipped = fetch_pages(cache, range(args.start_page, args.end_page + 1))
    print(f"DONE backfill pages {args.start_page}-{args.end_page}: "
          f"added={added} skipped={skipped}")


if __name__ == "__main__":
    main()
