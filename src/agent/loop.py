"""The agent loop: validate, plan, filter, act, critique, revise.

The loop owns production of the `user_prefs` dict that the original recommender
expects, so natural language is the only input the listener has to provide.
"""

from dataclasses import replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from src.agent.constraints import apply_filters, nearest_misses, prune_counts
from src.agent.critic import confidence_after_surrender, critique
from src.agent.planner import revise
from src.agent.query_parser import QueryValidationError, parse_query, validate_query
from src.agent.types import (
    STATUS_ACCEPTED,
    STATUS_BEST_EFFORT,
    STATUS_INFEASIBLE,
    STATUS_REJECTED,
    AgentResult,
    QueryPlan,
    TracePass,
)

# Revisions the agent is allowed before it settles for its best effort.
MAX_PASSES = 3
# Hard stop on loop turns, so no-op concessions cannot spin forever.
MAX_ITERATIONS = 6
DEFAULT_K = 5
NEAREST_MISS_LIMIT = 2

Pick = Tuple[Dict, float, str]
Enricher = Callable[[QueryPlan], QueryPlan]


def _signature(picks: Sequence[Pick]) -> Tuple[str, ...]:
    """The ranking the listener would see. Scores are excluded on purpose: a concession
    that shuffles scores but not the order has changed nothing worth a pass."""
    return tuple(str(song.get("title", "")) for song, _, _ in picks)


def _pick_summary(picks: Sequence[Pick]) -> Tuple[Tuple[str, str, float], ...]:
    return tuple(
        (str(song.get("title", "")), str(song.get("artist", "")), round(score, 2))
        for song, score, _ in picks
    )


def _rejected(query: str, error: QueryValidationError) -> AgentResult:
    suggestions = "\n".join(f"  - {example}" for example in error.suggestions)
    message = str(error)
    if suggestions:
        message = f"{message}\nTry something like:\n{suggestions}"
    return AgentResult(query=query, status=STATUS_REJECTED, message=message)


def _infeasible(plan: QueryPlan, songs: Sequence[Dict]) -> AgentResult:
    """No song satisfies the hard filters. Name the blocker and the closest misses."""
    counts = prune_counts(songs, plan.filters)
    blockers = sorted(counts.items(), key=lambda row: row[1], reverse=True)
    blocker_text = "; ".join(f"{item.label} (removes {count} of {len(songs)})" for item, count in blockers)
    lines = [
        f"No song in the catalog satisfies every hard requirement: {blocker_text}.",
    ]
    misses = nearest_misses(songs, plan.filters, limit=NEAREST_MISS_LIMIT)
    if misses:
        closest = "; ".join(
            f"{song['title']} ({song.get('genre', '?')}, fails {', '.join(item.label for item in failures)})"
            for song, _, failures in misses
        )
        lines.append(f"Closest available: {closest}.")
    lines.append("Relax one of those requirements and ask again.")
    return AgentResult(
        query=plan.query,
        status=STATUS_INFEASIBLE,
        message=" ".join(lines),
        plan=plan,
    )


def _surrendered(original: Tuple, plan: QueryPlan) -> Tuple[str, ...]:
    """Constraints present in the first plan but given up by the final one."""
    kept = set(plan.requirements) | set(plan.filters)
    return tuple(item.label for item in original if item not in kept)


def _final_message(status: str, plan: QueryPlan, surrendered: Tuple[str, ...]) -> str:
    switches = [note for note in plan.notes if note.startswith("switched")]
    if status == STATUS_ACCEPTED and not switches:
        return "Every requirement in the query was satisfied on the first attempt."
    if status == STATUS_ACCEPTED:
        return "Satisfied every requirement after " + "; ".join(switches) + "."
    if surrendered:
        return (
            "Best effort: the catalog has nothing matching "
            + ", ".join(surrendered)
            + ", so that part of the request was given up. Everything else still holds."
        )
    return "Best effort: no arrangement of the catalog satisfied every check."


def run_agent(
    query: str,
    songs: Sequence[Dict],
    k: int = DEFAULT_K,
    mode: Optional[str] = None,
    enrich: Optional[Enricher] = None,
) -> AgentResult:
    """Answer a free-text music request, self-checking and revising as needed."""
    try:
        cleaned = validate_query(query)
    except QueryValidationError as error:
        return _rejected(query if query is not None else "", error)

    # Lazy import keeps the loop importable even when run as a script from src/.
    from src.recommender import recommend_songs

    plan = parse_query(cleaned)
    if mode is not None:
        plan = replace(plan, mode=mode, notes=plan.notes + (f"mode forced to {mode}",))
    if enrich is not None:
        plan = enrich(plan)

    original_constraints = plan.requirements + plan.filters
    passes: List[TracePass] = []
    seen: List[Tuple[str, ...]] = []
    counted = 0
    last_picks: Sequence[Pick] = ()

    for iteration in range(1, MAX_ITERATIONS + 1):
        survivors = apply_filters(songs, plan.filters)
        if not survivors:
            return _infeasible(plan, songs)

        picks = recommend_songs(plan.prefs, list(survivors), k=k, mode=plan.mode)
        signature = _signature(picks)
        repeated = signature in seen
        seen.append(signature)
        verdict = critique(plan, picks, survivors=len(survivors), revisions=counted)
        last_picks = picks

        if verdict.accepted:
            surrendered = _surrendered(original_constraints, plan)
            # Accepting only because every requirement was surrendered is not success.
            status = STATUS_BEST_EFFORT if surrendered else STATUS_ACCEPTED
            passes.append(
                TracePass(iteration, plan, len(survivors), _pick_summary(picks), verdict, "accept")
            )
            return AgentResult(
                query=cleaned,
                status=status,
                recommendations=tuple(picks),
                confidence=confidence_after_surrender(
                    verdict.confidence, len(surrendered), len(original_constraints)
                ),
                passes=tuple(passes),
                message=_final_message(status, plan, surrendered),
                plan=plan,
                revisions=counted,
                surrendered=surrendered,
            )

        next_plan = revise(plan, verdict, prefer_mode_switch=repeated)
        if next_plan is None:
            passes.append(
                TracePass(iteration, plan, len(survivors), _pick_summary(picks), verdict, "exhausted")
            )
            break

        concession = next_plan.notes[-1] if next_plan.notes else "revised plan"
        action = f"no-op concession, trying next: {concession}" if repeated else f"revise: {concession}"
        passes.append(
            TracePass(iteration, plan, len(survivors), _pick_summary(picks), verdict, action)
        )
        if not repeated:
            counted += 1
        if counted >= MAX_PASSES:
            plan = next_plan
            break
        plan = next_plan

    verdict = passes[-1].verdict if passes else None
    surrendered = _surrendered(original_constraints, plan)
    return AgentResult(
        query=cleaned,
        status=STATUS_BEST_EFFORT,
        recommendations=tuple(last_picks),
        confidence=confidence_after_surrender(
            verdict.confidence if verdict else 0.0, len(surrendered), len(original_constraints)
        ),
        passes=tuple(passes),
        message=_final_message(STATUS_BEST_EFFORT, plan, surrendered),
        plan=plan,
        revisions=counted,
        surrendered=surrendered,
    )
