"""A saved listener profile: background taste the agent carries into every query.

Precedence is deliberate and never varies:

    what you typed  >  your saved profile  >  the knowledge corpus

A profile contributes *preferences*, never requirements, so the critic can never fail a
result for missing something you did not ask for in this query. The one exception is
`avoid_genres`, which becomes a veto the planner will not concede — with the query still
winning: asking for a genre you normally avoid overrides the veto for that run.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.agent.knowledge import KnowledgeIndex
from src.agent.query_parser import GENRE_WORDS, MOOD_WORDS
from src.agent.types import KIND_FILTER, OP_NOT_EQUALS, Constraint, QueryPlan

PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"
DEFAULT_PROFILE_PATH = PROFILES_DIR / "me.json"

LIST_FIELDS = ("favorite_genres", "avoid_genres", "favorite_moods", "favorite_decades")
FLOAT_FIELDS = ("typical_energy",)
BOOL_FIELDS = ("likes_popular",)
TEXT_FIELDS = ("name", "notes")
KNOWN_FIELDS = frozenset(LIST_FIELDS + FLOAT_FIELDS + BOOL_FIELDS + TEXT_FIELDS)

KNOWN_GENRES = frozenset(GENRE_WORDS.values())
KNOWN_MOODS = frozenset(MOOD_WORDS.values())
KNOWN_DECADES = frozenset({"1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"})


class ProfileError(ValueError):
    """Raised when a profile file cannot be trusted. Carries a readable reason."""


@dataclass(frozen=True)
class Profile:
    """Background taste. Every field is optional; an empty profile is valid and inert."""

    name: str = "listener"
    favorite_genres: Tuple[str, ...] = ()
    avoid_genres: Tuple[str, ...] = ()
    favorite_moods: Tuple[str, ...] = ()
    favorite_decades: Tuple[str, ...] = ()
    typical_energy: Optional[float] = None
    likes_popular: Optional[bool] = None
    notes: str = ""
    warnings: Tuple[str, ...] = field(default=())

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.favorite_genres,
                self.avoid_genres,
                self.favorite_moods,
                self.favorite_decades,
                self.typical_energy is not None,
                self.likes_popular is not None,
            )
        )

    def describe(self) -> str:
        parts: List[str] = []
        if self.favorite_genres:
            parts.append("genres " + "/".join(self.favorite_genres))
        if self.favorite_moods:
            parts.append("moods " + "/".join(self.favorite_moods))
        if self.favorite_decades:
            parts.append("decades " + "/".join(self.favorite_decades))
        if self.typical_energy is not None:
            parts.append(f"usual energy {self.typical_energy}")
        if self.likes_popular is not None:
            parts.append("likes hits" if self.likes_popular else "prefers deep cuts")
        if self.avoid_genres:
            parts.append("skips " + "/".join(self.avoid_genres))
        return f"{self.name} — " + (", ".join(parts) if parts else "no stated taste")


def _strings(payload: Dict, key: str) -> Tuple[str, ...]:
    raw = payload.get(key)
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ProfileError(f"Profile field '{key}' must be a list of strings, got {type(raw).__name__}.")
    return tuple(item.strip().lower() for item in raw if item.strip())


def _float(payload: Dict, key: str) -> Optional[float]:
    raw = payload.get(key)
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise ProfileError(f"Profile field '{key}' must be a number, got {raw!r}.") from error
    if not 0.0 <= value <= 1.0:
        raise ProfileError(f"Profile field '{key}' must be between 0.0 and 1.0, got {value}.")
    return value


def _bool(payload: Dict, key: str) -> Optional[bool]:
    raw = payload.get(key)
    if raw is None:
        return None
    if not isinstance(raw, bool):
        raise ProfileError(f"Profile field '{key}' must be true or false, got {raw!r}.")
    return raw


def _vocabulary_warnings(
    values: Sequence[str], known: frozenset, label: str
) -> List[str]:
    unknown = [value for value in values if value not in known]
    if not unknown:
        return []
    return [
        f"{label} not present in this catalog, so it cannot match anything: "
        + ", ".join(sorted(unknown))
    ]


def profile_from_dict(payload: Dict[str, Any]) -> Profile:
    """Validate a decoded profile. External data, so every field is checked."""
    if not isinstance(payload, dict):
        raise ProfileError(f"A profile must be a JSON object, got {type(payload).__name__}.")

    warnings: List[str] = [
        f"ignored unknown profile field '{key}'"
        for key in sorted(payload)
        if key not in KNOWN_FIELDS
    ]
    genres = _strings(payload, "favorite_genres")
    avoid = _strings(payload, "avoid_genres")
    moods = _strings(payload, "favorite_moods")
    decades = _strings(payload, "favorite_decades")

    warnings.extend(_vocabulary_warnings(genres + avoid, KNOWN_GENRES, "genre"))
    warnings.extend(_vocabulary_warnings(moods, KNOWN_MOODS, "mood"))
    warnings.extend(_vocabulary_warnings(decades, KNOWN_DECADES, "decade"))
    overlap = set(genres) & set(avoid)
    if overlap:
        raise ProfileError(
            "A genre cannot be both favourite and avoided: " + ", ".join(sorted(overlap))
        )

    return Profile(
        name=str(payload.get("name", "listener")).strip() or "listener",
        favorite_genres=genres,
        avoid_genres=avoid,
        favorite_moods=moods,
        favorite_decades=decades,
        typical_energy=_float(payload, "typical_energy"),
        likes_popular=_bool(payload, "likes_popular"),
        notes=str(payload.get("notes", "")).strip(),
        warnings=tuple(warnings),
    )


def load_profile(path: str = None) -> Profile:
    """Read and validate a profile file."""
    target = Path(path) if path else DEFAULT_PROFILE_PATH
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ProfileError(
            f"Profile not found: {target}. Copy profiles/example.json to "
            f"{DEFAULT_PROFILE_PATH.name} and edit it, or pass --profile PATH."
        ) from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ProfileError(f"Profile {target} is not valid JSON: {error}") from error
    return profile_from_dict(payload)


def _single_or_tuple(values: Tuple[str, ...]):
    """score_song() accepts one value or several, so pass a tuple only when needed."""
    return values[0] if len(values) == 1 else values


def apply_profile(plan: QueryPlan, profile: Profile) -> QueryPlan:
    """Layer a profile under a parsed query. Anything the query stated wins."""
    if profile.is_empty:
        return plan.with_additions(notes=(f"profile: {profile.name} has no stated taste",))

    prefs: Dict[str, Any] = {}
    applied: List[str] = []
    for key, values in (
        ("genre", profile.favorite_genres),
        ("mood", profile.favorite_moods),
        ("release_decade", profile.favorite_decades),
    ):
        if values and key not in plan.prefs:
            prefs[key] = _single_or_tuple(values)
            applied.append(f"{key}={'/'.join(values)}")
    if profile.typical_energy is not None and "energy" not in plan.prefs:
        prefs["energy"] = profile.typical_energy
        applied.append(f"energy={profile.typical_energy}")
    if profile.likes_popular is not None and "prefers_popular" not in plan.prefs:
        prefs["prefers_popular"] = profile.likes_popular
        applied.append(f"prefers_popular={profile.likes_popular}")

    notes: List[str] = [
        f"profile: {profile.name} contributed {', '.join(applied) if applied else 'nothing new'}"
    ]
    notes.extend(f"profile warning: {warning}" for warning in profile.warnings)

    # A genre you normally skip, but asked for today, is not vetoed today.
    requested = plan.prefs.get("genre")
    requested_values = requested if isinstance(requested, (list, tuple)) else (requested,)
    filters: List[Constraint] = []
    for genre in profile.avoid_genres:
        if genre in requested_values:
            notes.append(f"profile: query overrode your usual skip of {genre}")
            continue
        filters.append(
            Constraint(
                field="genre",
                op=OP_NOT_EQUALS,
                value=genre,
                kind=KIND_FILTER,
                label=f"exclude genre {genre} (your profile)",
                source="profile",
            )
        )

    return plan.with_additions(prefs=prefs, filters=tuple(filters), notes=tuple(notes))


def make_profile_enricher(
    profile: Profile, index: Optional[KnowledgeIndex] = None
) -> Callable[[QueryPlan], QueryPlan]:
    """Profile first, then the knowledge corpus fills whatever is still unstated."""
    from src.agent.hints import enrich_plan

    def enrich(plan: QueryPlan) -> QueryPlan:
        enriched = apply_profile(plan, profile)
        return enrich_plan(enriched, index) if index is not None else enriched

    return enrich
