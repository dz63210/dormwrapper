"""Conservative, reproducible selection rules for a dorm development dataset."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.services.catalogue_sources import AboAdapter, ProductRecord, _english_values

RULE_VERSION = 2


@dataclass(frozen=True)
class DormRule:
    quota: int
    leaves: frozenset[str]
    title_pattern: str
    # Sorted horizontal sides avoid assuming length always means depth.
    footprint: tuple[float, float] | None
    height: float | None
    reason: str


RULES = {
    "lighting": DormRule(40, frozenset({"desk lamps", "table lamps", "floor lamps", "reading lamps"}),
        r"\b(?:desk|table|floor|reading) lamp\b", (20, 20), 65,
        "Task or ambient lighting with a small footprint."),
    "organizers": DormRule(60, frozenset({"baskets & bins", "hangers", "standard hangers",
        "over the door shoe organisers", "shoe racks", "desk organizers", "drawer organizers",
        "storage bins", "clothing & wardrobe storage", "home storage & organisation"}),
        r"\b(?:storage (?:bins?|baskets?|cubes?)|desk organi[sz]ers?|drawer organi[sz]ers?|shoe racks?|(?:clothes|clothing|coat|closet|velvet|pants|skirt|suit) hangers?|laundry hampers?)\b",
        (24, 18), 40, "Small organizers for desks, clothing, and everyday storage."),
    "textiles": DormRule(40, frozenset({"throws", "throw pillows", "decorative pillows",
        "decorative pillowcases", "lumbar pillows", "blankets, throws & patchwork quilts"}),
        r"\b(?:throw (?:pillow|blanket)|decorative pillow|fleece throw)\b",
        None, None, "Soft furnishings for a bed or study seat; no mattress or bed-size claim."),
    "desks": DormRule(30, frozenset({"desks", "home office desks", "computer workstations"}),
        r"\b(?:writing|computer|study|home office|folding) desk\b",
        (48, 24), 36, "Optional compact study desk for rooms without a supplied desk."),
    "desk_chairs": DormRule(30, frozenset({"desk chairs", "home office desk chairs", "task chairs"}),
        r"\b(?:office|desk|task|computer) chair\b",
        (28, 28), 50, "Compact study chair; clearance and room layout still need checking."),
    "storage": DormRule(60, frozenset({"bookcases", "shelf", "shelves", "shelving & storage",
        "storage cabinets", "utility carts", "storage trolleys", "drawers", "home office storage"}),
        r"\b(?:bookcase|bookshelf|storage cart|utility cart|shelving unit|storage cabinet)\b",
        (36, 18), 60, "Freestanding storage with a narrow footprint."),
    "small_tables": DormRule(40, frozenset({"end tables", "side tables", "bedside tables",
        "nightstands", "nesting tables"}), r"\b(?:end table|side table|bedside table|nightstand)\b",
        (24, 24), 32, "Compact surface beside a bed or study seat."),
}

EXCLUDED = re.compile(
    r"\b(?:patio|outdoor|garden|crib|nursery|toddler|kids|children|cat|dog|pet|"
    r"sofa|sectional|recliner|dining|headboard|bed frame|mattress|executive|"
    r"wall[ -]mount(?:ed)?|chandelier|lamp shade|lampshade|"
    r"replacement|cover only|covers only|candle|heater|hot plate)\b", re.I)

UNIT_INCHES = {"inch": 1, "inches": 1, "in": 1, "centimeter": 1 / 2.54,
               "centimeters": 1 / 2.54, "cm": 1 / 2.54, "millimeter": 1 / 25.4,
               "millimeters": 1 / 25.4, "mm": 1 / 25.4, "meter": 100 / 2.54,
               "meters": 100 / 2.54, "m": 100 / 2.54, "foot": 12, "feet": 12, "ft": 12}


def dimensions_inches(raw: dict) -> dict[str, float]:
    result = {}
    for axis, measurement in (raw.get("item_dimensions") or {}).items():
        if not isinstance(measurement, dict):
            continue
        normalized = measurement.get("normalized_value") or measurement
        factor = UNIT_INCHES.get(str(normalized.get("unit", "")).lower())
        try:
            value = float(normalized.get("value"))
        except (TypeError, ValueError):
            continue
        if factor and math.isfinite(value) and value > 0:
            result[axis] = round(value * factor, 3)
    return result


def select_dorm_record(raw: dict) -> ProductRecord | None:
    # Restrict to one marketplace so ASIN identity is unambiguous in this subset.
    if raw.get("domain_name") != "amazon.com":
        return None
    names = _english_values(raw.get("item_name"))
    if not names or not raw.get("item_id") or not raw.get("main_image_id"):
        return None
    name = names[0]
    nodes = [n.get("node_name") or n.get("path") or "" for n in raw.get("node", []) or []
             if isinstance(n, dict)]
    if EXCLUDED.search(name + " " + " ".join(nodes)):
        return None
    leaves = {n.rsplit("/", 1)[-1].lower() for n in nodes}
    dims = dimensions_inches(raw)
    matched = [bucket for bucket, rule in RULES.items() if leaves.intersection(rule.leaves)]
    if not matched:
        matched = [bucket for bucket, rule in RULES.items() if re.search(rule.title_pattern, name, re.I)]
    for bucket in matched:
        rule = RULES[bucket]
        complete = all(axis in dims for axis in ("width", "length", "height"))
        if rule.footprint:
            # Large furniture must have all three measurements to qualify.
            if bucket in {"desks", "desk_chairs", "storage", "small_tables"} and not complete:
                return None
            if "width" in dims or "length" in dims:
                measured = sorted((dims[axis] for axis in ("width", "length") if axis in dims), reverse=True)
                if any(value > maximum for value, maximum in zip(measured, rule.footprint)):
                    return None
            if rule.height and dims.get("height", 0) > rule.height:
                return None
        record = AboAdapter.make_record(raw, name, bucket)
        record.room_type = "student_dorm"
        record.metadata["dorm_selection"] = {
            "bucket": bucket, "reason": rule.reason,
            "dimensions_inches": dims,
            "size_status": "measured" if complete else "manual_review",
            "rule_version": RULE_VERSION,
            "requires_room_policy_check": bucket == "storage",
        }
        return record
    return None
