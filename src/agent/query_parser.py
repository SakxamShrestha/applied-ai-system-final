"""Turn free-text listener requests into a QueryPlan.

Deliberately rule-based: the catalog has a closed vocabulary (12 genres, 10 moods,
4 decades), so keyword tables cover it, and the whole system stays reproducible
offline with no API key.
"""

import re
from typing import Any, Dict, List, Tuple

from src.agent.types import (
    KIND_FILTER,
    KIND_REQUIREMENT,
    OP_AT_LEAST,
    OP_AT_MOST,
    OP_EQUALS,
    OP_NOT_EQUALS,
    Constraint,
    QueryPlan,
)

MAX_QUERY_CHARS = 300

# --- Vocabulary ---------------------------------------------------------------------
GENRE_WORDS = {
    "lofi": "lofi", "lo-fi": "lofi", "lo fi": "lofi",
    "hip hop": "hip-hop", "hip-hop": "hip-hop", "hiphop": "hip-hop", "rap": "hip-hop",
    "indie rock": "indie rock", "indie pop": "indie pop", "indie": "indie rock",
    "jazz": "jazz", "edm": "edm", "electronic": "edm", "dance music": "edm",
    "rock": "rock", "pop": "pop", "poppy": "pop",
    "r&b": "r&b", "rnb": "r&b", "randb": "r&b",
    "acoustic": "acoustic", "ambient": "ambient", "synthwave": "synthwave",
    "synth wave": "synthwave", "retrowave": "synthwave",
    # Added for this listener's own catalog entries.
    "nepali": "nepali", "nepalese": "nepali", "nepal": "nepali",
    "j-pop": "j-pop", "jpop": "j-pop", "japanese": "j-pop", "japan": "j-pop",
    "city pop": "city pop", "citypop": "city pop",
}
MOOD_WORDS = {
    "chill": "chill", "chilled": "chill", "happy": "happy", "upbeat": "happy",
    "sad": "moody", "moody": "moody", "melancholy": "moody",
    "intense": "intense", "aggressive": "intense", "hard": "intense",
    "relaxed": "relaxed", "calm": "relaxed", "focused": "focused",
    "energetic": "energetic", "confident": "confident", "romantic": "romantic",
}
MOOD_TAG_WORDS = {
    "euphoric": "euphoric", "focused": "focused", "aggressive": "aggressive",
    "dreamy": "dreamy", "cozy": "cozy", "nostalgic": "nostalgic",
    "reflective": "reflective", "angsty": "angsty", "melancholic": "melancholic",
    "romantic": "romantic", "playful": "playful", "peaceful": "peaceful",
    "confident": "confident",
}
DECADE_WORDS = {
    "60s": "1960s", "1960s": "1960s", "sixties": "1960s",
    "70s": "1970s", "1970s": "1970s", "seventies": "1970s",
    "80s": "1980s", "1980s": "1980s", "eighties": "1980s",
    "90s": "1990s", "1990s": "1990s", "nineties": "1990s",
    "2000s": "2000s", "00s": "2000s",
    "2010s": "2010s", "10s": "2010s",
    "2020s": "2020s", "20s": "2020s", "modern": "2020s", "recent": "2020s",
}

# --- Numeric cues -------------------------------------------------------------------
ENERGY_CUES = {
    "high energy": 0.9, "hype": 0.9, "gym": 0.9, "workout": 0.9, "pump": 0.9,
    "party": 0.85, "dance": 0.8,
    "low energy": 0.2, "sleep": 0.15, "studying": 0.3, "study": 0.3,
    "coding": 0.3, "focus": 0.3, "background": 0.25, "reading": 0.25,
}
TEMPO_CUES = {"fast": 150.0, "uptempo": 150.0, "slow": 70.0, "slowed": 70.0}
DANCE_CUES = {"danceable": 0.85, "to dance": 0.85, "groovy": 0.8}

INSTRUMENTAL_WORDS = ("instrumental", "no vocals", "no lyrics", "no words", "wordless")
INSTRUMENTAL_MIN = 0.5
LYRICAL_WORDS = ("lyrical", "wordy", "storytelling")
SPEECHINESS_MIN = 0.1
POPULAR_WORDS = ("popular", "hits", "mainstream", "chart", "well known")
OBSCURE_WORDS = ("obscure", "deep cuts", "underground", "hidden gems", "lesser known")
OBSCURE_MAX_POPULARITY = 70

