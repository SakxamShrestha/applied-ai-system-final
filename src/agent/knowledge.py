"""Retrieval over the knowledge corpus: hand-written notes plus catalog facts.

Pure-Python TF-IDF, so retrieval needs no extra dependency and gives identical
results on every machine. The corpus holds editorial judgements that the song
columns cannot express ("focus music means near-instrumental"), which is what makes
retrieval change the ranking rather than restate it.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"
TOKEN_PATTERN = re.compile(r"[a-z0-9&\-]+")
HINT_PATTERN = re.compile(r"^-\s*hint:\s*(?P<field>[a-z_]+)\s*=\s*(?P<value>.+?)\s*$", re.MULTILINE)
SECTION_PATTERN = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)

# Similarity below this is treated as "the corpus has nothing to say". Raised from 0.05
# after a *high energy* query retrieved the "Chill, relaxed and calm" passage at 0.08 and
# injected an acousticness target that worked against the request.
MIN_SIMILARITY = 0.10
DEFAULT_TOP_K = 3
STOPWORDS = frozenset(
    """a an and are as at be but by for from has have in is it its of on or
    that the their them these this to too with without you your not no are
    more most than then they when while which who how what why
    music song songs track tracks listener listeners listening
    something anything someone somebody stuff thing things some any
    want wants wanted need needs give get put find looking look
    me my i you your it is are was were do does did can could would
    here there about into over under out up down""".split()
)


@dataclass(frozen=True)
class Passage:
    """One retrievable chunk: a markdown section or a catalog summary."""

    title: str
    body: str
    source: str
    hints: Tuple[Tuple[str, str], ...] = field(default=())

    @property
    def text(self) -> str:
        return f"{self.title}\n{self.body}"


def tokenize(text: str) -> List[str]:
    return [token for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOPWORDS]


def _parse_hints(body: str) -> Tuple[Tuple[str, str], ...]:
    return tuple((match.group("field"), match.group("value")) for match in HINT_PATTERN.finditer(body))


def _split_sections(text: str, source: str) -> List[Passage]:
    matches = list(SECTION_PATTERN.finditer(text))
    passages = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        passages.append(
            Passage(title=match.group("title"), body=body, source=source, hints=_parse_hints(body))
        )
    return passages


def load_markdown_passages(directory: Path = KNOWLEDGE_DIR) -> Tuple[Passage, ...]:
    """Every '## ' section of every markdown file in the corpus directory."""
    if not directory.exists():
        raise FileNotFoundError(f"Knowledge directory not found: {directory}")
    passages: List[Passage] = []
    for path in sorted(directory.glob("*.md")):
        passages.extend(_split_sections(path.read_text(encoding="utf-8"), source=path.name))
    return tuple(passages)


def catalog_passages(songs: Sequence[Dict]) -> Tuple[Passage, ...]:
    """One passage per genre describing what the catalog actually holds.

    This is the second retrieval source: it keeps the agent honest about coverage
    ("jazz exists only in the 1960s and 1990s") without hand-maintaining that text.
    """
    by_genre: Dict[str, List[Dict]] = {}
    for song in songs:
        by_genre.setdefault(str(song.get("genre", "unknown")), []).append(song)

    passages = []
    for genre, members in sorted(by_genre.items()):
        decades = sorted({str(song.get("release_decade", "?")) for song in members})
        moods = sorted({str(song.get("mood", "?")) for song in members})
        energies = [float(song.get("energy", 0.0)) for song in members]
        instrumentals = [float(song.get("instrumentalness", 0.0)) for song in members]
        mean_energy = sum(energies) / len(energies)
        mean_instrumental = sum(instrumentals) / len(instrumentals)
        body = (
            f"Catalog coverage for {genre}: {len(members)} song(s), "
            f"decades {', '.join(decades)}, moods {', '.join(moods)}. "
            f"Mean energy {mean_energy:.2f}, mean instrumentalness {mean_instrumental:.2f}."
        )
        passages.append(Passage(title=f"{genre} in this catalog", body=body, source="data/songs.csv"))
    return tuple(passages)


class KnowledgeIndex:
    """TF-IDF index over a fixed set of passages."""

    def __init__(self, passages: Sequence[Passage]):
        self.passages: Tuple[Passage, ...] = tuple(passages)
        self._document_frequency: Counter = Counter()
        self._vectors: List[Dict[str, float]] = []
        for passage in self.passages:
            self._document_frequency.update(set(tokenize(passage.text)))
        for passage in self.passages:
            self._vectors.append(self._vector(tokenize(passage.text)))

    def _idf(self, token: str) -> float:
        total = max(1, len(self.passages))
        return math.log(total / (1 + self._document_frequency.get(token, 0))) + 1.0

    def _vector(self, tokens: Sequence[str]) -> Dict[str, float]:
        if not tokens:
            return {}
        counts = Counter(tokens)
        length = len(tokens)
        return {token: (count / length) * self._idf(token) for token, count in counts.items()}

    @staticmethod
    def _cosine(left: Dict[str, float], right: Dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        shared = set(left) & set(right)
        if not shared:
            return 0.0
        dot = sum(left[token] * right[token] for token in shared)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return dot / (left_norm * right_norm)

    def retrieve(
        self, query: str, top_k: int = DEFAULT_TOP_K, min_similarity: float = MIN_SIMILARITY
    ) -> Tuple[Tuple[Passage, float], ...]:
        """Passages most similar to the query, best first, above the threshold."""
        query_vector = self._vector(tokenize(query))
        scored = [
            (passage, self._cosine(query_vector, vector))
            for passage, vector in zip(self.passages, self._vectors)
        ]
        hits = [(passage, score) for passage, score in scored if score >= min_similarity]
        hits.sort(key=lambda row: (-row[1], row[0].title))
        return tuple(hits[:top_k])


def build_index(
    songs: Sequence[Dict] = (), directory: Path = KNOWLEDGE_DIR
) -> KnowledgeIndex:
    """Index the markdown corpus together with catalog-derived passages."""
    return KnowledgeIndex(load_markdown_passages(directory) + catalog_passages(songs))
