import json

import pytest

from eval.run_eval import DEFAULT_CASES, evaluate_case, load_cases, main, run_suite
from src.main import SONGS_CSV
from src.recommender import load_songs


@pytest.fixture(scope="module")
def catalog():
    return load_songs(str(SONGS_CSV))


def test_committed_golden_set_passes_completely(catalog):
    cases = load_cases(DEFAULT_CASES)

    assert run_suite(cases, catalog) == 0


def test_golden_set_covers_every_status(catalog):
    statuses = {case.get("expect_status") for case in load_cases(DEFAULT_CASES)}

    assert statuses == {"accepted", "best_effort", "infeasible", "rejected"}


def test_evaluate_case_reports_a_failing_expectation(catalog):
    case = {"name": "deliberately wrong", "query": "chill lofi", "expect_status": "rejected"}

    _, failures = evaluate_case(case, catalog)

    assert failures and "expected 'rejected'" in failures[0]


def test_load_cases_rejects_a_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_cases(tmp_path / "nope.json")


def test_load_cases_rejects_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError):
        load_cases(bad)


def test_load_cases_rejects_a_case_without_a_query(tmp_path):
    bad = tmp_path / "incomplete.json"
    bad.write_text(json.dumps({"cases": [{"name": "nameless"}]}), encoding="utf-8")

    with pytest.raises(ValueError):
        load_cases(bad)


def test_main_exits_zero_on_the_committed_golden_set(capsys):
    code = main([])

    assert code == 0
    assert "12/12 cases passed" in capsys.readouterr().out
