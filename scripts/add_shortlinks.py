#!/usr/bin/env python3
"""为文章下载链接生成 ShrtFly 付费短链，写入 front matter dl_short。

用法:
    python scripts/add_shortlinks.py --model 蠢沫沫   # 测试组
    python scripts/add_shortlinks.py --all           # 全量
    python scripts/add_shortlinks.py --model 蠢沫沫 --dry-run   # 只统计不调用 API

API key 优先级: --api-key 参数 > SHRTFLY_API_KEY 环境变量 > /home/ubuntu/webpages/apikey.md
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

API = "https://shrtfly.com/api"
ADS_TYPE = 1  # 1=mainstream, 2=adult
RATE = 1.0  # req/s

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "content" / "posts"
KEYFILE = Path("/home/ubuntu/webpages/apikey.md")

DL_RE = re.compile(r'\{\{<\s*download\s+"([^"]+)"')
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})


def load_api_key(cli_arg):
    if cli_arg:
        return cli_arg
    if os.environ.get("SHRTFLY_API_KEY"):
        return os.environ["SHRTFLY_API_KEY"]
    if KEYFILE.exists():
        for line in KEYFILE.read_text(encoding="utf-8").splitlines():
            if "shrtfly_api_key" in line.lower():
                return line.split(":", 1)[1].strip()
    sys.exit("ERROR: no ShrtFly API key found (arg/env/apikey.md)")


def shorten(api_key, url, tries=4):
    """ShrtFly API: GET /api?api=KEY&url=URL&format=text&type=1 -> 纯文本短链"""
    for i in range(tries):
        try:
            r = session.get(API, params={
                "api": api_key, "url": url,
                "format": "text", "type": ADS_TYPE,
            }, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            text = r.text.strip()
            if text.startswith("http"):
                return text
            # JSON error like {"status":"error","result":"..."}
            try:
                j = json.loads(text)
                raise RuntimeError(f"API error: {j.get('result', text)}")
            except json.JSONDecodeError:
                raise RuntimeError(f"API returned non-URL: {text[:200]}")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i + 1)
    return None


def process_post(path, api_key, dry_run):
    """单篇处理。返回 (动作, 详情)。动作: skip/added/error/no_dl"""
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if not m:
        return "error", "no front matter"
    fm = m.group(1)

    if "dl_short:" in fm:
        return "skip", "already has dl_short"

    dl = DL_RE.search(text)
    if not dl:
        return "no_dl", "no download shortcode"
    long_url = dl.group(1)

    if dry_run:
        return "added", f"(dry) would shorten {long_url}"

    short = shorten(api_key, long_url)
    if not short:
        return "error", "API returned empty"

    # 插入 dl_short 到 front matter（source: 行之后，保持与 _yaml_fm 风格一致）
    insert_line = f'dl_short: {json.dumps(short, ensure_ascii=False)}'
    new_fm = re.sub(r'^(source:.*)$', r'\1\n' + insert_line, fm, count=1, flags=re.M)
    new_text = text.replace(f"---\n{fm}\n---\n", f"---\n{new_fm}\n---\n", 1)
    path.write_text(new_text, encoding="utf-8")
    return "added", short


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="只处理该模特的文章（front matter 含此名）")
    ap.add_argument("--all", action="store_true", help="处理全部文章")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不调用 API")
    ap.add_argument("--limit", type=int, help="最多处理的篇数（测试用）")
    ap.add_argument("--api-key", help="ShrtFly API key")
    args = ap.parse_args()

    if not args.model and not args.all:
        sys.exit("ERROR: 需指定 --model <名> 或 --all")

    api_key = load_api_key(args.api_key)

    stats = {"added": 0, "skip": 0, "no_dl": 0, "error": 0}
    errors = []
    files = sorted(POSTS.glob("*.md"))
    matched = 0

    for path in files:
        if args.model:
            text = path.read_text(encoding="utf-8")
            m = FM_RE.match(text)
            fm = m.group(1) if m else ""
            if f'"{args.model}"' not in fm:
                continue
        matched += 1
        if args.limit and stats["added"] >= args.limit:
            continue
        action, detail = process_post(path, api_key, args.dry_run)
        stats[action] += 1
        if action == "error":
            errors.append(f"{path.name}: {detail}")
            print(f"  ERROR {path.name}: {detail}")
        if action == "added" and not args.dry_run:
            time.sleep(RATE)
        if stats["added"] % 50 == 0 and stats["added"] > 0 and not args.dry_run:
            print(f"  progress: added={stats['added']} "
                  f"skip={stats['skip']} err={stats['error']}")

    print(f"\nDONE: matched={matched} added={stats['added']} "
          f"skip={stats['skip']} no_dl={stats['no_dl']} error={stats['error']}")
    if errors:
        print("failed files:")
        for e in errors:
            print(f"  {e}")


if __name__ == "__main__":
    main()
