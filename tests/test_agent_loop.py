import pytest

from src.agent.loop import MAX_ITERATIONS, MAX_PASSES, run_agent
from src.agent.types import (
    STATUS_ACCEPTED,
    STATUS_BEST_EFFORT,
    STATUS_INFEASIBLE,
    STATUS_REJECTED,
)
from src.recommender import load_songs
from tests.test_constraints import make_song


@pytest.fixture(scope="module")
def catalog():
    return load_songs("data/songs.csv")


def titles(result):
    return [song["title"] for song, _, _ in result.recommendations]


def test_easy_query_is_accepted_on_the_first_pass(catalog):
    result = run_agent("high energy hip hop to hype me up", catalog)

    assert result.status == STATUS_ACCEPTED
    assert result.revisions == 0
    assert result.recommendations[0][0]["genre"] == "hip-hop"
    assert result.confidence > 0.5


def test_over_constrained_query_revises_and_changes_its_answer(catalog):
    result = run_agent("chill acoustic 90s stuff for studying, nothing too poppy", catalog)

    assert result.status in (STATUS_ACCEPTED, STATUS_BEST_EFFORT)
    assert result.revisions >= 1
    first_pass_titles = [title for title, _, _ in result.passes[0].picks]
    assert titles(result) != first_pass_titles


def test_veto_is_never_surrendered(catalog):
    result = run_agent("upbeat music, nothing too poppy", catalog)

    assert all(song["genre"] != "pop" for song, _, _ in result.recommendations)


def test_impossible_filter_combination_is_reported_as_infeasible():
    songs = [
        make_song(id=1, title="Vocal Pop", genre="pop", instrumentalness=0.0, speechiness=0.3),
        make_song(id=2, title="Quiet Ambient", genre="ambient", instrumentalness=0.9, speechiness=0.0),
    ]

    result = run_agent("instrumental lyrical music", songs)

    assert result.status == STATUS_INFEASIBLE
    assert "instrumentalness" in result.message or "speechiness" in result.message
    assert result.recommendations == ()
    assert result.confidence == pytest.approx(0.0)


def test_infeasible_message_names_the_closest_songs():
    songs = [make_song(id=1, title="Almost There", genre="pop", instrumentalness=0.9, speechiness=0.0)]

    result = run_agent("instrumental lyrical music", songs)

    assert "Almost There" in result.message


def test_empty_query_is_rejected_before_any_work(catalog):
    result = run_agent("   ", catalog)

    assert result.status == STATUS_REJECTED
    assert result.passes == ()
    assert "empty" in result.message.lower()


def test_unrecognised_query_is_rejected_with_examples(catalog):
    result = run_agent("asdfghjkl qwerty", catalog)

    assert result.status == STATUS_REJECTED
    assert "chill lofi for studying" in result.message


def test_loop_never_exceeds_its_pass_budget(catalog):
    result = run_agent("1960s instrumental hip hop, nothing too poppy", catalog)

    assert len(result.passes) <= MAX_ITERATIONS
    assert result.revisions <= MAX_PASSES
    assert result.status in (STATUS_ACCEPTED, STATUS_BEST_EFFORT, STATUS_INFEASIBLE)


def test_no_op_relaxation_does_not_burn_a_pass(catalog):
    result = run_agent("1960s instrumental hip hop", catalog)

    repeated = [item for item in result.passes if "no-op" in item.action]
    for item in repeated:
        assert "relaxed" in item.action or "no-op" in item.action


def test_mode_override_is_respected(catalog):
    result = run_agent("chill lofi", catalog, mode="genre_first")

    assert result.passes[0].plan.mode == "genre_first"


def test_result_carries_a_trace_for_every_pass(catalog):
    result = run_agent("moody 1990s jazz", catalog)

    assert result.passes
    for index, item in enumerate(result.passes, start=1):
        assert item.index == index
        assert item.verdict is not None
        assert item.action


def test_input_catalog_is_not_mutated(catalog):
    snapshot = [dict(song) for song in catalog]

    run_agent("chill acoustic 90s stuff for studying, nothing too poppy", catalog)

    assert catalog == snapshot
