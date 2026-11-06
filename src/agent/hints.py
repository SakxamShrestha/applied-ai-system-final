"""Turn retrieved passages into planning hints.

Retrieval only ever *adds* targets the listener did not state. Anything the
listener said explicitly wins, and retrieval never creates a hard filter: guessing
a veto from a similarity score would silently hide songs.
"""

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.agent.knowledge import KnowledgeIndex, Passage
from src.agent.types import QueryPlan

NUMERIC_HINT_FIELDS = frozenset(
    {"energy", "danceability", "acousticness", "instrumentalness", "speechiness", "tempo_bpm"}
)
CATEGORICAL_HINT_FIELDS = frozenset({"genre", "mood", "detailed_mood_tag", "release_decade"})
BOOLEAN_HINT_FIELDS = frozenset({"prefers_popular"})
MODE_HINT_FIELD = "mode"
# A mode hint is only honoured when the parser had too little to go on to choose.
MODE_HINT_APPLIES_TO = "balanced"
DEFAULT_TOP_K = 2
TRUE_WORDS = frozenset({"true", "yes", "1"})
FALSE_WORDS = frozenset({"false", "no", "0"})


def _coerce(field: str, raw: str) -> Tuple[bool, Any, str]:
    """(ok, value, reason). Corpus text is external data, so every value is validated."""
    text = raw.strip()
    if field in NUMERIC_HINT_FIELDS:
        try:
            return True, float(text), ""
        except ValueError:
            return False, None, f"{field}={text!r} is not a number"
    if field in CATEGORICAL_HINT_FIELDS:
        return (True, text.lower(), "") if text else (False, None, f"{field} hint was empty")
    if field in BOOLEAN_HINT_FIELDS:
        lowered = text.lower()
        if lowered in TRUE_WORDS:
            return True, True, ""
        if lowered in FALSE_WORDS:
            return True, False, ""
        return False, None, f"{field}={text!r} is not a boolean"
    return False, None, f"unknown hint field {field!r}"


def _describe(passage: Passage, similarity: float) -> str:
    return f"{passage.title!r} ({passage.source}, similarity {similarity:.2f})"


def hints_from_passages(
    hits: Sequence[Tuple[Passage, float]]
) -> Tuple[Dict[str, Any], Optional[str], Tuple[str, ...]]:
    """Collapse retrieved passages into (prefs, mode, notes). Earlier hits win."""
    prefs: Dict[str, Any] = {}
    mode: Optional[str] = None
    notes: List[str] = []
    for passage, similarity in hits:
        applied: List[str] = []
        for field, raw in passage.hints:
            if field == MODE_HINT_FIELD:
                if mode is None:
                    mode = raw.strip()
                    applied.append(f"mode={mode}")
                continue
            ok, value, reason = _coerce(field, raw)
            if not ok:
                notes.append(f"knowledge: ignored invalid hint in {_describe(passage, similarity)}: {reason}")
                continue
            if field in prefs:
                continue
            prefs[field] = value
            applied.append(f"{field}={value}")
        detail = ", ".join(applied) if applied else "no usable hints"
        notes.append(f"knowledge: retrieved {_describe(passage, similarity)} -> {detail}")
    return prefs, mode, tuple(notes)


def enrich_plan(
    plan: QueryPlan, index: KnowledgeIndex, top_k: int = DEFAULT_TOP_K
) -> QueryPlan:
    """Add retrieved targets to a plan without overriding anything the listener said."""
    hits = index.retrieve(plan.query, top_k=top_k)
    if not hits:
        return plan.with_additions(notes=("knowledge: no passage matched this query",))

    prefs, mode, notes = hints_from_passages(hits)
    enriched = plan.with_additions(prefs=prefs, notes=notes)
    if mode is not None and plan.mode == MODE_HINT_APPLIES_TO and mode != plan.mode:
        enriched = enriched.with_mode(mode)
    return enriched


def make_enricher(
    index: KnowledgeIndex, top_k: int = DEFAULT_TOP_K
) -> Callable[[QueryPlan], QueryPlan]:
    """Bind an index into the single-argument hook the agent loop expects."""

    def enrich(plan: QueryPlan) -> QueryPlan:
        return enrich_plan(plan, index, top_k=top_k)

    return enrich
