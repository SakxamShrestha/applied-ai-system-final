"""The critic: decides whether a result set actually answers the query.

Every check is reported, passed or failed, so the trace shows what the agent
verified rather than only what went wrong.
"""

from typing import Dict, List, Sequence, Tuple

from src.agent.constraints import matches
from src.agent.types import Check, Constraint, QueryPlan, Verdict

# A top score at or below this means nothing in the catalog matched any part of the
# request. Scoring a little is a weak answer, not a broken one, so the threshold sits
# just above zero and confidence carries the nuance instead.
MIN_MATCH_SCORE = 0.01
# Score treated as "a complete match" when normalising confidence.
CONFIDENCE_FULL_SCORE = 5.0
# Weighting between "scored well" and "honoured what was asked".
CONFIDENCE_SCORE_WEIGHT = 0.5
CONFIDENCE_REQUIREMENT_WEIGHT = 0.5
# Each revision costs this much confidence, multiplicatively.
REVISION_CONFIDENCE_PENALTY = 0.85
MAX_SAME_ARTIST = 2
# Floor applied once a run has surrendered part of the request: the answer is real,
# it just is not what was asked for.
MIN_SURRENDERED_CONFIDENCE = 0.05

Pick = Tuple[Dict, float, str]


def _results_check(picks: Sequence[Pick], survivors: int) -> Check:
    if picks:
        return Check("results_returned", True, f"{len(picks)} song(s) returned")
    return Check(
        "results_returned",
        False,
        f"no songs returned ({survivors} survived the filter stage)",
    )


def _match_check(picks: Sequence[Pick]) -> Check:
    top_score = picks[0][1] if picks else 0.0
    if top_score > MIN_MATCH_SCORE:
        return Check("score_floor", True, f"top score {top_score:.2f}")
    return Check(
        "score_floor",
        False,
        f"top score {top_score:.2f}: nothing in the catalog matched any part of the request",
    )


def _requirement_checks(plan: QueryPlan, picks: Sequence[Pick]) -> List[Check]:
    checks: List[Check] = []
    if not picks:
        return checks
    top_song = picks[0][0]
    for requirement in plan.requirements:
        if matches(top_song, requirement):
            checks.append(
                Check(
                    f"requirement:{requirement.field}",
                    True,
                    f"top pick satisfies {requirement.label}",
                    requirement,
                )
            )
            continue
        actual = top_song.get(requirement.field, "(missing)")
        checks.append(
            Check(
                f"requirement:{requirement.field}",
                False,
                f"top pick has {requirement.field}={actual!r}, wanted {requirement.value!r}",
                requirement,
            )
        )
    return checks


def _veto_check(plan: QueryPlan, picks: Sequence[Pick]) -> List[Check]:
    vetoes: Tuple[Constraint, ...] = tuple(item for item in plan.filters if item.is_veto)
    if not vetoes:
        return []
    offenders = [
        song["title"]
        for song, _, _ in picks
        for veto in vetoes
        if not matches(song, veto)
    ]
    if offenders:
        return [
            Check(
                "vetoes_respected",
                False,
                f"excluded values present in results: {sorted(set(offenders))}",
            )
        ]
    return [Check("vetoes_respected", True, f"{len(vetoes)} exclusion(s) honoured")]


def _artist_spread_check(picks: Sequence[Pick]) -> Check:
    counts: Dict[str, int] = {}
    for song, _, _ in picks:
        artist = str(song.get("artist", "unknown"))
        counts[artist] = counts.get(artist, 0) + 1
    crowded = {artist: count for artist, count in counts.items() if count > MAX_SAME_ARTIST}
    if crowded:
        return Check("artist_spread", False, f"artist repeated too often: {crowded}")
    return Check("artist_spread", True, f"{len(counts)} distinct artist(s)")


def _confidence(plan: QueryPlan, picks: Sequence[Pick], revisions: int) -> float:
    if not picks:
        return 0.0
    top_score = picks[0][1]
    if top_score <= MIN_MATCH_SCORE:
        return 0.0
    score_part = min(1.0, top_score / CONFIDENCE_FULL_SCORE)
    requirement_checks = _requirement_checks(plan, picks)
    if requirement_checks:
        satisfied = sum(1 for check in requirement_checks if check.passed) / len(requirement_checks)
    else:
        satisfied = 1.0
    base = score_part * CONFIDENCE_SCORE_WEIGHT + satisfied * CONFIDENCE_REQUIREMENT_WEIGHT
    penalised = base * (REVISION_CONFIDENCE_PENALTY ** max(0, revisions))
    return round(min(1.0, max(0.0, penalised)), 2)


def critique(
    plan: QueryPlan, picks: Sequence[Pick], survivors: int, revisions: int = 0
) -> Verdict:
    """Run every check against one pass's results and score the agent's confidence."""
    checks: List[Check] = [_results_check(picks, survivors), _match_check(picks)]
    checks.extend(_requirement_checks(plan, picks))
    checks.extend(_veto_check(plan, picks))
    checks.append(_artist_spread_check(picks))
    return Verdict(checks=tuple(checks), confidence=_confidence(plan, picks, revisions))


def confidence_after_surrender(confidence: float, surrendered: int, original: int) -> float:
    """Scale confidence by the share of the original request still honoured.

    The critic only ever sees the *surviving* constraints, so a run that reached
    "all checks pass" by giving two requirements away would otherwise report the
    same confidence as one that satisfied everything.
    """
    if surrendered <= 0 or original <= 0:
        return round(max(0.0, min(1.0, confidence)), 2)
    honoured = max(0, original - surrendered) / original
    return round(max(MIN_SURRENDERED_CONFIDENCE, min(1.0, confidence * honoured)), 2)
