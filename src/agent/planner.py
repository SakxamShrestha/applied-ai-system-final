"""The revise step: pick the single cheapest concession that could unblock the critic.

Order of concessions, cheapest first:
  1. a violated requirement, least specific first (decade before genre)
  2. an untried ranking mode
  3. a threshold filter
  4. nothing left -> give up and report best effort

Explicit vetoes ("nothing too poppy") are never conceded: honouring them matters
more than a higher score.
"""

from typing import Optional, Tuple

from src.agent.constraints import relaxable
from src.agent.types import Constraint, QueryPlan, Verdict

MODE_PREFERENCE = ("balanced", "genre_first", "vibe_and_energy")
MODE_NOTE_PREFIX = "switched ranking mode to "
INITIAL_MODE_NOTE_PREFIX = "initial ranking mode "


def violated_requirements(plan: QueryPlan, verdict: Verdict) -> Tuple[Constraint, ...]:
    """Requirements the critic reported as unmet, least specific first."""
    failed = [check.constraint for check in verdict.problems if check.constraint is not None]
    requirements = [item for item in failed if item in plan.requirements]
    return tuple(sorted(requirements, key=lambda item: item.relax_priority))


def tried_modes(plan: QueryPlan) -> Tuple[str, ...]:
    """Modes already used in this run, read back from the plan's own notes."""
    switched = tuple(
        note[len(MODE_NOTE_PREFIX):] for note in plan.notes if note.startswith(MODE_NOTE_PREFIX)
    )
    initial = tuple(
        note[len(INITIAL_MODE_NOTE_PREFIX):]
        for note in plan.notes
        if note.startswith(INITIAL_MODE_NOTE_PREFIX)
    )
    return (plan.mode,) + switched + initial


def next_mode(plan: QueryPlan) -> Optional[str]:
    used = set(tried_modes(plan))
    for mode in MODE_PREFERENCE:
        if mode not in used:
            return mode
    return None


def revise(
    plan: QueryPlan, verdict: Verdict, prefer_mode_switch: bool = False
) -> Optional[QueryPlan]:
    """Return the next plan to try, or None when every concession is spent.

    prefer_mode_switch is set by the loop when the previous concession left the
    ranking unchanged: giving up more preferences clearly will not help, so try a
    different ranking strategy instead.
    """
    if verdict.accepted:
        return None

    if prefer_mode_switch:
        mode = next_mode(plan)
        if mode is not None:
            return plan.with_mode(mode)

    violated = violated_requirements(plan, verdict)
    if violated:
        return plan.without(violated[0])

    mode = next_mode(plan)
    if mode is not None:
        return plan.with_mode(mode)

    for candidate in relaxable(plan.filters):
        return plan.without(candidate)

    return None
