import pytest

from src.agent.constraints import (
    apply_filters,
    matches,
    nearest_misses,
    prune_counts,
    relaxable,
)
from src.agent.types import (
    KIND_FILTER,
    OP_AT_LEAST,
    OP_AT_MOST,
    OP_EQUALS,
    OP_NOT_EQUALS,
    Constraint,
)


def make_song(**overrides) -> dict:
    """Mirrors the fixture style in tests/test_scoring.py."""
    base = {
        "id": 1,
        "title": "Track",
        "artist": "Artist A",
        "genre": "pop",
        "mood": "happy",
        "energy": 0.8,
        "tempo_bpm": 120.0,
        "valence": 0.8,
        "danceability": 0.8,
        "acousticness": 0.2,
        "popularity": 50,
        "release_decade": "2010s",
        "detailed_mood_tag": "euphoric",
        "instrumentalness": 0.1,
        "speechiness": 0.05,
    }
    return {**base, **overrides}


def filter_for(field, op, value) -> Constraint:
    return Constraint(field=field, op=op, value=value, kind=KIND_FILTER, label=f"{field} {op} {value}")


def test_matches_handles_every_operator():
    song = make_song(genre="jazz", instrumentalness=0.7, popularity=40)

    assert matches(song, filter_for("genre", OP_EQUALS, "jazz"))
    assert matches(song, filter_for("genre", OP_NOT_EQUALS, "pop"))
    assert not matches(song, filter_for("genre", OP_NOT_EQUALS, "jazz"))
    assert matches(song, filter_for("instrumentalness", OP_AT_LEAST, 0.5))
    assert not matches(song, filter_for("instrumentalness", OP_AT_LEAST, 0.9))
    assert matches(song, filter_for("popularity", OP_AT_MOST, 70))


def test_matches_is_case_insensitive_for_text():
    song = make_song(genre="Hip-Hop")

    assert matches(song, filter_for("genre", OP_EQUALS, "hip-hop"))


def test_matches_skips_constraints_on_fields_the_song_lacks():
    song = {"id": 2, "title": "Sparse", "genre": "pop"}

    assert matches(song, filter_for("instrumentalness", OP_AT_LEAST, 0.5))


def test_apply_filters_keeps_only_survivors_and_does_not_mutate_input():
    songs = [make_song(id=1, instrumentalness=0.9), make_song(id=2, instrumentalness=0.1)]
    original = [dict(song) for song in songs]

    survivors = apply_filters(songs, (filter_for("instrumentalness", OP_AT_LEAST, 0.5),))

    assert [song["id"] for song in survivors] == [1]
    assert songs == original


def test_apply_filters_with_no_filters_returns_everything():
    songs = [make_song(id=1), make_song(id=2)]

    assert len(apply_filters(songs, ())) == 2


def test_prune_counts_reports_how_many_each_filter_removes():
    songs = [make_song(id=1, genre="pop"), make_song(id=2, genre="jazz", instrumentalness=0.8)]
    filters = (
        filter_for("genre", OP_NOT_EQUALS, "pop"),
        filter_for("instrumentalness", OP_AT_LEAST, 0.5),
    )

    counts = prune_counts(songs, filters)

    assert counts[filters[0]] == 1
    assert counts[filters[1]] == 1


def test_relaxable_never_offers_a_veto():
    veto = filter_for("genre", OP_NOT_EQUALS, "pop")
    threshold = filter_for("instrumentalness", OP_AT_LEAST, 0.5)

    assert relaxable((veto, threshold)) == (threshold,)


def test_nearest_misses_names_songs_that_fail_the_fewest_filters():
    songs = [
        make_song(id=1, genre="pop", instrumentalness=0.0),
        make_song(id=2, genre="jazz", instrumentalness=0.7, title="Almost"),
    ]
    filters = (
        filter_for("genre", OP_EQUALS, "hip-hop"),
        filter_for("instrumentalness", OP_AT_LEAST, 0.5),
    )

    misses = nearest_misses(songs, filters, limit=1)

    assert misses[0][0]["title"] == "Almost"
    assert misses[0][1] == 1


def test_nearest_misses_returns_empty_list_for_empty_catalog():
    assert nearest_misses([], (filter_for("genre", OP_EQUALS, "jazz"),), limit=3) == ()
