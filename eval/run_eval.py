"""Evaluation harness: run the agent over a golden set and report pass/fail.

Usage (from the project root):
    python eval/run_eval.py
    python eval/run_eval.py --cases eval/golden_queries.json --verbose

Exit code is non-zero when any case fails, so this doubles as a regression gate.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.hints import make_enricher  # noqa: E402
from src.agent.knowledge import build_index  # noqa: E402
from src.agent.loop import run_agent  # noqa: E402
from src.agent.types import AgentResult  # noqa: E402
from src.main import SONGS_CSV  # noqa: E402
from src.recommender import load_songs  # noqa: E402

DEFAULT_CASES = PROJECT_ROOT / "eval" / "golden_queries.json"
COLUMNS = ("Case", "RAG", "Status", "Expected", "Conf", "Rev", "Result")
# Retrieval is on by default, matching src/agent_cli.py. Cases that test the bare
# loop set "use_rag": false explicitly.
DEFAULT_USE_RAG = True


def _check_status(case: Dict, result: AgentResult) -> List[str]:
    expected = case.get("expect_status")
    if expected and result.status != expected:
        return [f"status {result.status!r}, expected {expected!r}"]
    return []


def _check_counts(case: Dict, result: AgentResult) -> List[str]:
    failures = []
    count = len(result.recommendations)
    if "min_results" in case and count < case["min_results"]:
        failures.append(f"{count} result(s), wanted at least {case['min_results']}")
    if "max_results" in case and count > case["max_results"]:
        failures.append(f"{count} result(s), wanted at most {case['max_results']}")
    if "min_confidence" in case and result.confidence < case["min_confidence"]:
        failures.append(f"confidence {result.confidence:.2f} below {case['min_confidence']}")
    if "min_revisions" in case and result.revisions < case["min_revisions"]:
        failures.append(f"{result.revisions} revision(s), wanted at least {case['min_revisions']}")
    if "max_revisions" in case and result.revisions > case["max_revisions"]:
        failures.append(f"{result.revisions} revision(s), wanted at most {case['max_revisions']}")
    return failures


def _check_songs(case: Dict, result: AgentResult) -> List[str]:
    failures = []
    songs = [song for song, _, _ in result.recommendations]
    if "top_genre" in case:
        actual = songs[0].get("genre") if songs else None
        if actual != case["top_genre"]:
            failures.append(f"top genre {actual!r}, expected {case['top_genre']!r}")
    for genre in case.get("forbidden_genres", []):
        offenders = [song["title"] for song in songs if song.get("genre") == genre]
        if offenders:
            failures.append(f"excluded genre {genre!r} present: {offenders}")
    for field, minimum in case.get("field_at_least", {}).items():
        offenders = [song["title"] for song in songs if float(song.get(field, 0)) < minimum]
        if offenders:
            failures.append(f"{field} below {minimum} for {offenders}")
    for field, maximum in case.get("field_at_most", {}).items():
        offenders = [song["title"] for song in songs if float(song.get(field, 0)) > maximum]
        if offenders:
            failures.append(f"{field} above {maximum} for {offenders}")
    return failures


def _check_text(case: Dict, result: AgentResult) -> List[str]:
    failures = []
    needle = case.get("message_contains")
    if needle and needle.lower() not in result.message.lower():
        failures.append(f"message did not mention {needle!r}")
    surrendered = case.get("surrendered_contains")
    if surrendered and surrendered not in result.surrendered:
        failures.append(f"did not surrender {surrendered!r} (surrendered {list(result.surrendered)})")
    return failures


CHECKS = (_check_status, _check_counts, _check_songs, _check_text)


def evaluate_case(
    case: Dict, songs: Sequence[Dict], enrich=None
) -> Tuple[AgentResult, Tuple[str, ...]]:
    """Run one golden case and return its result plus any failure reasons."""
    use_rag = case.get("use_rag", DEFAULT_USE_RAG)
    result = run_agent(case["query"], songs, enrich=enrich if use_rag else None)
    failures: List[str] = []
    for check in CHECKS:
        failures.extend(check(case, result))
    return result, tuple(failures)


def load_cases(path: Path) -> List[Dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Golden case file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Golden case file {path} is not valid JSON: {error}") from error
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"Golden case file {path} contains no 'cases' list.")
    for index, case in enumerate(cases, start=1):
        if "query" not in case or "name" not in case:
            raise ValueError(f"Case {index} in {path} needs both 'name' and 'query'.")
    return cases


def _row(case: Dict, result: AgentResult, failures: Sequence[str]) -> Tuple[str, ...]:
    return (
        case["name"],
        "on" if case.get("use_rag", DEFAULT_USE_RAG) else "off",
        result.status,
        str(case.get("expect_status", "-")),
        f"{result.confidence:.2f}",
        str(result.revisions),
        "PASS" if not failures else "FAIL",
    )


def _render_table(rows: Sequence[Sequence[str]]) -> str:
    table = [COLUMNS] + [tuple(row) for row in rows]
    widths = [max(len(row[index]) for row in table) for index in range(len(COLUMNS))]
    lines = []
    for position, row in enumerate(table):
        lines.append("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)).rstrip())
        if position == 0:
            lines.append("  ".join("-" * width for width in widths))
    return "\n".join(lines)


def run_suite(cases: Sequence[Dict], songs: Sequence[Dict], verbose: bool = False) -> int:
    """Print the report and return the number of failing cases."""
    rows, details, confidences = [], [], []
    enrich = make_enricher(build_index(songs))
    for case in cases:
        result, failures = evaluate_case(case, songs, enrich=enrich)
        rows.append(_row(case, result, failures))
        confidences.append(result.confidence)
        if failures:
            details.append((case["name"], failures))
        if verbose:
            details.append((case["name"], (f"message: {result.message}",)))

    print(f"Agent evaluation harness — {len(cases)} cases, catalog of {len(songs)} songs\n")
    print(_render_table(rows))

    failed = sum(1 for row in rows if row[-1] == "FAIL")
    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    print(
        f"\n{len(cases) - failed}/{len(cases)} cases passed | "
        f"mean confidence {mean_confidence:.2f} | "
        f"{sum(1 for row in rows if row[2] == 'rejected')} guardrail rejection(s)"
    )
    for name, reasons in details:
        for reason in reasons:
            print(f"  - {name}: {reason}")
    return failed


def main(argv: Sequence[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the agent against its golden query set.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="golden case JSON file")
    parser.add_argument("--verbose", action="store_true", help="print each case's agent message")
    args = parser.parse_args(argv)

    try:
        cases = load_cases(args.cases)
        songs = load_songs(str(SONGS_CSV))
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 1 if run_suite(cases, songs, verbose=args.verbose) else 0


if __name__ == "__main__":
    sys.exit(main())
