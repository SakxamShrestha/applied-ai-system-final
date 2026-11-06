"""Render and persist the agent's reasoning trace.

The trace is the evidence that the loop plans, checks and revises, so it is written
to a committed log file rather than only printed.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from src.agent.types import AgentResult, TracePass

TRACE_LOG = Path(__file__).resolve().parents[2] / "logs" / "agent_traces.md"
MAX_PICKS_SHOWN = 5


def _pass_lines(item: TracePass) -> List[str]:
    picks = ", ".join(f"{title} ({score:.2f})" for title, _, score in item.picks[:MAX_PICKS_SHOWN])
    lines = [
        f"- **Pass {item.index}** — mode `{item.plan.mode}`, "
        f"{item.survivors} song(s) survived the filter stage",
        f"    - PLAN: {item.plan.describe_prefs()}",
    ]
    if item.plan.filters:
        lines.append(
            "    - FILTERS: " + "; ".join(constraint.label for constraint in item.plan.filters)
        )
    if item.plan.requirements:
        lines.append(
            "    - REQUIREMENTS: "
            + "; ".join(constraint.label for constraint in item.plan.requirements)
        )
    lines.append(f"    - ACT: {picks or '(nothing returned)'}")
    if item.verdict is not None:
        passed = sum(1 for check in item.verdict.checks if check.passed)
        lines.append(
            f"    - CRITIC: {passed}/{len(item.verdict.checks)} checks passed, "
            f"confidence {item.verdict.confidence:.2f}"
        )
        if item.verdict.problems:
            lines.append(f"    - PROBLEMS: {item.verdict.describe_problems()}")
    lines.append(f"    - ACTION: {item.action}")
    return lines


def render_trace(result: AgentResult) -> str:
    """The whole run as markdown, suitable for committing to ai_interactions.md."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    lines = [
        f"## Query: \"{result.query}\"",
        "",
        f"- Recorded: {stamp}",
        f"- Status: **{result.status}** (confidence {result.confidence:.2f}, "
        f"{result.revisions} revision(s))",
        f"- Outcome: {result.message}",
    ]
    if result.surrendered:
        lines.append(f"- Surrendered: {', '.join(result.surrendered)}")
    lines.extend(["", "### Reasoning trace", ""])
    if not result.passes:
        lines.append("- No passes ran: the query was rejected by the input guardrail.")
    for item in result.passes:
        lines.extend(_pass_lines(item))
    lines.append("")
    return "\n".join(lines)


def append_trace(result: AgentResult, path: Path = TRACE_LOG) -> Path:
    """Append one run to the trace log, creating it on first use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "" if path.exists() else "# Agent reasoning traces\n\nAppended automatically by `src/agent_cli.py`.\n\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(header + render_trace(result) + "\n---\n\n")
    return path


def append_traces(results: Iterable[AgentResult], path: Path = TRACE_LOG) -> Path:
    for result in results:
        append_trace(result, path)
    return path
