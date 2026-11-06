import pytest

from src.agent.hints import enrich_plan, hints_from_passages, make_enricher
from src.agent.knowledge import KnowledgeIndex, Passage, build_index
from src.agent.query_parser import parse_query
from src.recommender import load_songs


@pytest.fixture(scope="module")
def catalog():
    return load_songs("data/songs.csv")


@pytest.fixture(scope="module")
def index(catalog):
    return build_index(catalog)


def passage(title="Test", hints=(), source="test.md"):
    return Passage(title=title, body="body", source=source, hints=tuple(hints))


def test_hints_from_passages_coerces_each_value_type():
    hits = [
        (passage(hints=[("energy", "0.3"), ("genre", "Lofi"), ("prefers_popular", "true")]), 0.4)
    ]

    prefs, mode, _ = hints_from_passages(hits)

    assert prefs == {"energy": 0.3, "genre": "lofi", "prefers_popular": True}
    assert mode is None


def test_hints_from_passages_takes_the_best_match_on_conflict():
    hits = [
        (passage(title="Best", hints=[("energy", "0.9")]), 0.5),
        (passage(title="Worse", hints=[("energy", "0.1")]), 0.2),
    ]

    prefs, _, _ = hints_from_passages(hits)

    assert prefs["energy"] == pytest.approx(0.9)


def test_hints_from_passages_reports_but_ignores_bad_hints():
    hits = [(passage(hints=[("energy", "very high"), ("nonsense", "1")]), 0.3)]

    prefs, _, notes = hints_from_passages(hits)

    assert prefs == {}
    assert any("not a number" in note for note in notes)
    assert any("unknown hint field" in note for note in notes)


def test_hints_from_passages_records_a_mode_hint():
    hits = [(passage(hints=[("mode", "vibe_and_energy")]), 0.3)]

    _, mode, _ = hints_from_passages(hits)

    assert mode == "vibe_and_energy"


def test_enrich_plan_adds_retrieved_targets(index):
    plan = parse_query("something for deep focus while coding")

    enriched = enrich_plan(plan, index)

    assert enriched.prefs["instrumentalness"] == pytest.approx(0.95)
    assert any("Deep focus" in note for note in enriched.notes)


def test_enrich_plan_never_overrides_what_the_listener_said(index):
    plan = parse_query("high energy lofi for studying")
    assert plan.prefs["energy"] == pytest.approx(0.9)

    enriched = enrich_plan(plan, index)

    assert enriched.prefs["energy"] == pytest.approx(0.9)


def test_enrich_plan_never_adds_a_hard_filter(index):
    plan = parse_query("something for deep focus while coding")

    enriched = enrich_plan(plan, index)

    assert enriched.filters == plan.filters


def test_enrich_plan_keeps_requirements_untouched(index):
    plan = parse_query("moody 1990s jazz")

    enriched = enrich_plan(plan, index)

    assert enriched.requirements == plan.requirements


def test_enrich_plan_notes_when_nothing_was_retrieved():
    empty = KnowledgeIndex([])
    plan = parse_query("chill lofi")

    enriched = enrich_plan(plan, empty)

    assert enriched.prefs == plan.prefs
    assert any("no passage matched" in note for note in enriched.notes)


def test_enrich_plan_applies_a_mode_hint_only_to_the_balanced_default():
    index = KnowledgeIndex([passage(title="Romantic", hints=[("mode", "vibe_and_energy")])])
    balanced = parse_query("popular romantic tracks")
    assert balanced.mode == "balanced"

    assert enrich_plan(balanced, index).mode == "vibe_and_energy"

    energetic = parse_query("high energy romantic tracks")
    assert enrich_plan(energetic, index).mode == energetic.mode


def test_make_enricher_binds_the_index(index):
    enrich = make_enricher(index)

    enriched = enrich(parse_query("gym workout hype"))

    assert enriched.prefs["danceability"] == pytest.approx(0.85)
