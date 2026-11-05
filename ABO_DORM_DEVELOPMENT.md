# Amazon Berkeley Objects dorm development subset

The version 2 subset contains 256 products selected from the already downloaded official ABO metadata archive. It is intended for retrieval and attribute experiments for DormWrapper. It does not contain live Amazon shopping data. Use the version 2 paths below; the intermediate version 1 files were preserved and are not the recommended development bundle.

## Local files

- `backend/data/research/abo-dorm-v2/products.jsonl`: normalized product metadata, approximately 426 KB.
- `backend/data/research/abo-dorm-v2/manifest.json`: category counts, selection rules, and limitations.
- `backend/data/research/abo-dorm-v2/ATTRIBUTION.md`: attribution and modification notice.
- `backend/data/research/abo-dorm-v2/LICENSE-CC-BY-4.0.txt`: license copied from the official archive.
- `backend/data/research/abo-dorm-v2.db`: separate searchable SQLite research database.

These generated files are ignored by Git. The selection code and this guide are versioned so another developer can reproduce the subset.

## Contents

| Category | Products | Maximum furniture footprint and height |
| --- | ---: | --- |
| Compact study desks | 30 | 48 × 24 inches; 36 inches high |
| Desk chairs | 30 | 28 × 28 inches; 50 inches high |
| Storage and shelving | 37 | 36 × 18 inches; 60 inches high |
| Lamps | 40 | 20 × 20 inches; 65 inches high |
| Small bedside and side tables | 40 | 24 × 24 inches; 32 inches high |
| Organizers | 39 | 24 × 18 inches; 40 inches high when dimensions are available |
| Throws and decorative pillows | 40 | No bed-size or fit claim |

The target quotas total 300. The result is 256 because only 30 desks and 37 storage products met the rules, and only 39 organizers qualified. Category quotas are upper bounds; the selector preserves the size and relevance requirements when fewer products qualify.

Only `amazon.com` listings with English names and a main image identifier are considered. Category and title matching select relevant products. Exclusions cover outdoor furniture, nursery and children's products, pet furniture, sofas, mattresses, bed frames, executive furniture, replacement-only parts, and wall-mounted products. Selection is conservative and may omit useful items.

Desks, chairs, storage furniture, and small tables require complete usable dimensions. Inches, centimeters, millimeters, meters, and feet are supported. Horizontal dimensions are compared in size order so a source's width/length convention does not incorrectly reject rotated footprints. Known oversized measurements exclude accessories too. Four selected accessories have incomplete dimensions and are marked `manual_review`; the other 252 have complete source dimensions. Source dimensions have not been independently verified.

Stable sampling within categories uses a hash of product ID and favors complete dimensions. Each product carries its category, selection reason, normalized inch measurements, size status, and rule version under `metadata.dorm_selection`. The original dimensions, materials, descriptions, image IDs, and model IDs remain available where supplied.

## Search the development database

Run from `backend` with the backend Python environment activated:

```sh
DATABASE_URL=data/research/abo-dorm-v2.db python -m app.catalogue_research desks --limit 5
DATABASE_URL=data/research/abo-dorm-v2.db python -m app.catalogue_research lighting --limit 5
DATABASE_URL=data/research/abo-dorm-v2.db python -m app.catalogue_research organizer --limit 5
```

Every record is `research_only`, uses source type `amazon_abo`, has a null price, and has unknown availability. The database contains 256 research records and zero public catalog records. The regular app's database remains separate.

## Reproduce or change the subset

The source is `backend/data/research/abo-listings.tar`, obtained from the [official ABO dataset](https://amazon-berkeley-objects.s3.amazonaws.com/index.html). This task reused that local archive; no additional dataset download was needed.

```sh
# Preview category coverage without writing a subset.
python -m app.abo_dorm_subset data/research/abo-listings.tar --dry-run

# Create the default subset on a new machine.
python -m app.abo_dorm_subset data/research/abo-listings.tar

# Create a different subset without overwriting the existing one.
python -m app.abo_dorm_subset data/research/abo-listings.tar --per-category 15 --output data/research/abo-dorm-small

# Import or refresh the dedicated research database.
DATABASE_URL=data/research/abo-dorm-v2.db python -m app.catalogue_import feed data/research/abo-dorm-v2/products.jsonl
```

The builder refuses to replace an existing output bundle. Change `--output` for another selection. Imports update matching products without removing earlier records; use a distinct `DATABASE_URL` when comparing different subsets.

Category and size rules are in `backend/app/services/abo_dorm.py`. The dataset builder is `backend/app/abo_dorm_subset.py`. Selection tests cover oversized and missing furniture measurements, excluded products, marketplace boundaries, lighting category handling, unit conversion, duplicate handling, and reproducible sampling.

## Development limits

The subset contains image identifiers, not downloaded image pixels or 3D files. No current prices, inventory, or verified purchase URLs are supplied. It supports metadata search and attribute experiments now; visual similarity experiments need image data as a separate step. Room clearance, university rules, and whether a student already has a desk or chair should influence later recommendations.

ABO data is credited to Amazon.com and the dataset authors in `ATTRIBUTION.md`. The official archive supplies CC BY 4.0. DormWrapper filtered, sampled, converted units, and normalized the metadata; attribution and the modification notice accompany the local subset.