# "no X", "nothing too X", "without X", "not X", "avoid X", "skip X", "minus X"
NEGATION_PATTERNS = (
    r"\bno\s+(?P<term>[a-z&\- ]{2,12})",
    r"\bnothing\s+too\s+(?P<term>[a-z&\- ]{2,12})",
    r"\bnot\s+too\s+(?P<term>[a-z&\- ]{2,12})",
    r"\bwithout\s+(?P<term>[a-z&\- ]{2,12})",
    r"\bavoid\s+(?P<term>[a-z&\- ]{2,12})",
    r"\bskip\s+(?P<term>[a-z&\- ]{2,12})",
)

INITIAL_MODE_NOTE_PREFIX = "initial ranking mode "
MODE_VIBE = "vibe_and_energy"
MODE_GENRE = "genre_first"
MODE_BALANCED = "balanced"


class QueryValidationError(ValueError):
    """Raised when a query cannot be used at all. Carries a listener-facing message."""

    def __init__(self, message: str, suggestions: Tuple[str, ...] = ()):
        super().__init__(message)
        self.suggestions = suggestions


def _known_vocabulary() -> Tuple[str, ...]:
    words = set(GENRE_WORDS) | set(MOOD_WORDS) | set(MOOD_TAG_WORDS) | set(DECADE_WORDS)
    words |= set(ENERGY_CUES) | set(TEMPO_CUES) | set(DANCE_CUES)
    words |= set(INSTRUMENTAL_WORDS) | set(LYRICAL_WORDS) | set(POPULAR_WORDS) | set(OBSCURE_WORDS)
    return tuple(sorted(words))


EXAMPLE_QUERIES = (
    "chill lofi for studying",
    "high energy hip hop to hype me up",
    "moody 1990s jazz, nothing too poppy",
)


def validate_query(text: str) -> str:
    """Guardrail: return the cleaned query, or raise QueryValidationError explaining why not."""
    if text is None:
        raise QueryValidationError("Query was empty. Describe the music you want.", EXAMPLE_QUERIES)
    cleaned = " ".join(text.split())
    if not cleaned:
        raise QueryValidationError("Query was empty. Describe the music you want.", EXAMPLE_QUERIES)
    if len(cleaned) > MAX_QUERY_CHARS:
        raise QueryValidationError(
            f"Query is too long ({len(cleaned)} characters, limit {MAX_QUERY_CHARS}). "
            "Keep it to a sentence or two.",
            EXAMPLE_QUERIES,
        )
    lowered = cleaned.lower()
    if not any(_contains(lowered, word) for word in _known_vocabulary()):
        raise QueryValidationError(
            "Could not recognise any genre, mood, decade or listening situation in that query.",
            EXAMPLE_QUERIES,
        )
    return cleaned


def _negated_terms(lowered: str) -> Tuple[str, ...]:
    """Genre values the listener explicitly ruled out."""
    found: List[str] = []
    for pattern in NEGATION_PATTERNS:
        for match in re.finditer(pattern, lowered):
            term = match.group("term").strip()
            for word in sorted(GENRE_WORDS, key=len, reverse=True):
                if term.startswith(word) and GENRE_WORDS[word] not in found:
                    found.append(GENRE_WORDS[word])
                    break
    return tuple(found)


def _contains(lowered: str, phrase: str) -> bool:
    """Whole-phrase match, so 'pop' does not fire inside 'popular'."""
    return re.search(rf"(?<![a-z0-9&]){re.escape(phrase)}(?![a-z0-9])", lowered) is not None


def _best_match(lowered: str, table: Dict[str, str], blocked: Tuple[str, ...] = ()) -> Any:
    """Longest keyword wins, so 'indie rock' beats 'rock' and 'hip hop' beats 'pop'."""
    for word in sorted(table, key=len, reverse=True):
        if _contains(lowered, word) and table[word] not in blocked:
            return table[word]
    return None


def _first_cue(lowered: str, cues: Dict[str, float]) -> Any:
    for word in sorted(cues, key=len, reverse=True):
        if _contains(lowered, word):
            return cues[word]
    return None


