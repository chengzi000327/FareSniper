import json
from pathlib import Path


def test_dataset_has_50_cases():
    p = Path("backend/eval/datasets/e2e_50.jsonl")
    cases = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    assert len(cases) == 50


def test_each_case_has_required_fields():
    p = Path("backend/eval/datasets/e2e_50.jsonl")
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        assert {"case_id", "category", "input_sequence", "expected_intent", "pass_criteria"}.issubset(c)
