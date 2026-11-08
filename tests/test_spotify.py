from pathlib import Path

import pytest

from src.agent.spotify import (
    EXAMPLE_EXPORT,
    SpotifyImportError,
    catalog_rows,
    infer_profile,
    map_genre,
    read_export,
    summarize,
)


@pytest.fixture(scope="module")
def tracks():
    return read_export(str(EXAMPLE_EXPORT))


def write_csv(tmp_path, text, name="export.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


HEADER = "Track Name,Artist Name(s),Album Release Date,Popularity,Artist Genres,Energy\n"


# --- reading -----------------------------------------------------------------------


def test_read_export_parses_every_row(tracks):
    assert len(tracks) == 15
    first = tracks[0]
    assert first.title == "Stronger"
    assert first.artist == "Kanye West"
    assert first.popularity == 82
    assert first.release_year == 2007
    assert "chicago rap" in first.spotify_genres


def test_read_export_keeps_audio_features_when_present(tracks):
    first = tracks[0]

    assert first.features["energy"] == pytest.approx(0.85)
    assert first.features["danceability"] == pytest.approx(0.78)
    assert first.features["instrumentalness"] == pytest.approx(0.0)


def test_read_export_tolerates_a_file_without_audio_features(tmp_path):
    path = write_csv(
        tmp_path,
        "Track Name,Artist Name(s),Album Release Date,Popularity,Artist Genres\n"
        "Lemon,Kenshi Yonezu,2018-03-14,76,j-pop\n",
    )

    tracks = read_export(path)

    assert tracks[0].features == {}
    assert tracks[0].title == "Lemon"


def test_read_export_handles_a_utf8_bom(tmp_path):
    path = tmp_path / "bom.csv"
    path.write_text(HEADER + "Idol,YOASOBI,2023-04-12,84,j-pop,0.9\n", encoding="utf-8-sig")

    assert read_export(str(path))[0].title == "Idol"


def test_read_export_rejects_a_missing_file(tmp_path):
    with pytest.raises(SpotifyImportError) as error:
        read_export(str(tmp_path / "nope.csv"))

    assert "not found" in str(error.value).lower()


def test_read_export_rejects_a_file_without_the_required_columns(tmp_path):
    path = write_csv(tmp_path, "Foo,Bar\n1,2\n")

    with pytest.raises(SpotifyImportError) as error:
        read_export(path)

    assert "Track Name" in str(error.value)


def test_read_export_rejects_an_empty_export(tmp_path):
    path = write_csv(tmp_path, HEADER)

    with pytest.raises(SpotifyImportError) as error:
        read_export(path)

    assert "no tracks" in str(error.value).lower()


def test_read_export_skips_rows_with_no_title_and_reports_them(tmp_path):
    path = write_csv(tmp_path, HEADER + ",Kanye West,2007-09-11,82,rap,0.8\nIdol,YOASOBI,2023-04-12,84,j-pop,0.9\n")

    tracks = read_export(path)

    assert len(tracks) == 1
    assert tracks[0].title == "Idol"


def test_read_export_survives_unparseable_numbers(tmp_path):
    path = write_csv(tmp_path, HEADER + "Idol,YOASOBI,not-a-date,high,j-pop,loud\n")

    track = read_export(path)[0]

    assert track.release_year is None
    assert track.popularity is None
    assert "energy" not in track.features


# --- genre mapping -----------------------------------------------------------------


@pytest.mark.parametrize(
    "spotify_genre,expected",
    [
        ("chicago rap", "hip-hop"),
        ("atlanta trap", "hip-hop"),
        ("hip hop", "hip-hop"),
        ("japanese city pop", "city pop"),
        ("j-pop", "j-pop"),
        ("anime", "j-pop"),
        ("nepali classical", "nepali"),
        ("neo soul", "r&b"),
        ("chillhop", "lofi"),
        ("deep house", "edm"),
        ("vaporwave", "synthwave"),
        ("indie pop", "indie pop"),
        ("dance pop", "pop"),
        ("singer-songwriter", "acoustic"),
    ],
)
def test_map_genre_maps_spotify_vocabulary_onto_the_catalog(spotify_genre, expected):
    assert map_genre(spotify_genre) == expected


def test_map_genre_prefers_the_more_specific_match():
    # "japanese city pop" contains both "city pop" and "japanese"; city pop wins.
    assert map_genre("japanese city pop") == "city pop"


@pytest.mark.parametrize("unmapped", ["norwegian polka", "bluegrass", "gregorian chant", ""])
def test_map_genre_returns_none_for_something_unmapped(unmapped):
    assert map_genre(unmapped) is None


def test_map_genre_still_matches_a_substring_inside_a_longer_genre():
    # "black metal" is not in the catalog, but metal is closest to rock, so it maps.
    assert map_genre("norwegian black metal") == "rock"


# --- profile inference -------------------------------------------------------------


def test_infer_profile_picks_the_most_played_genres(tracks):
    profile = infer_profile(tracks, name="Test")

    assert profile.favorite_genres[0] == "hip-hop"
    assert set(profile.favorite_genres) <= {"hip-hop", "j-pop", "nepali", "city pop"}
    assert profile.name == "Test"


def test_infer_profile_derives_decades_from_release_dates(tracks):
    profile = infer_profile(tracks)

    assert "2010s" in profile.favorite_decades


def test_infer_profile_sets_typical_energy_from_the_mean(tracks):
    profile = infer_profile(tracks)

    assert 0.0 < profile.typical_energy < 1.0


def test_infer_profile_leaves_energy_unset_without_audio_features(tmp_path):
    path = write_csv(
        tmp_path,
        "Track Name,Artist Name(s),Album Release Date,Popularity,Artist Genres\n"
        "Lemon,Kenshi Yonezu,2018-03-14,76,j-pop\n",
    )

    profile = infer_profile(read_export(path))

    assert profile.typical_energy is None


def test_infer_profile_never_invents_a_veto(tracks):
    assert infer_profile(tracks).avoid_genres == ()


def test_infer_profile_reports_genres_it_could_not_map(tmp_path):
    path = write_csv(tmp_path, HEADER + "Mystery,Someone,2020-01-01,50,norwegian polka,0.5\n")

    profile = infer_profile(read_export(path))

    assert any("polka" in warning for warning in profile.warnings)


def test_infer_profile_limits_how_many_genres_it_claims(tracks):
    assert len(infer_profile(tracks, top_genres=2).favorite_genres) == 2


# --- catalog rows ------------------------------------------------------------------


def test_catalog_rows_only_include_tracks_with_real_features(tracks):
    rows = catalog_rows(tracks, start_id=100)

    assert len(rows) == 15
    assert rows[0]["id"] == 100
    assert rows[0]["title"] == "Stronger"
    assert rows[0]["genre"] == "hip-hop"


def test_catalog_rows_skip_tracks_without_features_or_genre(tmp_path):
    path = write_csv(
        tmp_path,
        "Track Name,Artist Name(s),Album Release Date,Popularity,Artist Genres\n"
        "Lemon,Kenshi Yonezu,2018-03-14,76,j-pop\n",
    )

    assert catalog_rows(read_export(path), start_id=100) == ()


def test_catalog_rows_fill_every_catalog_column(tracks):
    from src.recommender import FLOAT_FIELDS, INT_FIELDS

    row = catalog_rows(tracks, start_id=100)[0]

    for column in INT_FIELDS + FLOAT_FIELDS + ("title", "artist", "genre", "mood", "release_decade"):
        assert column in row, column


def test_summarize_mentions_counts_and_mapping(tracks):
    text = summarize(tracks, infer_profile(tracks))

    assert "15" in text
    assert "hip-hop" in text


# --- CLI ---------------------------------------------------------------------------


def test_cli_dry_run_writes_nothing(tmp_path, capsys):
    from src.import_spotify import EXIT_OK, main

    out = tmp_path / "profile.json"
    code = main([str(EXAMPLE_EXPORT), "--name", "Test", "--out", str(out), "--dry-run"])

    output = capsys.readouterr().out
    assert code == EXIT_OK
    assert not out.exists()
    assert "Dry run: nothing written" in output
    assert "hip-hop" in output


def test_cli_writes_a_loadable_profile(tmp_path, capsys):
    from src.agent.profile import load_profile
    from src.import_spotify import EXIT_OK, main

    out = tmp_path / "profile.json"
    code = main([str(EXAMPLE_EXPORT), "--name", "Test", "--out", str(out), "--write"])

    assert code == EXIT_OK
    capsys.readouterr()
    written = load_profile(str(out))
    assert written.name == "Test"
    assert written.favorite_genres[0] == "hip-hop"
    assert written.warnings == ()


def test_cli_reports_a_missing_export(tmp_path, capsys):
    from src.import_spotify import EXIT_IMPORT_ERROR, main

    code = main([str(tmp_path / "nope.csv")])

    assert code == EXIT_IMPORT_ERROR
    assert "not found" in capsys.readouterr().err.lower()


def test_cli_refuses_to_write_an_empty_profile(tmp_path, capsys):
    from src.import_spotify import EXIT_NOTHING_TO_WRITE, main

    export = tmp_path / "unmappable.csv"
    export.write_text(
        "Track Name,Artist Name(s),Artist Genres\nMystery,Someone,norwegian polka\n",
        encoding="utf-8",
    )

    code = main([str(export), "--write", "--out", str(tmp_path / "p.json")])

    assert code == EXIT_NOTHING_TO_WRITE
    assert "nothing" in capsys.readouterr().err.lower()


def test_append_catalog_skips_titles_already_present(tmp_path):
    from src.import_spotify import append_catalog
    from src.recommender import load_songs

    catalog = tmp_path / "songs.csv"
    original = Path("data/songs.csv").read_text(encoding="utf-8")
    catalog.write_text(original, encoding="utf-8")
    before = len(load_songs(str(catalog)))
    rows = catalog_rows(read_export(str(EXAMPLE_EXPORT)), start_id=900)

    written = append_catalog(rows, catalog)

    after = load_songs(str(catalog))
    assert len(after) == before + written
    # Stronger and Lemon are already in the committed catalog, so they are not duplicated.
    titles = [song["title"] for song in after]
    assert titles.count("Stronger") == 1
    assert titles.count("Lemon") == 1


def test_profile_to_dict_omits_empty_fields():
    from src.agent.profile import Profile
    from src.import_spotify import profile_to_dict

    payload = profile_to_dict(Profile(name="Bare"))

    assert payload == {"name": "Bare"}