def _categorical(lowered: str, blocked: Tuple[str, ...]) -> Tuple[Dict[str, Any], Tuple[Constraint, ...]]:
    """Genre/mood/decade/mood-tag become soft prefs AND critic requirements."""
    prefs: Dict[str, Any] = {}
    requirements: List[Constraint] = []
    tables = (
        ("genre", GENRE_WORDS, blocked),
        ("mood", MOOD_WORDS, ()),
        ("release_decade", DECADE_WORDS, ()),
        ("detailed_mood_tag", MOOD_TAG_WORDS, ()),
    )
    for field, table, blocked_values in tables:
        value = _best_match(lowered, table, blocked_values)
        if value is None:
            continue
        prefs[field] = value
        requirements.append(
            Constraint(
                field=field,
                op=OP_EQUALS,
                value=value,
                kind=KIND_REQUIREMENT,
                label=f"{field.replace('_', ' ')} = {value}",
            )
        )
    # A mood tag that merely repeats the mood adds nothing; keep the mood.
    if prefs.get("detailed_mood_tag") == prefs.get("mood"):
        prefs.pop("detailed_mood_tag", None)
        requirements = [item for item in requirements if item.field != "detailed_mood_tag"]
    return prefs, tuple(requirements)


def _numeric_prefs(lowered: str) -> Dict[str, Any]:
    prefs: Dict[str, Any] = {}
    for field, cues in (("energy", ENERGY_CUES), ("tempo_bpm", TEMPO_CUES), ("danceability", DANCE_CUES)):
        value = _first_cue(lowered, cues)
        if value is not None:
            prefs[field] = value
    if any(_contains(lowered, word) for word in POPULAR_WORDS):
        prefs["prefers_popular"] = True
    return prefs


def _filters(lowered: str, negated: Tuple[str, ...]) -> Tuple[Constraint, ...]:
    """Hard constraints that prune the catalog before scoring."""
    filters: List[Constraint] = []
    for genre in negated:
        filters.append(
            Constraint(
                field="genre",
                op=OP_NOT_EQUALS,
                value=genre,
                kind=KIND_FILTER,
                label=f"exclude genre {genre}",
            )
        )
    if any(_contains(lowered, word) for word in INSTRUMENTAL_WORDS):
        filters.append(
            Constraint(
                field="instrumentalness",
                op=OP_AT_LEAST,
                value=INSTRUMENTAL_MIN,
                kind=KIND_FILTER,
                label=f"instrumentalness at least {INSTRUMENTAL_MIN}",
            )
        )
    if any(_contains(lowered, word) for word in LYRICAL_WORDS):
        filters.append(
            Constraint(
                field="speechiness",
                op=OP_AT_LEAST,
                value=SPEECHINESS_MIN,
                kind=KIND_FILTER,
                label=f"speechiness at least {SPEECHINESS_MIN}",
            )
        )
    if any(_contains(lowered, word) for word in OBSCURE_WORDS):
        filters.append(
            Constraint(
                field="popularity",
                op=OP_AT_MOST,
                value=OBSCURE_MAX_POPULARITY,
                kind=KIND_FILTER,
                label=f"popularity at most {OBSCURE_MAX_POPULARITY}",
            )
        )
    return tuple(filters)


def _pick_mode(prefs: Dict[str, Any]) -> str:
    if "energy" in prefs or "detailed_mood_tag" in prefs:
        return MODE_VIBE
    if "genre" in prefs:
        return MODE_GENRE
    return MODE_BALANCED


def parse_query(text: str) -> QueryPlan:
    """Build the first QueryPlan for a query. Assumes validate_query already ran."""
    cleaned = " ".join((text or "").split())
    lowered = cleaned.lower()
    negated = _negated_terms(lowered)
    categorical, requirements = _categorical(lowered, negated)
    prefs = {**categorical, **_numeric_prefs(lowered)}
    filters = _filters(lowered, negated)
    mode = _pick_mode(prefs)
    notes = (
        f"parsed {len(prefs)} preference(s), {len(filters)} filter(s)",
        f"{INITIAL_MODE_NOTE_PREFIX}{mode}",
    )
    return QueryPlan(
        query=cleaned,
        prefs=prefs,
        filters=filters,
        requirements=requirements,
        mode=mode,
        notes=notes,
    )
