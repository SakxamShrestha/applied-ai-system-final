import json

import pytest

from src.agent.profile import (
    DEFAULT_PROFILE_PATH,
    ProfileError,
    apply_profile,
    load_profile,
    make_profile_enricher,
)
from src.agent.query_parser import parse_query
from src.agent.types import OP_NOT_EQUALS


def write(tmp_path, payload) -> str:
    path = tmp_path / "me.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


BASIC = {
    "name": "Test Listener",
    "favorite_genres": ["hip-hop", "r&b"],
    "avoid_genres": ["ambient"],
    "typical_energy": 0.8,
    "favorite_decades": ["2020s"],
    "likes_popular": True,
}


def test_load_profile_reads_every_field(tmp_path):
    profile = load_profile(write(tmp_path, BASIC))

    assert profile.name == "Test Listener"
    assert profile.favorite_genres == ("hip-hop", "r&b")
    assert profile.avoid_genres == ("ambient",)
    assert profile.typical_energy == pytest.approx(0.8)
    assert profile.favorite_decades == ("2020s",)
    assert profile.likes_popular is True


def test_load_profile_accepts_a_partial_profile(tmp_path):
    profile = load_profile(write(tmp_path, {"favorite_genres": ["jazz"]}))

    assert profile.favorite_genres == ("jazz",)
    assert profile.typical_energy is None
    assert profile.avoid_genres == ()


def test_load_profile_rejects_a_missing_file(tmp_path):
    with pytest.raises(ProfileError) as error:
        load_profile(str(tmp_path / "nope.json"))

    assert "not found" in str(error.value).lower()


def test_load_profile_rejects_malformed_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ProfileError) as error:
        load_profile(str(path))

    assert "valid json" in str(error.value).lower()


def test_load_profile_rejects_an_out_of_range_energy(tmp_path):
    with pytest.raises(ProfileError) as error:
        load_profile(write(tmp_path, {"typical_energy": 4.0}))

    assert "typical_energy" in str(error.value)


def test_load_profile_rejects_a_non_list_genre_field(tmp_path):
    with pytest.raises(ProfileError) as error:
        load_profile(write(tmp_path, {"favorite_genres": "hip-hop"}))

    assert "favorite_genres" in str(error.value)


def test_load_profile_reports_unknown_keys(tmp_path):
    profile = load_profile(write(tmp_path, {"favourite_genres": ["jazz"]}))

    assert any("favourite_genres" in warning for warning in profile.warnings)


def test_load_profile_warns_about_a_genre_not_in_the_catalog(tmp_path):
    profile = load_profile(write(tmp_path, {"favorite_genres": ["polka"]}))

    assert any("polka" in warning for warning in profile.warnings)


def test_apply_profile_adds_background_preferences(tmp_path):
    profile = load_profile(write(tmp_path, BASIC))
    plan = parse_query("something upbeat")

    enriched = apply_profile(plan, profile)

    assert enriched.prefs["genre"] == ("hip-hop", "r&b")
    assert enriched.prefs["energy"] == pytest.approx(0.8)
    assert enriched.prefs["prefers_popular"] is True
    assert any("profile" in note for note in enriched.notes)


def test_the_query_always_beats_the_profile(tmp_path):
    profile = load_profile(write(tmp_path, BASIC))
    plan = parse_query("jazz")
    assert plan.prefs["genre"] == "jazz"

    enriched = apply_profile(plan, profile)

    assert enriched.prefs["genre"] == "jazz"


def test_avoided_genres_become_vetoes(tmp_path):
    profile = load_profile(write(tmp_path, BASIC))

    enriched = apply_profile(parse_query("something upbeat"), profile)

    vetoes = [item for item in enriched.filters if item.op == OP_NOT_EQUALS]
    assert [item.value for item in vetoes] == ["ambient"]
    assert vetoes[0].is_veto


def test_an_avoided_genre_is_dropped_when_the_query_asks_for_it(tmp_path):
    profile = load_profile(write(tmp_path, BASIC))

    enriched = apply_profile(parse_query("ambient music"), profile)

    assert [item for item in enriched.filters if item.op == OP_NOT_EQUALS] == []
    assert any("overrode" in note for note in enriched.notes)


def test_profile_never_creates_a_critic_requirement(tmp_path):
    profile = load_profile(write(tmp_path, BASIC))
    plan = parse_query("something upbeat")

    enriched = apply_profile(plan, profile)

    assert enriched.requirements == plan.requirements


def test_make_profile_enricher_runs_profile_then_knowledge(tmp_path):
    from src.agent.knowledge import build_index
    from src.recommender import load_songs

    songs = load_songs("data/songs.csv")
    profile = load_profile(write(tmp_path, BASIC))
    enrich = make_profile_enricher(profile, build_index(songs))

    enriched = enrich(parse_query("something for deep focus while coding"))

    # "coding" is itself an energy cue, so the query outranks the profile here.
    assert enriched.prefs["energy"] == pytest.approx(0.3)
    # The profile still supplies the genre the query never mentioned.
    assert enriched.prefs["genre"] == ("hip-hop", "r&b")
    # And knowledge fills what neither stated.
    assert "instrumentalness" in enriched.prefs


def test_profile_energy_applies_when_the_query_gives_no_energy_cue(tmp_path):
    from src.agent.knowledge import build_index
    from src.recommender import load_songs

    songs = load_songs("data/songs.csv")
    profile = load_profile(write(tmp_path, BASIC))
    enrich = make_profile_enricher(profile, build_index(songs))

    enriched = enrich(parse_query("jazz"))

    assert enriched.prefs["energy"] == pytest.approx(0.8)


def test_default_profile_path_points_into_the_repo():
    assert DEFAULT_PROFILE_PATH.name == "me.json"
    assert DEFAULT_PROFILE_PATH.parent.name == "profiles"
