# test_suites.py
# Every built-in suite fixture must load and have the expected structure.

import json
from pathlib import Path

import pytest

SUITES_DIR = Path(__file__).resolve().parent.parent / "suites"

EXPECTED_SUITES = {
    "coding": {"prompt", "unit_tests", "expected_function"},
    "reasoning": {"prompt", "ground_truth", "context"},
    "rag_faithfulness": {"context", "question", "ground_truth"},
    "safety": {"prompt", "expected_behavior", "harm_category"},
}


@pytest.mark.parametrize("suite_id", sorted(EXPECTED_SUITES.keys()))
def test_suite_file_loads_and_has_five_items(suite_id):
    path = SUITES_DIR / f"{suite_id}.json"
    assert path.exists(), f"missing suite file: {path}"

    items = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(items, list)
    assert len(items) == 5

    required_keys = EXPECTED_SUITES[suite_id]
    for item in items:
        assert "id" in item
        assert required_keys.issubset(item.keys())


def test_all_item_ids_are_unique_within_each_suite():
    for suite_id in EXPECTED_SUITES:
        path = SUITES_DIR / f"{suite_id}.json"
        items = json.loads(path.read_text(encoding="utf-8"))
        ids = [item["id"] for item in items]
        assert len(ids) == len(set(ids))
