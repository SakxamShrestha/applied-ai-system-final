import pytest

from src.agent.query_parser import (
    GENRE_WORDS,
    QueryValidationError,
    parse_query,
    validate_query,
)
from src.agent.types import KIND_FILTER, KIND_REQUIREMENT, OP_AT_LEAST, OP_NOT_EQUALS
from src.recommender import WEIGHT_STRATEGIES, load_songs


def constraint_fields(constraints):
    return {item.field for item in constraints}


def test_parse_query_extracts_genre_mood_and_decade():
    plan = parse_query("chill 1990s jazz")

    assert plan.prefs["genre"] == "jazz"
    assert plan.prefs["mood"] == "chill"
    assert plan.prefs["release_decade"] == "1990s"
    assert constraint_fields(plan.requirements) == {"genre", "mood", "release_decade"}
    assert all(item.kind == KIND_REQUIREMENT for item in plan.requirements)


def test_parse_query_prefers_longest_keyword_match():
    plan = parse_query("some indie rock for the drive")

    assert plan.prefs["genre"] == "indie rock"


def test_parse_query_maps_activity_cue_to_low_energy():
    plan = parse_query("something for studying")

    assert plan.prefs["energy"] == pytest.approx(0.3)


def test_parse_query_maps_hype_cue_to_high_energy():
    plan = parse_query("hype me up for the gym")

    assert plan.prefs["energy"] == pytest.approx(0.9)


def test_parse_query_turns_instrumental_into_a_hard_filter():
    plan = parse_query("instrumental background music")

    instrumental = [item for item in plan.filters if item.field == "instrumentalness"]
    assert len(instrumental) == 1
    assert instrumental[0].op == OP_AT_LEAST
    assert instrumental[0].kind == KIND_FILTER


def test_parse_query_turns_negation_into_a_veto_filter():
    plan = parse_query("upbeat stuff, nothing too poppy")

    vetoes = [item for item in plan.filters if item.op == OP_NOT_EQUALS]
    assert [item.value for item in vetoes] == ["pop"]
    assert vetoes[0].is_veto


def test_parse_query_negation_wins_over_positive_mention():
    plan = parse_query("no hip hop please, give me jazz")

    assert plan.prefs.get("genre") == "jazz"
    assert [item.value for item in plan.filters if item.op == OP_NOT_EQUALS] == ["hip-hop"]


def test_parse_query_picks_mode_from_what_it_found():
    assert parse_query("hip hop").mode == "genre_first"
    assert parse_query("high energy music").mode == "vibe_and_energy"
    assert parse_query("popular tracks").mode == "balanced"
    assert all(plan_mode in WEIGHT_STRATEGIES for plan_mode in ("genre_first", "vibe_and_energy", "balanced"))


def test_parse_query_keeps_the_original_text():
    plan = parse_query("  Moody R&B  ")

    assert plan.query == "Moody R&B"
    assert plan.prefs["genre"] == "r&b"


def test_validate_query_rejects_empty_input():
    with pytest.raises(QueryValidationError) as error:
        validate_query("   ")

    assert "empty" in str(error.value).lower()


def test_validate_query_rejects_overlong_input():
    with pytest.raises(QueryValidationError) as error:
        validate_query("lofi " * 200)

    assert "too long" in str(error.value).lower()


def test_validate_query_rejects_text_with_no_known_vocabulary():
    with pytest.raises(QueryValidationError) as error:
        validate_query("asdfghjkl qwerty")

    message = str(error.value).lower()
    assert "recognise" in message or "recognize" in message


def test_validate_query_returns_cleaned_text_when_accepted():
    assert validate_query("  lofi beats  ") == "lofi beats"


def test_every_catalog_genre_is_in_the_parser_vocabulary():
    songs = load_songs("data/songs.csv")

    catalog_genres = {song["genre"] for song in songs}
    assert catalog_genres <= set(GENRE_WORDS.values())
