import pytest

from src.agent.voices import (
    VOICE_CRITIC,
    VOICE_DJ,
    VOICE_PLAIN,
    VOICES,
    UnknownVoiceError,
    aspects,
    explain,
    explain_all,
    voice_stats,
)
from tests.test_constraints import make_song

REASONS = "Genre match: lofi (+0.75); Mood match: chill (+2.0); Energy proximity: 0.95 (+2.85)"


def test_aspects_reads_the_scorers_own_labels():
    assert aspects(REASONS) == ("genre", "mood", "energy")


def test_aspects_ignores_unknown_labels_and_empty_text():
    assert aspects("Something else: 1") == ()
    assert aspects("") == ()


def test_plain_voice_states_the_facts_without_flourish():
    line = explain(make_song(genre="lofi", title="Library Rain"), 5.6, REASONS, VOICE_PLAIN)

    assert line.startswith("Library Rain:")
    assert "lofi" in line
    assert "!" not in line


def test_dj_voice_addresses_the_listener_and_names_the_artist():
    song = make_song(genre="edm", title="Laser Tide", artist="Voltage Youth", energy=0.95)

    line = explain(song, 6.0, REASONS, VOICE_DJ, rank=1)

    assert "Voltage Youth" in line
    assert line.startswith("Up next,")
    assert line.endswith("!")


def test_critic_voice_quotes_numbers():
    song = make_song(title="Coffee Shop Stories", instrumentalness=0.7)
    reasons = "Instrumentalness proximity: 0.95 (+1.43)"

    line = explain(song, 3.1, reasons, VOICE_CRITIC)

    assert "instrumentalness 0.70" in line
    assert "score 3.10" in line


def test_voices_differ_from_each_other_for_the_same_song():
    song = make_song(genre="lofi", title="Library Rain")

    lines = {voice: explain(song, 5.6, REASONS, voice) for voice in VOICES}

    assert len(set(lines.values())) == len(VOICES)


def test_dj_opener_rotates_with_rank():
    song = make_song()

    first = explain(song, 3.0, REASONS, VOICE_DJ, rank=1)
    second = explain(song, 3.0, REASONS, VOICE_DJ, rank=2)

    assert first != second


def test_every_voice_handles_a_song_with_no_credited_matches():
    song = make_song(title="Nothing Matched")

    for voice in VOICES:
        line = explain(song, 0.0, "", voice)
        assert "Nothing Matched" in line or "closest" in line


def test_explain_is_deterministic():
    song = make_song()

    assert explain(song, 3.0, REASONS, VOICE_DJ) == explain(song, 3.0, REASONS, VOICE_DJ)


def test_unknown_voice_is_rejected_by_name():
    with pytest.raises(UnknownVoiceError) as error:
        explain(make_song(), 1.0, REASONS, "shakespeare")

    assert "shakespeare" in str(error.value)
    assert "plain" in str(error.value)


def test_explain_all_numbers_every_recommendation():
    recommendations = [(make_song(id=index, title=f"Song {index}"), 3.0, REASONS) for index in range(1, 4)]

    lines = explain_all(recommendations, VOICE_CRITIC)

    assert len(lines) == 3
    assert "Song 1" in lines[0] and "Song 3" in lines[2]


def test_voice_stats_measures_length_and_numeric_density():
    plain = explain_all([(make_song(), 3.0, REASONS)], VOICE_PLAIN)
    critic = explain_all([(make_song(), 3.0, REASONS)], VOICE_CRITIC)

    assert voice_stats(critic)["digits"] > voice_stats(plain)["digits"]
    assert voice_stats(plain)["lines"] == 1
