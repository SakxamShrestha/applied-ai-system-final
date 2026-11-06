"""The filter stage: hard constraints prune the catalog before anything is scored.

This is the stage the original recommender lacks. Weighted scoring can express
"I prefer instrumental music" but not "do not show me anything with vocals", and
columns like instrumentalness carry no weight at all, so a threshold request was
previously unsatisfiable.
"""

from typing import Dict, List, Sequence, Tuple

from src.agent.types import (
    OP_AT_LEAST,
    OP_AT_MOST,
    OP_EQUALS,
    OP_NOT_EQUALS,
    Constraint,
)

SongDict = Dict
NearestMiss = Tuple[SongDict, int, Tuple[Constraint, ...]]


def _same_text(left, right) -> bool:
    return str(left).strip().lower() == str(right).strip().lower()


def _as_float(value, constraint: Constraint) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Song value {value!r} for '{constraint.field}' is not numeric, "
            f"so constraint '{constraint.label}' cannot be checked."
        ) from error


def matches(song: SongDict, constraint: Constraint) -> bool:
    """True when the song satisfies the constraint.

    A field the song does not carry is treated as 'cannot judge, do not exclude',
    matching how score_song() skips features missing from a song.
    """
    if constraint.field not in song:
        return True
    actual = song[constraint.field]
    if constraint.op == OP_EQUALS:
        return _same_text(actual, constraint.value)
    if constraint.op == OP_NOT_EQUALS:
        return not _same_text(actual, constraint.value)
    if constraint.op == OP_AT_LEAST:
        return _as_float(actual, constraint) >= float(constraint.value)
    if constraint.op == OP_AT_MOST:
        return _as_float(actual, constraint) <= float(constraint.value)
    raise ValueError(f"Unknown constraint operator '{constraint.op}' in '{constraint.label}'.")


def failed_constraints(song: SongDict, constraints: Sequence[Constraint]) -> Tuple[Constraint, ...]:
    """Every constraint this song does not satisfy."""
    return tuple(item for item in constraints if not matches(song, item))


def apply_filters(songs: Sequence[SongDict], filters: Sequence[Constraint]) -> Tuple[SongDict, ...]:
    """Return the songs satisfying every filter. Input is never modified."""
    if not filters:
        return tuple(songs)
    return tuple(song for song in songs if not failed_constraints(song, filters))


def prune_counts(
    songs: Sequence[SongDict], filters: Sequence[Constraint]
) -> Dict[Constraint, int]:
    """How many songs each filter removes on its own. Used to explain infeasibility."""
    return {item: sum(1 for song in songs if not matches(song, item)) for item in filters}


def relaxable(filters: Sequence[Constraint]) -> Tuple[Constraint, ...]:
    """Filters the agent may surrender, easiest first. Vetoes are never surrendered."""
    candidates = [item for item in filters if not item.is_veto]
    return tuple(sorted(candidates, key=lambda item: item.relax_priority))


def nearest_misses(
    songs: Sequence[SongDict], constraints: Sequence[Constraint], limit: int = 3
) -> Tuple[NearestMiss, ...]:
    """Songs that fail the fewest constraints, for 'the closest thing we have' messages."""
    scored: List[NearestMiss] = []
    for song in songs:
        failures = failed_constraints(song, constraints)
        if failures:
            scored.append((song, len(failures), failures))
    scored.sort(key=lambda row: (row[1], str(row[0].get("title", ""))))
    return tuple(scored[:limit])
