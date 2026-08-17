#!/usr/bin/env python3
"""标签工具：
1) 从标题提取 coser 名写入 front matter tags
2) 剩余主题词清洗后统计 -> keywords.md（供人工筛选）
3) --apply 模式：按白名单 data/keywords.txt 给文章补打主题词标签
"""
import argparse
import collections
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_lib import (ROOT, CONTENT_DIR, WHITELIST_FILE, parse_title,
                      clean_word, is_noise)

KEYWORDS_MD = ROOT / "keywords.md"

TITLE_RE = re.compile(r'^title: "(.*)"$', re.M)
TAGS_BLOCK_RE = re.compile(r'^tags:$((?:\n  - .*)*)', re.M)
MODELS_BLOCK_RE = re.compile(r'^models:$((?:\n  - .*)+)', re.M)
CATS_BLOCK_RE = re.compile(r'^categories:$((?:\n  - .*)+)', re.M)


def get_tags(text):
    m = TAGS_BLOCK_RE.search(text)
    if not m:
        return []
    return [l.strip()[2:].strip('"') for l in m.group(1).splitlines() if l.strip()]


def set_tags(text, tags):
    """写入/替换 tags 块（保持生成格式）。"""
    block = "tags:\n" + "".join(
        f'  - {json.dumps(t, ensure_ascii=False)}\n' for t in tags)
    m = TAGS_BLOCK_RE.search(text)
    if m:
        return text[:m.start()] + block + text[m.end():]
    m = MODELS_BLOCK_RE.search(text) or CATS_BLOCK_RE.search(text)
    if m:
        return text[:m.end() + 1] + block + text[m.end() + 1:]
    raise RuntimeError("no insertion point for tags block")


def iter_posts():
    for p in sorted(CONTENT_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = TITLE_RE.search(text)
        if m:
            yield p, text, m.group(1)


def run_extract():
    kw = collections.Counter()
    alias = collections.Counter()
    unmatched = []
    tagged = 0
    total = 0
    for p, text, title in iter_posts():
        total += 1
        coser, words, parens = parse_title(title)
        for w in words:
            kw[w] += 1
        for g in parens:
            alias[g] += 1
        if coser:
            old = get_tags(text)
            new = list(dict.fromkeys([coser] + old))
            if new != old:
                p.write_text(set_tags(text, new), encoding="utf-8")
            tagged += 1
        else:
            unmatched.append(title)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# 关键词报告  生成于 {now}",
             f"# 文章总数 {total} | 成功打 coser 名标签 {tagged} | 未解析 {len(unmatched)}",
             "# 用法：直接删除不要的行，保留的行将进入白名单；行内 (次数) 仅参考",
             "", f"## 普通主题词（{len(kw)} 个，按次数降序）", ""]
    lines += [f"{w} ({c})" for w, c in kw.most_common()]
    lines += ["", f"## 括号别名组（{len(alias)} 个，多为 coser 别名/中文译名）", ""]
    lines += [f"{w} ({c})" for w, c in alias.most_common()]
    lines += ["", f"## 未解析标题（{len(unmatched)}）", ""]
    lines += [f"- {t}" for t in unmatched]
    KEYWORDS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"total={total} tagged={tagged} unmatched={len(unmatched)}")
    print(f"theme words: {len(kw)} distinct | alias groups: {len(alias)} distinct")
    print(f"written: {KEYWORDS_MD}")


def load_whitelist():
    if not WHITELIST_FILE.exists():
        sys.exit(f"whitelist not found: {WHITELIST_FILE}")
    return {l.split(" (")[0].strip()
            for l in WHITELIST_FILE.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")}


def run_apply():
    whitelist = load_whitelist()
    updated = added_kw = 0
    for p, text, title in iter_posts():
        coser, words, parens = parse_title(title)
        hits = [w for w in (words + parens) if w in whitelist]
        old = get_tags(text)
        new = list(dict.fromkeys(([coser] if coser else []) + old + sorted(hits)))
        if new != old:
            p.write_text(set_tags(text, new), encoding="utf-8")
            updated += 1
            added_kw += len(hits)
    print(f"updated={updated} posts, keyword tags added={added_kw}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="按 data/keywords.txt 白名单给文章补打主题词标签")
    args = ap.parse_args()
    run_apply() if args.apply else run_extract()


if __name__ == "__main__":
    main()
