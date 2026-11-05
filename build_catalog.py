"""Build catalog.json from the 2025 IKEA US dataset (jeffreyszhou/ikea-us-products-2025).

  products-us.jsonl (~30,500 rows, from Hugging Face)
    -> filter to 20 dorm-relevant furniture types
    -> 15 per type, fixed seed
    -> drop good_to_know / materials / care_instructions / raw title / trees
    -> parse price -> USD float, dominant_color from the title
    -> attach hand-assigned style tags (STYLE_TAGS, below)
    -> catalog.json   (fetch_images.py then pulls the photos into images/)

catalog.json is the source of truth. `python export_catalog.py` copies it to
backend/data/catalog.json, which the backend seeds from.

Run:  python build_catalog.py
Raw file:  curl -sL -o products-us.jsonl \\
  https://huggingface.co/datasets/jeffreyszhou/ikea-us-products-2025/resolve/main/products-us.jsonl
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "products-us.jsonl"
OUT = HERE / "catalog.json"
PER_TYPE = 15
SEED = 42

STYLES = {
    "scandinavian", "minimalist", "modern", "industrial",
    "mid-century", "boho", "traditional",
}

# category_tree filters -> our "type" label. Chosen to hit whole usable products
# and skip modular systems / sets / parts / covers.
def _t(r, i):
    t = r["category_tree"]
    return t[i] if len(t) > i else None


TYPES = {
    "Beds": lambda r: r["category_tree"][2:4] == ["Beds", "Bed frames"],
    "Sofas": lambda r: _t(r, 2) == "Sofas & sectionals",
    "Sleeper sofas": lambda r: _t(r, 2) == "Sleeper sofas & sofa beds",
    "Armchairs": lambda r: _t(r, 2) == "Armchairs & accent chairs",
    "Ottomans & footstools": lambda r: _t(r, 2) == "Ottomans, footstools & pouffes",
    "Dining tables": lambda r: _t(r, 3) == "Dining tables",
    "Dining chairs": lambda r: _t(r, 3) == "Dining chairs",
    "Accent tables": lambda r: _t(r, 2) == "Accent tables",
    "Desks": lambda r: _t(r, 3) in {
        "Desks for home", "Standing desks", "Laptop tables", "Gaming Desks", "Desks for office"
    },
    "Desk chairs": lambda r: _t(r, 2) == "Desk chairs",
    "Bar furniture": lambda r: _t(r, 2) == "Bar furniture",
    "Benches": lambda r: _t(r, 2) == "Benches",
    "Bookcases & shelving": lambda r: _t(r, 3) in {
        "Bookshelves & bookcases", "Storage shelves & shelving units", "Cube storage"
    },
    "Dressers": lambda r: _t(r, 2) == "Dressers & storage drawers",
    "Wardrobes": lambda r: _t(r, 2) == "Armoires & wardrobes",
    "TV & media furniture": lambda r: _t(r, 2) == "TV & media furniture",
    "Rugs": lambda r: _t(r, 2) == "Rugs",
    "Wall art": lambda r: _t(r, 3) in {"Wall art", "Art posters and prints"},
    "Lamps": lambda r: _t(r, 3) in {"Table lamps", "Floor lamps", "Desk lamps"},
    "Mirrors": lambda r: _t(r, 2) == "Mirrors",
}

# title colour vocabulary: compounds / materials first, earliest match wins.
COLOR_PATTERNS = [
    (r"off-white", "white"), (r"high-gloss white", "white"),
    (r"gray-brown|grey-brown", "brown"), (r"black-brown", "brown"),
    (r"dark brown|dark-brown", "brown"), (r"light brown|light-brown", "brown"),
    (r"light gray|light grey|light-gray", "gray"), (r"dark gray|dark grey", "gray"),
    (r"light blue", "blue"), (r"dark blue", "blue"),
    (r"dark green|olive", "green"), (r"light green", "green"),
    (r"light beige", "beige"), (r"dark red", "red"),
    (r"stainless steel|chrome|nickel-plated|nickel plated", "silver"),
    (r"anthracite", "gray"), (r"gold-colou?r|brass", "gold"),
    (r"multicolou?r|multi-colou?r", "multicolor"),
    (r"pewter|pewter effect", "silver"),
    (r"\bbamboo\b|\brattan\b|\bbirch\b|\boak\b|\bpine\b|\bash\b|seagrass|water hyacinth", "natural"),
    (r"\bwalnut\b", "brown"), (r"clear glass|frosted glass|\bmirror\b", "clear"),
    (r"\bblack\b", "black"), (r"\bwhite\b", "white"), (r"\bgray\b|\bgrey\b", "gray"),
    (r"\bbrown\b", "brown"), (r"\bbeige\b", "beige"), (r"\bblue\b", "blue"),
    (r"\bgreen\b", "green"), (r"\byellow\b", "yellow"), (r"\bpink\b", "pink"),
    (r"\bred\b", "red"), (r"\bpurple\b|lilac", "purple"), (r"\borange\b", "orange"),
    (r"\bturquoise\b", "blue"), (r"\bgold\b", "gold"), (r"\bsilver\b", "silver"),
    (r"\bglass\b", "clear"), (r"\bnatural\b", "natural"),
]

# titles that mean "not a whole standalone product" — parts, accessories, sets
EXCLUDE_TITLE = re.compile(
    r"\b(?:covers?|hardware|midbeam|slats?|mattress(?:es)?|foundation|underframe|"
    r"door|insert|extension unit)\b"
    r"|\bshelf\b(?!\s+unit)"
    r"|\band \d+ (?:bar stools?|chairs?)\b",
    re.I,
)

MANUAL_COLOR: dict[str, str] = {}

# Hand-assigned style tags (1-3 of STYLES), keyed by product_id. If the sample
# changes, re-run once and fill in any product_id the script reports as untagged.
STYLE_TAGS: dict[str, str] = {
    # Beds
    "99392240": "traditional,scandinavian", "50506436": "scandinavian,minimalist",
    "89496865": "scandinavian,traditional", "69567528": "traditional,scandinavian",
    "79516661": "scandinavian,boho", "59577698": "traditional,mid-century",
    "79577697": "traditional,mid-century", "59577740": "traditional,scandinavian",
    "69567533": "traditional,scandinavian", "79441736": "boho,scandinavian",
    "50458911": "traditional,modern", "69437805": "minimalist,scandinavian",
    "19574395": "minimalist,mid-century", "19581838": "scandinavian,minimalist",
    "59560037": "minimalist,modern",
    # Sofas
    "89471493": "modern,minimalist", "09305619": "scandinavian,mid-century",
    "19304638": "scandinavian,modern", "99319216": "modern,scandinavian",
    "19389166": "modern,minimalist", "29442427": "mid-century,scandinavian",
    "19499787": "scandinavian,mid-century", "89449671": "scandinavian,mid-century",
    "09319254": "modern,scandinavian", "09514552": "scandinavian,mid-century",
    "59489574": "scandinavian,modern", "49575713": "modern,scandinavian",
    "19499688": "scandinavian,traditional", "40586117": "mid-century,modern",
    "69471413": "modern,boho",
    # Sleeper sofas
    "49575671": "modern,scandinavian", "39491323": "mid-century,modern",
    "99491259": "scandinavian,modern", "60541585": "scandinavian,modern",
    "39499654": "scandinavian,traditional", "69499657": "scandinavian,traditional",
    "79470248": "scandinavian,modern", "19491319": "mid-century,modern",
    "69491326": "mid-century,modern", "89542810": "modern,scandinavian",
    "09542885": "modern,scandinavian", "89491325": "mid-century,modern",
    "29542832": "modern,scandinavian", "70585079": "scandinavian,minimalist",
    "29491253": "scandinavian,modern",
    # Armchairs
    "90570821": "modern,boho", "60494249": "scandinavian,mid-century",
    "39551604": "mid-century,scandinavian", "69429122": "mid-century,scandinavian",
    "49502123": "mid-century,scandinavian", "10505028": "scandinavian,mid-century",
    "59487872": "traditional,mid-century", "90494587": "mid-century,modern",
    "90359829": "traditional,mid-century", "89502079": "mid-century,scandinavian",
    "79553842": "traditional,scandinavian", "80423576": "scandinavian,mid-century",
    "90359848": "traditional,mid-century", "89429178": "mid-century,scandinavian",
    "69395848": "mid-century,boho",
    # Ottomans & footstools
    "59514446": "scandinavian,mid-century", "99553855": "traditional,boho",
    "79387273": "mid-century,scandinavian", "19305968": "mid-century,scandinavian",
    "79387268": "mid-century,scandinavian", "39499753": "scandinavian,mid-century",
    "20586175": "traditional,mid-century", "59443430": "mid-century,scandinavian",
    "40586179": "mid-century,modern", "29499678": "scandinavian,modern",
    "39553858": "traditional,scandinavian", "79553861": "traditional,scandinavian",
    "10594760": "scandinavian,modern", "29336035": "mid-century,scandinavian",
    "79305965": "mid-century,scandinavian",
    # Dining tables
    "40556318": "modern,minimalist", "70593574": "scandinavian,minimalist",
    "59578513": "scandinavian,minimalist", "30434657": "traditional,scandinavian",
    "79579984": "mid-century,scandinavian", "40599940": "traditional,mid-century",
    "00593879": "traditional,mid-century", "80492942": "mid-century,modern",
    "00568728": "scandinavian,modern", "19578510": "scandinavian,modern",
    "60563780": "scandinavian,mid-century", "50576716": "traditional,scandinavian",
    "50386245": "mid-century,traditional", "99578511": "scandinavian,modern",
    "90280096": "minimalist,scandinavian",
    # Dining chairs
    "80530623": "modern,minimalist", "80582645": "industrial,modern",
    "10547052": "industrial,mid-century", "40369109": "traditional,scandinavian",
    "60359996": "modern,scandinavian", "50544867": "boho,traditional",
    "60530619": "modern,minimalist", "60334722": "modern,minimalist",
    "00606626": "scandinavian,traditional", "89599689": "traditional,mid-century",
    "20584435": "industrial,modern", "79399841": "modern,minimalist",
    "90538647": "mid-century,modern", "50457313": "modern,scandinavian",
    "40532134": "modern,minimalist",
    # Accent tables
    "20487873": "traditional,scandinavian", "20295930": "modern,minimalist",
    "50488734": "scandinavian,minimalist", "30565554": "traditional,scandinavian",
    "40530917": "modern,minimalist", "50531983": "traditional,modern",
    "50578555": "scandinavian,boho", "40578971": "modern,minimalist",
    "70489308": "traditional,mid-century", "00541418": "mid-century,modern",
    "60340389": "modern,minimalist", "20299829": "mid-century,scandinavian",
    "90491560": "traditional,scandinavian", "60538795": "modern,boho",
    "70319028": "minimalist,scandinavian",
    # Desks
    "10607357": "minimalist,modern", "30538202": "traditional,scandinavian",
    "60460838": "scandinavian,minimalist", "69591378": "modern,industrial",
    "59591374": "modern,industrial", "30553240": "scandinavian,mid-century",
    "30538198": "traditional,mid-century", "70538200": "traditional,scandinavian",
    "80483805": "minimalist,modern", "20541610": "modern,minimalist",
    "90493955": "minimalist,scandinavian", "80534701": "minimalist,modern",
    "90585101": "minimalist,scandinavian", "80541565": "scandinavian,minimalist",
    "00559026": "modern,minimalist",
    # Desk chairs
    "70503451": "modern", "49508243": "modern,minimalist",
    "29488571": "modern,minimalist", "30521862": "modern,industrial",
    "80489402": "modern", "20503284": "modern,minimalist",
    "10503454": "modern", "20571193": "boho,industrial",
    "39513928": "modern", "89508236": "modern,minimalist",
    "80487158": "scandinavian,mid-century", "49331904": "modern,industrial",
    "59331847": "modern,industrial", "10367461": "modern,mid-century",
    "90289172": "modern,industrial",
    # Bar furniture
    "59471786": "scandinavian,modern", "10602067": "scandinavian,boho",
    "40568255": "industrial,modern", "10122647": "traditional,scandinavian",
    "70246089": "modern,scandinavian", "40534798": "modern,mid-century",
    "10602072": "scandinavian,minimalist", "90511233": "mid-century,scandinavian",
    "50511230": "mid-century,scandinavian", "30515451": "minimalist,modern",
    "70498421": "modern,industrial", "60400745": "modern,minimalist",
    "90400517": "traditional,scandinavian", "49418836": "mid-century,modern",
    "89471761": "scandinavian,boho",
    # Benches
    "30551203": "boho,scandinavian", "20572786": "scandinavian,modern",
    "89443400": "mid-century,scandinavian", "60485339": "boho,scandinavian",
    "80565146": "mid-century,scandinavian", "70533542": "mid-century,modern",
    "50152703": "minimalist,scandinavian", "40340762": "traditional,scandinavian",
    "70152702": "minimalist,scandinavian", "79443405": "mid-century,scandinavian",
    "70245872": "traditional,scandinavian", "80512657": "boho,scandinavian",
    "80573957": "modern,minimalist", "80599325": "scandinavian,minimalist",
    "10572782": "scandinavian,boho",
    # Bookcases & shelving
    "69581906": "scandinavian,traditional", "99494724": "traditional,scandinavian",
    "99294517": "industrial,modern", "19581485": "traditional,scandinavian",
    "10409932": "minimalist,scandinavian", "09197605": "minimalist,scandinavian",
    "09573198": "minimalist,modern", "29613424": "modern,scandinavian",
    "79483613": "traditional,scandinavian", "10528464": "traditional,scandinavian",
    "89483542": "traditional,scandinavian", "80492782": "scandinavian,minimalist",
    "49571178": "scandinavian,minimalist", "49521070": "scandinavian,modern",
    "19483362": "traditional,scandinavian",
    # Dressers
    "70559297": "modern,scandinavian", "60483241": "scandinavian,minimalist",
    "80593597": "mid-century,modern", "20575803": "traditional",
    "30367441": "traditional,scandinavian", "00561246": "modern,scandinavian",
    "50559298": "modern,scandinavian", "10561769": "modern,minimalist",
    "80430746": "traditional,scandinavian", "20572833": "scandinavian,minimalist",
    "10576191": "traditional,scandinavian", "80510007": "traditional,scandinavian",
    "70299959": "traditional,scandinavian", "90559296": "modern,scandinavian",
    "50590915": "traditional,scandinavian",
    # Wardrobes
    "59572592": "modern,minimalist", "00453765": "minimalist,scandinavian",
    "29581630": "minimalist,scandinavian", "79581722": "minimalist,scandinavian",
    "99581943": "minimalist,scandinavian", "89572538": "modern,minimalist",
    "69572563": "traditional,minimalist", "00576139": "minimalist,scandinavian",
    "29572701": "modern,minimalist", "09590876": "modern",
    "00593841": "mid-century,modern", "40586805": "minimalist,scandinavian",
    "29572428": "modern,minimalist", "29579236": "traditional,minimalist",
    "89581731": "minimalist,scandinavian",
    # TV & media furniture
    "69565237": "modern,minimalist", "49576246": "scandinavian,modern",
    "30566049": "traditional,scandinavian", "70566052": "traditional,scandinavian",
    "70542749": "modern,minimalist", "59494660": "traditional,scandinavian",
    "99574971": "modern,minimalist", "79570281": "traditional,mid-century",
    "99572745": "scandinavian,minimalist", "19576224": "scandinavian,modern",
    "19576238": "scandinavian,modern", "90586638": "mid-century,scandinavian",
    "39569454": "minimalist,modern", "19508980": "modern,boho",
    "19563924": "mid-century,modern",
    # Rugs
    "50577650": "boho,modern", "50560065": "scandinavian,minimalist",
    "60519160": "boho,scandinavian", "10532927": "boho,traditional",
    "50425529": "minimalist,scandinavian", "70527051": "boho,scandinavian",
    "10576351": "scandinavian,minimalist", "30480357": "scandinavian,minimalist",
    "10514179": "boho,traditional", "80541481": "scandinavian,boho",
    "20536208": "boho,modern", "00277395": "boho,scandinavian",
    "30600939": "modern,scandinavian", "30575303": "traditional,boho",
    "60578017": "modern,boho",
    # Wall art
    "90602271": "modern", "90567970": "traditional,scandinavian",
    "40583557": "minimalist,modern", "80601917": "modern",
    "90570656": "boho,modern", "00465773": "traditional,scandinavian",
    "50554502": "modern,minimalist", "40602018": "scandinavian,minimalist",
    "10601992": "boho,modern", "80578912": "traditional",
    "39508917": "modern", "90590758": "minimalist,modern",
    "10570537": "minimalist,modern", "30601991": "traditional,boho",
    "20602000": "boho,traditional",
    # Lamps
    "80585936": "mid-century,modern", "70437828": "modern,mid-century",
    "20546453": "modern,industrial", "50477052": "modern,minimalist",
    "40448611": "modern,minimalist", "10464283": "mid-century,traditional",
    "60573576": "scandinavian,mid-century", "70437814": "modern,minimalist",
    "00323887": "traditional,industrial", "80494328": "traditional,mid-century",
    "59525831": "modern,minimalist", "60518410": "minimalist,boho",
    "70488295": "modern,mid-century", "80358496": "industrial,modern",
    "00331383": "traditional,industrial",
    # Mirrors
    "20591596": "scandinavian,mid-century", "60503791": "mid-century,modern",
    "24524485": "modern,industrial", "20503774": "minimalist,modern",
    "30503778": "minimalist,modern", "70601786": "modern,boho",
    "10591587": "mid-century,scandinavian", "10250084": "modern,minimalist",
    "60506129": "minimalist,modern", "90510993": "modern,scandinavian",
    "30501802": "traditional,boho", "00541913": "boho,traditional",
    "90552332": "minimalist,modern", "80507217": "traditional,scandinavian",
    "50507148": "traditional,boho",
}


def clean_name(title: str) -> str:
    return re.sub(r"\s*-\s*IKEA US\s*$", "", title).strip()


def dominant_color(title: str, pid: str) -> str | None:
    text = title.lower()
    best_pos, best = len(text) + 1, None
    for pat, col in COLOR_PATTERNS:
        m = re.search(pat, text)
        if m and m.start() < best_pos:
            best_pos, best = m.start(), col
    # posters / pictures carry no single colour word -> treat as multicolor
    return best or MANUAL_COLOR.get(pid) or "multicolor"


def main() -> None:
    rows = [json.loads(line) for line in RAW.open()]

    # assign each row to the first type it matches (skipping parts / covers)
    buckets: dict[str, list] = {name: [] for name in TYPES}
    for r in rows:
        if EXCLUDE_TITLE.search(r["title"]):
            continue
        for name, fn in TYPES.items():
            if fn(r):
                buckets[name].append(r)
                break

    import random

    out = []
    for name, items in buckets.items():
        rng = random.Random(SEED)
        picked = rng.sample(items, min(PER_TYPE, len(items)))
        for r in picked:
            pid = r["product_id"]
            out.append({
                "product_id": pid,
                "name": clean_name(r["title"]),
                "type": name,
                "price_usd": round(float(r["price"]), 2),
                "dominant_color": dominant_color(r["title"], pid),
                "styles": [s for s in STYLE_TAGS.get(pid, "").split(",") if s],
                "description": r["description"].strip(),
                "image": f"images/{pid}.jpg",
                "image_src": r["image_urls"][0],
                "product_url": r["source_url"],
            })

    missing_c = [o["product_id"] for o in out if not o["dominant_color"]]
    if missing_c:
        print(f"NO dominant_color ({len(missing_c)}): add to MANUAL_COLOR")
        for o in out:
            if not o["dominant_color"]:
                print(f"  {o['product_id']}: {o['name']}")

    untagged = [o["product_id"] for o in out if not o["styles"]]
    bad = {s for o in out for s in o["styles"] if s not in STYLES}
    if bad:
        raise SystemExit(f"unknown style tag(s): {sorted(bad)}")
    if untagged:
        print(f"style tags missing for {len(untagged)} items — add to STYLE_TAGS:")
        for o in out:
            if not o["styles"]:
                print(f"  {o['product_id']}: {o['name']} ({o['type']})")
        raise SystemExit(1)

    body = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    OUT.write_text(body)
    (HERE / "backend" / "data" / "catalog.json").write_text(body)

    from collections import Counter
    print(f"\nwrote {OUT.name} + backend/data/catalog.json: {len(out)} items, {len(buckets)} types")
    short = {n: len(v) for n, v in buckets.items() if len(v) < PER_TYPE}
    if short:
        print("types with < 15:", short)
    sc = Counter(s for o in out for s in o["styles"])
    print("style counts:", dict(sc.most_common()))
    print("color counts:", dict(Counter(o["dominant_color"] for o in out).most_common()))


if __name__ == "__main__":
    main()
