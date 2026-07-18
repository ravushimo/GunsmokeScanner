"""Download Growth Data specialized-trait icons from IOP Wiki.

Source page: https://iopwiki.com/wiki/GFL2_Doll_Enhancement
Files look like Sepal_Bloom_gamma.png, Marrow_Root_alpha.png, …
"""

from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WIKI_PAGE = "https://iopwiki.com/wiki/GFL2_Doll_Enhancement"
FILE_PAGE = "https://iopwiki.com/wiki/File:{name}"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

ICON_RE = re.compile(
    r"(?:File:|/wiki/File:)("
    r"(?:Sepal_Bloom|Heaven_Blossom|Crownslayer_Blossom|Flameflower|"
    r"Dewdrop_Leaf|Matrix_Leaf|Reverse-Thorned_Leaf|Emerald_Leaf|"
    r"Entropic_Stem|Fissure_Stem|Cataphyll_Stem|Keen_Stem|"
    r"Marrow_Root|Sanguine_Root|Stratified_Root|Thousand-Strand_Root)"
    r"_(?:alpha|beta|gamma)\.png)",
    re.I,
)
IMG_HREF_RE = re.compile(
    r'(?:href|content)="((?:https?:)?//iopwiki\.com)?(/images/(?!thumb/)[^"]+\.png)"',
    re.I,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def resolve_image_url(filename: str) -> str | None:
    html = fetch(FILE_PAGE.format(name=filename)).decode("utf-8", "replace")
    # Prefer non-thumb /images/.../ExactName.png
    candidates = []
    for m in IMG_HREF_RE.finditer(html):
        path = m.group(2)
        if filename.lower() not in path.lower():
            continue
        if "/thumb/" in path:
            continue
        candidates.append("https://iopwiki.com" + path)
    if not candidates:
        return None
    # Prefer exact basename match
    for c in candidates:
        if c.rstrip("/").endswith(filename):
            return c
    return candidates[0]


def main() -> int:
    out_dir = repo_root() / "assets" / "growth" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {WIKI_PAGE} …")
    html = fetch(WIKI_PAGE).decode("utf-8", "replace")
    names = sorted({m.group(1) for m in ICON_RE.finditer(html)})
    if not names:
        print("No icon filenames found on wiki page.", file=sys.stderr)
        return 1
    print(f"Found {len(names)} icons")

    ok = 0
    for name in names:
        dest = out_dir / name
        if dest.is_file() and dest.stat().st_size > 500:
            print(f"  skip {name}")
            ok += 1
            continue
        try:
            img_url = resolve_image_url(name)
            if not img_url:
                print(f"  FAIL {name}: could not resolve image URL")
                continue
            data = fetch(img_url)
            if len(data) < 200 or data[:1] == b"<":
                print(f"  FAIL {name}: unexpected response from {img_url}")
                continue
            dest.write_bytes(data)
            print(f"  ok   {name} ({len(data)} bytes)")
            ok += 1
            time.sleep(0.15)
        except urllib.error.HTTPError as e:
            print(f"  FAIL {name}: HTTP {e.code}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")

    print(f"Done: {ok}/{len(names)} in {out_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
