# Product sources and internal research

The first four catalog recommendations are implemented: preserve IKEA, support multiple retailers, add adapters, and use Amazon Berkeley Objects (ABO) for internal experiments.

## Existing catalog and migration

The app continues using SQLite. `init_db()` adds fields without replacing the database or changing product IDs. Existing saved designs retain their item references. IKEA's eight-digit product ID is stored separately from the internal integer ID, preserving leading zeros in image paths.

`python -m app.seed_data` adds missing IKEA records through the IKEA adapter without overwriting existing products. To intentionally update product data, use the import command below. Imports update matching retailer/external-ID pairs in place. They do not remove records omitted from a new feed. Mark products `out_of_stock` or `discontinued` to exclude them from new searches and recommendations while preserving saved designs.

Existing IKEA records remain a prototype snapshot with unknown availability and unreviewed permissions. The migration does not mark their prices or rights as verified.

## Normalized product fields

All adapters return `ProductRecord` from `backend/app/services/catalogue_sources.py`. Identity is `(retailer, external_product_id)`; the internal database ID remains the reference used by recommendations and saved designs.

Records carry name, category, price, ISO currency, colors, styles, materials, dimensions, room type, availability, product/image/affiliate URLs, source type, license status, ingestion time, and last verification time. Dimensions preserve supplied values and units. Import time is not a statement that price or inventory was checked. Source adapters should provide `last_verified_at` only after actual verification.

Public imports need a price. New public sources also need `license_status: "approved"`, an assertion by the operator that use is permitted. This flag does not itself grant permission. The existing IKEA snapshot is grandfathered for prototype compatibility. Research products may have a null price and are stored exclusively in `research_products`.

## Source adapters and imports

Run commands from `backend` with the backend Python environment activated:

```sh
python -m app.seed_data
python -m app.catalogue_import ikea data/catalog.json --dry-run
python -m app.catalogue_import ikea data/catalog.json
python -m app.catalogue_import feed /absolute/path/permitted-feed.jsonl --dry-run
python -m app.catalogue_import feed /absolute/path/permitted-feed.jsonl
```

Imports accept JSON arrays, JSON Lines, gzip compressed files, directories of shards, and tar archives containing supported shards. Archives are streamed without extracting files. The whole import runs in one transaction: an invalid record rolls back the import. `--limit 100` limits normalized products, after adapter filtering. Re-importing the same source updates records without duplicating them.

Available adapters:

| Adapter | Input | Destination |
| --- | --- | --- |
| `ikea` | Existing `product_id` / `type` / `price_usd` snapshot | Public prototype catalog |
| `feed` | Records already mapped to `ProductRecord` | Public catalog or research, depending on the record |
| `abo` | Official ABO listings | Internal research table |

Future retailer API adapters implement `SourceAdapter`, translate responses into `ProductRecord`, and yield pages to `ingest()`. Remote requests, provider credentials, retries, and provider-specific limits belong in the adapter. API routes and recommendation code use the local catalog repository and require no retailer-specific changes. Live Amazon, IKEA, and Temu API connections have not been added.

## Public retrieval

`GET /api/catalogue` supports `retailer`, `q`, `style`, `category`, `max_price`, `currency`, `limit` (1–1000, default 300), and `offset`. The response remains an array, with additional product metadata. Search is case-insensitive literal substring matching; style matching uses exact comma-separated tags.

```text
/api/catalogue?retailer=ikea&q=desk&max_price=150&currency=USD&limit=20
```

Generation uses the same repository, limits candidates to affordable USD products, and excludes known unavailable products. The current room budget is USD; no currency conversion is performed. If no affordable products match the requested style, it falls back to affordable USD products across styles. Research records never become recommendation candidates.

Product cards show retailer and currency, support HTTPS product images, and prefer an affiliate link if supplied. Locally stored product photos remain available to image generation. Remote product images are displayed by the browser; the backend currently uses remote-image products as text references rather than downloading them for the image model.

## Amazon Berkeley Objects experiments

A smaller subset of 256 products applicable to dorm development is available separately. See [ABO_DORM_DEVELOPMENT.md](ABO_DORM_DEVELOPMENT.md) for contents, selection rules, and search commands.

The official metadata archive has been downloaded locally to `backend/data/research/abo-listings.tar`. The import processed 6,974 furniture listings and retained 6,973 unique products in `backend/data/research/abo.db`; one repeated product identity was merged. Both paths are ignored by Git and must be reproduced on another machine if needed.

Search this database independently of the app:

```sh
DATABASE_URL=data/research/abo.db python -m app.catalogue_research desk --limit 5
DATABASE_URL=data/research/abo.db python -m app.catalogue_research sofa --limit 5
```

To recreate the import after obtaining the official archive:

```sh
DATABASE_URL=data/research/abo.db python -m app.catalogue_import abo data/research/abo-listings.tar
```

The adapter selects English furniture listings by category or product type. It keeps dimensions, materials, descriptions, styles, and original image/model identifiers. It does not invent prices, stock, purchase links, or image URLs. The full dataset includes other categories that are intentionally filtered out. The record filter is a practical starting point for furniture research, not a comprehensive category taxonomy.

Useful experiments include category coverage, attribute completeness, keyword retrieval, and later image similarity using the supplied image IDs. Image pixels and 3D models have not been downloaded. No paid API, model calls, or vector database are required for the current import and search workflow.

## Provenance

ABO source: [official dataset page](https://amazon-berkeley-objects.s3.amazonaws.com/index.html). The downloaded archive includes `LICENSE-CC-BY-4.0.txt`, and its `listings/README.md` identifies the data as CC BY 4.0. This provides direct provenance beyond the conflicting AWS registry label noted in the earlier research. Attribution and modification notices must accompany reuse. ABO remains internal regardless of a record's `research_only` flag when `source_type` is `amazon_abo`, because it is a static research dataset with no current price or inventory.

Data, including images and 3D models, is credited to Amazon.com. Dataset construction is credited to Matthieu Guillaumin, Thomas Dideriksen, Kenan Deng, Himanshu Arora, Arnab Dhua, Xi (Brian) Zhang, Tomas Yago-Vicente, Jasmine Collins, Shubham Goel, and Jitendra Malik, as listed on the official dataset page. The local adapter filters to furniture and English attributes and reformats metadata into the DormWrapper schema.

## Verification

`python -m pytest -q` includes migration preservation, source identity and upserts, metadata round trips, exact style matching, budget/currency/stock filtering, research exclusion, archive parsing without extraction, and API pagination. Existing authentication, ownership, generation, and saved-design tests remain part of the suite.
