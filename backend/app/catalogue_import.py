"""Offline import CLI. Reads ABO tar shards without extracting files."""
from __future__ import annotations

import argparse
import gzip
import io
import json
import tarfile
from pathlib import Path
from app.database import db_session, init_db
from app.services.catalogue_repository import ingest, validate_destination
from app.services.catalogue_sources import ADAPTERS


def _rows(stream, suffix: str):
    first = stream.read(1)
    while first and first.isspace():
        first = stream.read(1)
    if not first:
        return
    if first == "[":
        data = json.loads(first + stream.read())
        if not isinstance(data, list):
            raise ValueError("JSON input must be an array of products")
        yield from data
    else:
        yield json.loads(first + stream.readline())
        for line in stream:
            if line.strip():
                yield json.loads(line)


def read_records(path: Path):
    """JSON arrays or streaming JSONL/JSONL.GZ, including ABO listings.tar."""
    if path.is_dir():
        for file in sorted(path.rglob("*.json*")):
            yield from read_records(file)
    elif tarfile.is_tarfile(path):
        with tarfile.open(path, mode="r|*") as archive:
            for member in archive:
                if not member.isfile() or not member.name.endswith((".json", ".jsonl", ".json.gz", ".jsonl.gz")):
                    continue
                raw = archive.extractfile(member)
                if raw is None:
                    continue
                compressed = member.name.endswith(".gz")
                source = gzip.GzipFile(fileobj=raw) if compressed else raw
                suffix = Path(member.name.removesuffix(".gz")).suffix
                with io.TextIOWrapper(source, encoding="utf-8") as stream:
                    yield from _rows(stream, suffix)
    else:
        opener = gzip.open if path.suffix == ".gz" else open
        suffix = Path(str(path).removesuffix(".gz")).suffix
        with opener(path, "rt", encoding="utf-8") as stream:
            yield from _rows(stream, suffix)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=ADAPTERS)
    parser.add_argument("path", type=Path)
    parser.add_argument("--limit", type=int, help="Maximum normalized products to import")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count without database writes")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    records = ADAPTERS[args.source]().records(read_records(args.path))
    if args.limit:
        from itertools import islice
        records = islice(records, args.limit)
    if args.dry_run:
        counts = {"catalogue": 0, "research": 0}
        for record in records:
            counts[validate_destination(record)] += 1
    else:
        init_db()
        with db_session() as db:
            counts = ingest(db, records)
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
