#!/usr/bin/env python3
"""对 keywords.md 做噪声初筛（可重复运行）：
- A月份 / B碎片 / C通用英文 / D月度作品片段 -> 移入 keywords.removed.md
- E拉丁名碎片 / F短中文名碎片 -> 移到顶部“待定”区供人工快审
- 其余（G保留）与括号别名组、未解析标题区保持原样
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KW = ROOT / "keywords.md"
REMOVED = ROOT / "keywords.removed.md"

MONTHS = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
          "Nov", "Dec", "January", "February", "March", "April", "June", "July",
          "August", "September", "October", "November", "December"}
GENERIC_EN = {
    "Fantia", "Patreon", "PATREON", "Part", "Full", "Set", "Vol", "Girl", "Girls",
    "Dress", "Formal", "Bikini", "Maid", "Black", "Summer", "White", "Casual",
    "Red", "Blue", "Sexy", "Pack", "Cosplay", "Cos", "Silver", "Gold", "Hot",
    "Cute", "Bunny", "Swimsuit", "Lingerie", "Christmas", "Halloween", "Sailor",
    "Uniform", "Stockings", "School", "JK", "Santa", "Valentine", "Nurse",
    "Office", "Wedding", "Cheongsam", "Kimono", "Yukata", "Photos", "Photo",
    "Leech", "Leak", "Leaks", "Bonus", "Special", "Limited", "Deluxe",
    "Complete", "Collection", "Works", "Work", "Contents", "Content", "Tier",
    "Rewards", "Monthly"}
JUNK_CJK = re.compile(r"月作品|月票|月合集|特典|訂閱|订阅")

CAT_NAMES = {
    "A": "A_月份", "B": "B_单字符/Part碎片", "C": "C_通用英文词",
    "D": "D_月度作品片段", "E": "E_拉丁名碎片", "F": "F_短中文名碎片",
}


def load_fragments():
    cache = json.loads((ROOT / "scripts" / "cache" / "taxonomies.json")
                       .read_text(encoding="utf-8"))
    frag = set()
    for n in cache["models"].values():
        toks = [t.strip("()（）-_,.·") for t in n.split()]
        toks = [t for t in toks if len(t) >= 2]
        if len(toks) >= 2:
            frag.update(toks)
    return frag


def classify(word, frag):
    if word in MONTHS:
        return "A"
    if re.fullmatch(r"[a-z]|\d|x|o|a|Part\d+|part\d+", word):
        return "B"
    if word in GENERIC_EN:
        return "C"
    if JUNK_CJK.search(word) or re.search(r"^\d{4}年|^\d{1,2}月", word):
        return "D"
    if word in frag and re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-]*", word):
        return "E"
    if word in frag and len(word) <= 4:
        return "F"
    return "G"


def main():
    frag = load_fragments()
    lines = KW.read_text(encoding="utf-8").splitlines()

    normal, alias, unmatched, header = [], [], [], []
    sec = None
    for l in lines:
        if l.startswith("## "):
            sec = l
            continue
        if sec is None:  # 文件头注释
            header.append(l)
            continue
        if not l.strip():
            continue
        if "普通主题词" in sec:
            normal.append(l)
        elif "括号别名组" in sec:
            alias.append(l)
        elif "未解析" in sec:
            unmatched.append(l)

    removed = {"A": [], "B": [], "C": [], "D": []}
    pending, keep = [], []
    for l in normal:
        word = l.split(" (")[0].strip()
        c = classify(word, frag)
        if c in removed:
            removed[c].append(l)
        elif c in ("E", "F"):
            pending.append(l)
        else:
            keep.append(l)

    out = [
        "# 关键词报告（已初筛）",
        "# 已自动移除 A-D 类噪声 -> keywords.removed.md（可复核）",
        "# 待定区 = 名字碎片，可能混有角色/作品名，请扫一眼删除不要的行",
        "",
        f"## 待定（{len(pending)} 个：E拉丁名碎片 + F短中文名碎片）",
        "",
    ] + pending + [
        "",
        f"## 普通主题词（保留 {len(keep)} 个，按次数降序）",
        "",
    ] + keep + [
        "",
        f"## 括号别名组（{len(alias)} 个，多为 coser 别名/中文译名）",
        "",
    ] + alias + [
        "",
        f"## 未解析标题（{len(unmatched)}）",
        "",
    ] + unmatched
    KW.write_text("\n".join(out) + "\n", encoding="utf-8")

    rem = ["# 自动移除的噪声行（留底备查）", ""]
    for c in "ABCD":
        rem += [f"## {CAT_NAMES[c]}（{len(removed[c])}）", ""] + removed[c] + [""]
    REMOVED.write_text("\n".join(rem) + "\n", encoding="utf-8")

    total = sum(len(v) for v in removed.values())
    print(f"removed: {total} (A{len(removed['A'])} B{len(removed['B'])} "
          f"C{len(removed['C'])} D{len(removed['D'])})")
    print(f"pending(待定): {len(pending)} | keep: {len(keep)} | alias: {len(alias)}")
    print(f"written: {KW} / {REMOVED}")


if __name__ == "__main__":
    main()
