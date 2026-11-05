"""Create a balanced dorm subset from official ABO metadata, entirely offline."""
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from collections import Counter
from pathlib import Path

from app.catalogue_import import read_records
from app.database import utcnow_iso
from app.services.abo_dorm import RULES, RULE_VERSION, select_dorm_record


def build_subset(path: Path, per_category: int | None = None):
    candidates = {bucket: {} for bucket in RULES}
    scanned = 0
    for raw in read_records(path):
        scanned += 1
        record = select_dorm_record(raw)
        if record:
            candidates[record.category][record.external_product_id] = record
    selected = []
    for bucket, records in candidates.items():
        # Stable sampling avoids taking only the first brand or archive shard.
        ranked = sorted(records.values(), key=lambda r: (
            r.metadata["dorm_selection"]["size_status"] != "measured",
            hashlib.sha256(r.external_product_id.encode()).hexdigest()))
        selected.extend(ranked[:per_category or RULES[bucket].quota])
    report = {
        "rule_version": RULE_VERSION, "source": "Amazon Berkeley Objects",
        "source_url": "https://amazon-berkeley-objects.s3.amazonaws.com/index.html",
        "created_at": utcnow_iso(), "research_only": True,
        "scanned_listings": scanned, "selected_products": len(selected),
        "eligible_by_category": {k: len(v) for k, v in candidates.items()},
        "selected_by_category": dict(Counter(r.category for r in selected)),
        "size_status": dict(Counter(r.metadata["dorm_selection"]["size_status"] for r in selected)),
        "selection_rules": {bucket: {"quota": per_category or rule.quota,
            "max_footprint_inches": rule.footprint, "max_height_inches": rule.height,
            "reason": rule.reason} for bucket, rule in RULES.items()},
        "limitations": ["No current prices or inventory", "No downloaded image pixels or 3D models",
                        "Dimensions are source metadata, not independent verification",
                        "School rules, bed size, and actual room clearance need separate checking"],
    }
    return selected, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path, default=Path(f"data/research/abo-dorm-v{RULE_VERSION}"))
    parser.add_argument("--per-category", type=int, help="Override each category quota")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.per_category is not None and args.per_category < 1:
        parser.error("--per-category must be positive")
    files = ["products.jsonl", "manifest.json", "LICENSE-CC-BY-4.0.txt", "ATTRIBUTION.md"]
    if not args.dry_run and any((args.output / name).exists() for name in files):
        parser.error("Output already exists; choose a new --output directory to preserve existing data")
    # Read the accompanying license before creating any output files.
    with tarfile.open(args.path) as archive:
        license_file = archive.extractfile("LICENSE-CC-BY-4.0.txt")
        if license_file is None:
            parser.error("Official archive license is missing")
        license_data = license_file.read()
    records, manifest = build_subset(args.path, args.per_category)
    if not args.dry_run:
        # Output is generated data. Existing files are never replaced.
        args.output.mkdir(parents=True, exist_ok=True)
        with (args.output / "products.jsonl").open("x", encoding="utf-8") as stream:
            for record in records:
                stream.write(record.model_dump_json() + "\n")
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (args.output / "LICENSE-CC-BY-4.0.txt").write_bytes(license_data)
        (args.output / "ATTRIBUTION.md").write_text(
            "# Amazon Berkeley Objects dorm subset\n\n"
            "Data: Amazon.com. Dataset construction: Matthieu Guillaumin, Thomas Dideriksen, "
            "Kenan Deng, Himanshu Arora, Arnab Dhua, Xi (Brian) Zhang, Tomas Yago-Vicente, "
            "Jasmine Collins, Shubham Goel, and Jitendra Malik.\n\n"
            "Source: https://amazon-berkeley-objects.s3.amazonaws.com/index.html\n"
            "License: CC BY 4.0; see LICENSE-CC-BY-4.0.txt.\n\n"
            "Changes by DormWrapper: US marketplace and English selection, dorm category and "
            "size filtering, balanced sampling, unit conversion, and normalized metadata. "
            "Research use only in this project. Amazon does not endorse this subset.\n",
            encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
