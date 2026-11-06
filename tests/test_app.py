from src.agent.loop import run_agent
from src.app import EXAMPLE_QUERIES, result_rows, retrieved_notes
from src.agent.hints import make_enricher
from src.agent.knowledge import build_index
from src.agent.voices import VOICE_CRITIC
from src.recommender import load_songs


def test_result_rows_shape_matches_the_recommendations():
    songs = load_songs("data/songs.csv")
    result = run_agent("chill lofi for studying", songs, k=3)

    rows = result_rows(result, VOICE_CRITIC)

    assert len(rows) == 3
    assert [row["Rank"] for row in rows] == [1, 2, 3]
    assert all(row["Why"] for row in rows)
    assert set(rows[0]) == {"Rank", "Title", "Artist", "Genre", "Decade", "Score", "Why"}


def test_result_rows_is_empty_for_a_rejected_query():
    assert result_rows(run_agent("", [])) == []


def test_retrieved_notes_lists_knowledge_hits():
    songs = load_songs("data/songs.csv")
    enrich = make_enricher(build_index(songs))
    result = run_agent("something for deep focus while coding", songs, enrich=enrich)

    notes = retrieved_notes(result)

    assert any("Deep focus" in note for note in notes)


def test_retrieved_notes_is_empty_without_retrieval():
    songs = load_songs("data/songs.csv")

    assert retrieved_notes(run_agent("chill lofi", songs)) == ()


def test_example_queries_cover_the_interesting_cases():
    assert any("instrumental" in example for example in EXAMPLE_QUERIES)
    assert any("nothing too poppy" in example for example in EXAMPLE_QUERIES)
