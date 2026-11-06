"""Immutable value objects shared by every stage of the agent loop.

Nothing in this module mutates: each stage returns a new object, so a trace is simply
the list of objects produced along the way.
"""

from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping, Optional, Tuple

# --- Status values for AgentResult -------------------------------------------------
STATUS_ACCEPTED = "accepted"
STATUS_BEST_EFFORT = "best_effort"
STATUS_INFEASIBLE = "infeasible"
STATUS_REJECTED = "rejected"

# --- Constraint kinds ---------------------------------------------------------------
# Filters prune the catalog before scoring. Requirements are checked by the critic
# against the chosen songs; they steer revision but never prune (a 20-song catalog
# cannot survive categorical filtering and still return a top 5).
KIND_FILTER = "filter"
KIND_REQUIREMENT = "requirement"

OP_EQUALS = "eq"
OP_NOT_EQUALS = "ne"
OP_AT_LEAST = "min"
OP_AT_MOST = "max"

# How readily the agent gives a constraint up: lowest number is surrendered first.
# Explicit vetoes (OP_NOT_EQUALS filters) are never surrendered at all.
RELAX_PRIORITY = {
    "release_decade": 10,
    "detailed_mood_tag": 20,
    "mood": 30,
    "genre": 40,
    "instrumentalness": 50,
    "speechiness": 50,
    "energy": 60,
}
DEFAULT_RELAX_PRIORITY = 70


@dataclass(frozen=True)
class Constraint:
    """One thing the listener asked for, in a form the agent can test and relax."""

    field: str
    op: str
    value: Any
    kind: str
    label: str
    source: str = "query"

    @property
    def relax_priority(self) -> int:
        return RELAX_PRIORITY.get(self.field, DEFAULT_RELAX_PRIORITY)

    @property
    def is_veto(self) -> bool:
        """Vetoes ('nothing too poppy') are honoured even at the cost of a worse score."""
        return self.op == OP_NOT_EQUALS

    def describe(self) -> str:
        return self.label


@dataclass(frozen=True)
class QueryPlan:
    """What the planner decided to do with a query, for one pass of the loop."""

    query: str
    prefs: Mapping[str, Any]
    filters: Tuple[Constraint, ...] = ()
    requirements: Tuple[Constraint, ...] = ()
    mode: str = "balanced"
    notes: Tuple[str, ...] = ()

    def without(self, constraint: Constraint) -> "QueryPlan":
        """Return a copy with one constraint dropped, plus the matching soft pref."""
        return replace(
            self,
            prefs={key: value for key, value in self.prefs.items() if key != constraint.field},
            filters=tuple(item for item in self.filters if item != constraint),
            requirements=tuple(item for item in self.requirements if item != constraint),
            notes=self.notes + (f"relaxed {constraint.describe()}",),
        )

    def with_mode(self, mode: str) -> "QueryPlan":
        return replace(self, mode=mode, notes=self.notes + (f"switched ranking mode to {mode}",))

    def with_additions(
        self,
        prefs: Optional[Mapping[str, Any]] = None,
        filters: Tuple[Constraint, ...] = (),
        requirements: Tuple[Constraint, ...] = (),
        notes: Tuple[str, ...] = (),
    ) -> "QueryPlan":
        """Return a copy merged with extra prefs/constraints. Existing prefs win."""
        merged = {**(prefs or {}), **self.prefs}
        known = {(item.field, item.op) for item in self.filters + self.requirements}
        return replace(
            self,
            prefs=merged,
            filters=self.filters + tuple(f for f in filters if (f.field, f.op) not in known),
            requirements=self.requirements + tuple(r for r in requirements if (r.field, r.op) not in known),
            notes=self.notes + notes,
        )

    def describe_prefs(self) -> str:
        parts = []
        for key, value in self.prefs.items():
            shown = "/".join(str(item) for item in value) if isinstance(value, (list, tuple)) else value
            parts.append(f"{key}={shown}")
        return ", ".join(parts) or "(no preferences)"


@dataclass(frozen=True)
class Check:
    """One critic assertion about a result set."""

    name: str
    passed: bool
    detail: str
    constraint: Optional[Constraint] = None


@dataclass(frozen=True)
class Verdict:
    """The critic's opinion of one pass."""

    checks: Tuple[Check, ...]
    confidence: float

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def problems(self) -> Tuple[Check, ...]:
        return tuple(check for check in self.checks if not check.passed)

    def describe_problems(self) -> str:
        return "; ".join(check.detail for check in self.problems) or "none"


@dataclass(frozen=True)
class TracePass:
    """One recorded plan/act/critique cycle."""

    index: int
    plan: QueryPlan
    survivors: int
    picks: Tuple[Tuple[str, str, float], ...]
    verdict: Optional[Verdict]
    action: str


@dataclass(frozen=True)
class AgentResult:
    """Final answer plus everything needed to explain how it was reached."""

    query: str
    status: str
    recommendations: Tuple[Tuple[Dict, float, str], ...] = ()
    confidence: float = 0.0
    passes: Tuple[TracePass, ...] = ()
    message: str = ""
    plan: Optional[QueryPlan] = None
    revisions: int = 0
    surrendered: Tuple[str, ...] = ()
