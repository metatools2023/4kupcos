#!/usr/bin/env python3
"""扫描全部文章 front matter，按 tags[0]（coser 名）聚合成 data/models.json：
[{name, count, latest, image}]，按最近更新降序。封面取最新有图文章的首图。"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_lib import ROOT, CONTENT_DIR

DATE_RE = re.compile(r'^date: "?([^"\n]+)"?$', re.M)
IMAGE_RE = re.compile(r'^image: "(.*)"$', re.M)
TAGS_BLOCK_RE = re.compile(r'^tags:$((?:\n  - .*)*)', re.M)

OUT = ROOT / "data" / "models.json"


def main():
    models = {}
    for p in sorted(CONTENT_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = TAGS_BLOCK_RE.search(text)
        if not m:
            continue
        tags = [l.strip()[2:].strip('"') for l in m.group(1).splitlines() if l.strip()]
        if not tags:
            continue
        name = tags[0]  # coser 名恒为首个（retag/auto_tags 保证）
        d = DATE_RE.search(text)
        date = d.group(1).strip() if d else ""
        img = IMAGE_RE.search(text)
        image = img.group(1).strip() if img else ""
        rec = models.setdefault(name, {"count": 0, "latest": "", "image": ""})
        rec["count"] += 1
        if date > rec["latest"]:
            rec["latest"] = date
            if image:
                rec["image"] = image
        elif not rec["image"] and image:
            rec["image"] = image  # 兜底：最新篇无图时用较早的图

    data = [{"name": n, "count": r["count"], "latest": r["latest"], "image": r["image"]}
            for n, r in models.items()]
    data.sort(key=lambda x: x["name"])      # tiebreaker：latest 相同时按名字决胜，保证输出确定
    data.sort(key=lambda x: x["latest"], reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    with_image = sum(1 for d in data if d["image"])
    print(f"models: {len(data)} (with cover: {with_image}) -> {OUT}")


if __name__ == "__main__":
    main()
