"""Test meaningful selection boundaries, unit conversion, and reproducibility."""
import json

import pytest

from app.abo_dorm_subset import build_subset
from app.services.abo_dorm import dimensions_inches, select_dorm_record


def listing(name="Compact writing desk", **changes):
    return {
        "item_id": "B_DESK", "domain_name": "amazon.com", "main_image_id": "image",
        "item_name": [{"language_tag": "en_US", "value": name}],
        "node": [{"node_name": "/Categories/Furniture/Home Office Desks"}],
        "item_dimensions": {axis: {"unit": "inches", "value": value}
                            for axis, value in {"width": 40, "length": 20, "height": 30}.items()},
        **changes,
    }


def test_compact_desk_keeps_research_boundary_and_selection_reason():
    record = select_dorm_record(listing())
    assert record.category == "desks" and record.room_type == "student_dorm"
    assert record.research_only and record.price is None
    assert record.metadata["dorm_selection"]["size_status"] == "measured"
    assert record.metadata["dorm_selection"]["dimensions_inches"]["width"] == 40


@pytest.mark.parametrize("name", ["Executive writing desk", "Outdoor writing desk",
                                 "Kids writing desk", "Replacement desk cover only"])
def test_unsuitable_products_excluded(name):
    assert select_dorm_record(listing(name)) is None


@pytest.mark.parametrize("changes", [
    {"domain_name": "amazon.co.uk"}, {"main_image_id": None},
    {"item_dimensions": {}},
    {"item_dimensions": {"width": {"unit": "inches", "value": 60},
                         "length": {"unit": "inches", "value": 30},
                         "height": {"unit": "inches", "value": 30}}},
])
def test_missing_or_oversized_furniture_excluded(changes):
    assert select_dorm_record(listing(**changes)) is None


def test_table_lamps_survive_ceiling_fans_parent_category():
    record = select_dorm_record(listing("Blue table lamp",
        node=[{"node_name": "/Categories/Lighting & Ceiling Fans/Lamps & Shades/Table Lamps"}],
        item_dimensions={axis: {"unit": "inches", "value": value}
                         for axis, value in {"width": 10, "length": 10, "height": 20}.items()}))
    assert record.category == "lighting"


def test_missing_accessory_dimensions_require_manual_review():
    record = select_dorm_record(listing("Desk organizer", node=[], item_dimensions={}))
    assert record.category == "organizers"
    assert record.metadata["dorm_selection"]["size_status"] == "manual_review"


@pytest.mark.parametrize("name", ["Razor with shower hanger", "Arizona photo with wood hanger",
                                 "Wall Mount Hanger Holder for Guitar"])
def test_incidental_hanger_mentions_are_not_clothing_organizers(name):
    assert select_dorm_record(listing(name, node=[])) is None


def test_category_takes_priority_over_incidental_storage_basket_in_title():
    record = select_dorm_record(listing("Round side table with fabric storage basket",
        node=[{"node_name": "/Categories/Furniture/Side Tables"}],
        item_dimensions={axis: {"unit": "inches", "value": 20}
                         for axis in ("width", "length", "height")}))
    assert record.category == "small_tables"


def test_dimensions_convert_units_and_ignore_invalid_values():
    dims = dimensions_inches({"item_dimensions": {
        "width": {"normalized_value": {"unit": "centimeters", "value": 101.6}},
        "length": {"unit": "feet", "value": 2},
        "height": {"unit": "inches", "value": float("nan")}}})
    assert dims == {"width": 40, "length": 24}


def test_balanced_sampling_deduplicates_and_is_independent_of_input_order(tmp_path):
    records = [listing(item_id=f"B_{i}") for i in range(8)]
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps(records + [records[0]]))
    second.write_text(json.dumps(list(reversed(records))))
    a, report = build_subset(first, per_category=3)
    b, _ = build_subset(second, per_category=3)
    assert [r.external_product_id for r in a] == [r.external_product_id for r in b]
    assert report["eligible_by_category"]["desks"] == 8
    assert report["selected_by_category"] == {"desks": 3}
