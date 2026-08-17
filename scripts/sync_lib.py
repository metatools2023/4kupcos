"""4kupcos 共享逻辑：WP API 客户端、taxonomy 映射缓存、HTML->Markdown 转换。"""
import json
import re
import time
from html import unescape
from pathlib import Path

import requests
from bs4 import BeautifulSoup

API = "https://4kup.net/wp-json/wp/v2"
CATEGORY_ID = 2940  # coser
PER_PAGE = 100

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content" / "posts"
CACHE_FILE = Path(__file__).resolve().parent / "cache" / "taxonomies.json"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

session = requests.Session()
session.headers.update({"User-Agent": UA})


def throttle():
    time.sleep(1.0)


def get_json(url, params=None, tries=4):
    """GET JSON with backoff retry. Returns (data, headers); data=None when page out of range."""
    for i in range(tries):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 400:  # WP returns 400 "page number is larger" past the end
                return None, r.headers
            r.raise_for_status()
            return r.json(), r.headers
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i + 1)


# ---------- taxonomy 映射缓存 ----------

def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {"categories": {}, "models": {}}


def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))


def refresh_taxonomy(kind, cache):
    """增量刷新 kind('categories'|'models') 的 id->name 映射。
    按 id 降序翻页，遇到整页已知 id 即停（新条目 id 更大、出现在前面）。"""
    known = cache[kind]
    page = 1
    while True:
        data, headers = get_json(
            f"{API}/{kind}",
            {"per_page": PER_PAGE, "page": page, "orderby": "id",
             "order": "desc", "_fields": "id,name"},
        )
        if not data:
            break
        new = 0
        for t in data:
            k = str(t["id"])
            if k not in known:
                known[k] = unescape(t["name"])
                new += 1
        total_pages = int(headers.get("X-WP-TotalPages", 1))
        print(f"  {kind} page {page}/{total_pages}: +{new} new (total {len(known)})")
        if new == 0 or page >= total_pages:
            break
        page += 1
        throttle()


# ---------- 转换 ----------

def _yaml_fm(d):
    """手工渲染 YAML front matter（json.dumps 输出是合法 YAML 字符串）。"""
    lines = ["---"]
    for k, v in d.items():
        if isinstance(v, list):
            if v:
                lines.append(f"{k}:")
                lines += [f"  - {json.dumps(x, ensure_ascii=False)}" for x in v]
        elif isinstance(v, int):
            lines.append(f"{k}: {v}")
        elif v is not None:
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def post_to_markdown(post, cache):
    """WP post dict -> Hugo markdown 文本。纯函数，可全量重刷。"""
    soup = BeautifulSoup(post["content"]["rendered"], "html.parser")
    title = unescape(BeautifulSoup(post["title"]["rendered"],
                                   "html.parser").get_text()).strip()

    album, photos = None, None
    info = soup.select_one(".infobox")
    if info:
        text = info.get_text("\n")
        m = re.search(r"Album:\s*(.+)", text)
        if m:
            album = m.group(1).strip()
        m = re.search(r"Number of Photos:\s*(\d+)", text)
        if m:
            photos = int(m.group(1))

    dl = soup.select_one("p#download a")
    download_url = dl.get("href") if dl else None
    download_text = dl.get_text(strip=True) if dl else None

    images = []
    for a in soup.select("#gallery a.thumb-photo"):
        href = a.get("href")
        if href and href not in images:
            images.append(href)

    cats = [cache["categories"].get(str(c), str(c)) for c in post.get("categories", [])]
    models = [cache["models"].get(str(m), str(m)) for m in post.get("models", [])]

    fm = {
        "title": title,
        "date": post["date"],
        "slug": post["slug"],
        "wp_id": post["id"],
        "source": post["link"],
        "categories": cats,
        "models": models,
        "photos": photos,
        "image": images[0] if images else None,
    }

    body = []
    if album:
        body.append(f"**Album:** {album}  ")
    if photos:
        body.append(f"**Photos:** {photos}")
    body.append("")
    if download_url:
        body.append(f'{{{{< download "{download_url}" "{download_text or "Download"}" >}}}}')
        body.append("")
    for u in images:
        body.append(f"![]({u})")
        body.append("")

    return _yaml_fm(fm) + "\n\n" + "\n".join(body)


# ---------- 抓取 ----------

def prepare():
    cache = load_cache()
    refresh_taxonomy("categories", cache)
    refresh_taxonomy("models", cache)
    save_cache(cache)
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    return cache


def known_slugs():
    return {p.stem for p in CONTENT_DIR.glob("*.md")}


def fetch_pages(cache, pages):
    """抓取指定页码列表，跳过已存在文章。返回 (新增数, 跳过数)。"""
    known = known_slugs()
    added = skipped = 0
    for page in pages:
        data, headers = get_json(
            f"{API}/posts",
            {"categories": CATEGORY_ID, "per_page": PER_PAGE, "page": page},
        )
        if not data:
            print(f"page {page}: out of range, stop")
            break
        total_pages = headers.get("X-WP-TotalPages", "?")
        for post in data:
            slug = post["slug"]
            if slug in known:
                skipped += 1
                continue
            (CONTENT_DIR / f"{slug}.md").write_text(
                post_to_markdown(post, cache), encoding="utf-8")
            known.add(slug)
            added += 1
        print(f"page {page}/{total_pages}: {len(data)} posts "
              f"(added {added}, skipped {skipped})")
        throttle()
    return added, skipped


def sync(cache, max_pages):
    """增量：从最新页起翻页，整页已知即停。"""
    known = known_slugs()
    added = skipped = 0
    for page in range(1, max_pages + 1):
        data, headers = get_json(
            f"{API}/posts",
            {"categories": CATEGORY_ID, "per_page": PER_PAGE, "page": page},
        )
        if not data:
            break
        page_known = 0
        for post in data:
            slug = post["slug"]
            if slug in known:
                skipped += 1
                page_known += 1
                continue
            (CONTENT_DIR / f"{slug}.md").write_text(
                post_to_markdown(post, cache), encoding="utf-8")
            known.add(slug)
            added += 1
        print(f"page {page}: {len(data)} posts, {page_known} known "
              f"(added {added}, skipped {skipped})")
        throttle()
        if page_known == len(data):
            print("all known on this page, stop")
            break
    return added, skipped
