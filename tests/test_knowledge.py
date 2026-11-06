import pytest

from src.agent.knowledge import (
    MIN_SIMILARITY,
    KnowledgeIndex,
    Passage,
    build_index,
    catalog_passages,
    load_markdown_passages,
    tokenize,
)
from src.recommender import load_songs


@pytest.fixture(scope="module")
def catalog():
    return load_songs("data/songs.csv")


@pytest.fixture(scope="module")
def index(catalog):
    return build_index(catalog)


def test_tokenize_drops_stopwords_and_keeps_genre_spellings():
    tokens = tokenize("Music for the hip-hop and r&b listener")

    assert "hip-hop" in tokens
    assert "r&b" in tokens
    assert "the" not in tokens
    assert "music" not in tokens


def test_markdown_passages_are_split_per_section_with_hints():
    passages = load_markdown_passages()

    titles = [passage.title for passage in passages]
    assert "Deep focus, studying and coding" in titles
    focus = next(item for item in passages if item.title.startswith("Deep focus"))
    assert ("instrumentalness", "0.95") in focus.hints
    assert focus.source == "use_cases.md"


def test_catalog_passages_describe_coverage_per_genre(catalog):
    passages = catalog_passages(catalog)

    jazz = next(item for item in passages if item.title.startswith("jazz"))
    assert "1960s" in jazz.body and "1990s" in jazz.body
    assert jazz.source == "data/songs.csv"
    assert jazz.hints == ()


def test_index_covers_both_sources(index):
    sources = {passage.source for passage in index.passages}

    assert "data/songs.csv" in sources
    assert {"genres.md", "moods.md", "use_cases.md"} <= sources


def test_retrieve_finds_the_focus_passage_for_a_coding_query(index):
    hits = index.retrieve("something for deep focus while coding")

    titles = [passage.title for passage, _ in hits]
    assert any(title.startswith("Deep focus") for title in titles)
    assert all(score >= MIN_SIMILARITY for _, score in hits)


def test_retrieve_finds_the_workout_passage_for_a_gym_query(index):
    titles = [passage.title for passage, _ in index.retrieve("gym workout hype")]

    assert any("Workout" in title for title in titles)


def test_retrieve_returns_nothing_for_unrelated_text(index):
    assert index.retrieve("quarterly tax depreciation schedule") == ()


def test_retrieve_respects_top_k(index):
    assert len(index.retrieve("chill lofi for studying", top_k=2)) <= 2


def test_retrieve_orders_results_by_similarity(index):
    hits = index.retrieve("instrumental jazz from the 1960s")

    scores = [score for _, score in hits]
    assert scores == sorted(scores, reverse=True)


def test_index_handles_an_empty_corpus():
    empty = KnowledgeIndex([])

    assert empty.retrieve("anything") == ()


def test_index_handles_a_passage_with_no_usable_tokens():
    index = KnowledgeIndex([Passage(title="the", body="and the", source="x.md")])

    assert index.retrieve("the and") == ()


def test_load_markdown_passages_rejects_a_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_markdown_passages(tmp_path / "nowhere")
