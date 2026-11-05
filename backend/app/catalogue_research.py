"""Search internal research records from the command line; never exposed by the API."""
import argparse
import json
from app.database import db_session, init_db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    init_db()
    with db_session() as db:
        rows = db.execute("""SELECT normalized_json FROM research_products
            WHERE instr(lower(name || ' ' || category), lower(?)) > 0
            ORDER BY name, external_product_id LIMIT ?""", (args.query, args.limit))
        print(json.dumps([json.loads(row[0]) for row in rows], indent=2))


if __name__ == "__main__":
    main()
