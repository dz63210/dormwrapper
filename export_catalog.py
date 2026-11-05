"""Copy the root catalog.json to backend/data/catalog.json (what the backend seeds from).

build_catalog.py already writes both, so you only need this after hand-editing
the root catalog.json.

    python export_catalog.py
"""

import json
import shutil
from pathlib import Path

SRC = Path("catalog.json")
DST = Path("backend/data/catalog.json")


def main() -> None:
    n = len(json.loads(SRC.read_text()))
    DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, DST)
    print(f"copied {SRC} -> {DST} ({n} items)")


if __name__ == "__main__":
    main()
