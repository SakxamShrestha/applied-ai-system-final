import pytest

from src.agent.critic import MIN_MATCH_SCORE, critique
from src.agent.planner import revise
from src.agent.types import (
    KIND_FILTER,
    KIND_REQUIREMENT,
    OP_AT_LEAST,
    OP_EQUALS,
    OP_NOT_EQUALS,
    Constraint,
    QueryPlan,
)
from tests.test_constraints import make_song


def requirement(field, value) -> Constraint:
    return Constraint(
        field=field,
        op=OP_EQUALS,
        value=value,
        kind=KIND_REQUIREMENT,
        label=f"{field.replace('_', ' ')} = {value}",
    )


def pick(song, score, reason="matched"):
    return (song, score, reason)


def plan_with(**kwargs) -> QueryPlan:
    defaults = {"query": "test query", "prefs": {}, "mode": "balanced"}
    return QueryPlan(**{**defaults, **kwargs})


def test_critique_accepts_when_every_requirement_is_met():
    plan = plan_with(prefs={"genre": "jazz"}, requirements=(requirement("genre", "jazz"),))
    picks = [pick(make_song(genre="jazz", artist="A"), 4.0)]

    verdict = critique(plan, picks, survivors=5)

    assert verdict.accepted
    assert verdict.confidence > 0.5


def test_critique_flags_a_requirement_the_top_pick_misses():
    plan = plan_with(prefs={"genre": "jazz"}, requirements=(requirement("genre", "jazz"),))
    picks = [pick(make_song(genre="pop"), 4.0)]

    verdict = critique(plan, picks, survivors=5)

    assert not verdict.accepted
    problems = verdict.problems
    assert len(problems) == 1
    assert problems[0].constraint.field == "genre"
    assert "pop" in problems[0].detail


def test_critique_flags_degenerate_all_zero_scores():
    plan = plan_with(prefs={})
    picks = [pick(make_song(), 0.0)]

    verdict = critique(plan, picks, survivors=20)

    assert not verdict.accepted
    assert any("nothing in the catalog matched" in check.detail for check in verdict.problems)
    assert verdict.confidence == pytest.approx(0.0)


def test_critique_flags_an_empty_result_set():
    verdict = critique(plan_with(), [], survivors=0)

    assert not verdict.accepted
    assert any(check.name == "results_returned" for check in verdict.problems)


def test_critique_flags_a_veto_that_leaked_through():
    veto = Constraint(
        field="genre", op=OP_NOT_EQUALS, value="pop", kind=KIND_FILTER, label="exclude genre pop"
    )
    plan = plan_with(filters=(veto,))
    picks = [pick(make_song(genre="pop"), 3.0)]

    verdict = critique(plan, picks, survivors=20)

    assert any(check.name == "vetoes_respected" for check in verdict.problems)


def test_critique_flags_a_repeated_artist():
    plan = plan_with()
    picks = [pick(make_song(id=i, artist="Same Artist"), 3.0) for i in range(3)]

    verdict = critique(plan, picks, survivors=20)

    assert any(check.name == "artist_spread" for check in verdict.problems)


def test_confidence_drops_with_each_revision():
    plan = plan_with(prefs={"genre": "jazz"}, requirements=(requirement("genre", "jazz"),))
    picks = [pick(make_song(genre="jazz"), 5.0)]

    first = critique(plan, picks, survivors=20, revisions=0).confidence
    third = critique(plan, picks, survivors=20, revisions=2).confidence

    assert third < first


def test_confidence_is_bounded_between_zero_and_one():
    plan = plan_with(prefs={"genre": "jazz"})
    picks = [pick(make_song(genre="jazz"), 99.0)]

    assert 0.0 <= critique(plan, picks, survivors=20).confidence <= 1.0


def test_min_match_score_is_above_zero():
    assert MIN_MATCH_SCORE > 0


# --- planner ----------------------------------------------------------------------


def test_revise_drops_the_least_specific_violated_requirement_first():
    plan = plan_with(
        prefs={"genre": "hip-hop", "release_decade": "1990s"},
        requirements=(requirement("genre", "hip-hop"), requirement("release_decade", "1990s")),
    )
    picks = [pick(make_song(genre="pop", release_decade="2020s"), 1.0)]
    verdict = critique(plan, picks, survivors=20)

    revised = revise(plan, verdict)

    assert "release_decade" not in revised.prefs
    assert revised.prefs["genre"] == "hip-hop"
    assert any("release decade" in note for note in revised.notes)


def test_revise_switches_mode_when_requirements_are_met_but_nothing_scored():
    plan = plan_with(prefs={}, mode="balanced")
    picks = [pick(make_song(), 0.0)]
    verdict = critique(plan, picks, survivors=20)

    revised = revise(plan, verdict)

    assert revised.mode != "balanced"


def test_revise_surrenders_a_threshold_filter_before_giving_up():
    threshold = Constraint(
        field="instrumentalness",
        op=OP_AT_LEAST,
        value=0.5,
        kind=KIND_FILTER,
        label="instrumentalness at least 0.5",
    )
    plan = plan_with(prefs={}, filters=(threshold,), mode="balanced", notes=(
        "switched ranking mode to genre_first",
        "switched ranking mode to vibe_and_energy",
    ))
    picks = [pick(make_song(), 0.0)]
    verdict = critique(plan, picks, survivors=1)

    revised = revise(plan, verdict)

    assert revised.filters == ()


def test_revise_never_surrenders_a_veto_and_eventually_gives_up():
    veto = Constraint(
        field="genre", op=OP_NOT_EQUALS, value="pop", kind=KIND_FILTER, label="exclude genre pop"
    )
    plan = plan_with(prefs={}, filters=(veto,), notes=(
        "switched ranking mode to genre_first",
        "switched ranking mode to vibe_and_energy",
    ))
    picks = [pick(make_song(genre="jazz"), 0.0)]
    verdict = critique(plan, picks, survivors=1)

    assert revise(plan, verdict) is None
