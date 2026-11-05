"""Download one photo per item in catalog.json into images/<product_id>.jpg.

The Hugging Face dataset only ships images inside a 3.5 GB tar, but every
`image_src` basename is IKEA's own CDN filename and this is the live 2025 US
catalogue, so we pull each straight from ikea.com. Resumable: existing files are
skipped.

Run:  python fetch_images.py
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
CATALOG = HERE / "catalog.json"
IMG_DIR = HERE / "images"
BASE = "https://www.ikea.com/us/en/images/products/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}


def main() -> None:
    IMG_DIR.mkdir(exist_ok=True)
    items = json.loads(CATALOG.read_text())
    got = skipped = failed = 0

    for it in items:
        dst = IMG_DIR / f"{it['product_id']}.jpg"
        if dst.exists():
            skipped += 1
            continue
        url = BASE + it["image_src"].split("/")[-1]
        try:
            req = urllib.request.Request(url, headers=UA)
            data = urllib.request.urlopen(req, timeout=30).read()
            dst.write_bytes(data)
            got += 1
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            print(f"  FAIL {it['product_id']}: {e}")
            failed += 1
        time.sleep(0.2)

    print(f"\ndownloaded {got}, skipped {skipped}, failed {failed} "
          f"({len(list(IMG_DIR.glob('*.jpg')))} images on disk)")


if __name__ == "__main__":
    main()
