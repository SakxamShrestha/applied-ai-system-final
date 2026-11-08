"""Command line entry point for the agentic recommender.

Run from the project root:
    python -m src.agent_cli "chill lofi for studying"
    python -m src.agent_cli "1990s instrumental hip-hop" --trace
"""

import argparse
import sys
from typing import List, Sequence

from src.agent.hints import make_enricher
from src.agent.knowledge import build_index
from src.agent.profile import (
    DEFAULT_PROFILE_PATH,
    ProfileError,
    load_profile,
    make_profile_enricher,
)
from src.agent.loop import DEFAULT_K, run_agent
from src.agent.trace import append_trace, render_trace
from src.agent.voices import VOICE_PLAIN, VOICES, explain_all
from src.agent.types import (
    STATUS_ACCEPTED,
    STATUS_BEST_EFFORT,
    STATUS_INFEASIBLE,
    STATUS_REJECTED,
    AgentResult,
)
from src.main import SONGS_CSV, format_table
from src.recommender import WEIGHT_STRATEGIES, load_songs

EXIT_OK = 0
EXIT_LOAD_ERROR = 1
EXIT_REJECTED = 2
EXIT_INFEASIBLE = 3
EXIT_PROFILE_ERROR = 4

STATUS_LABELS = {
    STATUS_ACCEPTED: "ACCEPTED",
    STATUS_BEST_EFFORT: "BEST EFFORT",
    STATUS_INFEASIBLE: "INFEASIBLE",
    STATUS_REJECTED: "REJECTED",
}
EXIT_CODES = {
    STATUS_ACCEPTED: EXIT_OK,
    STATUS_BEST_EFFORT: EXIT_OK,
    STATUS_INFEASIBLE: EXIT_INFEASIBLE,
    STATUS_REJECTED: EXIT_REJECTED,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.agent_cli",
        description="Ask for music in plain English; the agent plans, checks and revises.",
    )
    parser.add_argument("query", nargs="?", default="", help="what you want to listen to")
    parser.add_argument("-k", "--top", type=int, default=DEFAULT_K, help="how many songs to return")
    parser.add_argument(
        "--mode",
        choices=sorted(WEIGHT_STRATEGIES),
        help="force a ranking mode instead of letting the planner choose",
    )
    parser.add_argument(
        "--voice",
        choices=VOICES,
        default=VOICE_PLAIN,
        help="explanation style for the recommendations",
    )
    parser.add_argument("--trace", action="store_true", help="print the full reasoning trace")
    parser.add_argument(
        "--me",
        action="store_true",
        help=f"apply your saved taste profile ({DEFAULT_PROFILE_PATH.name}) as background preferences",
    )
    parser.add_argument(
        "--profile",
        metavar="PATH",
        help="apply a specific profile file instead of the default",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="skip knowledge retrieval, so only the query itself shapes the plan",
    )
    parser.add_argument(
        "--no-log", action="store_true", help="do not append this run to logs/agent_traces.md"
    )
    return parser


def render_result(result: AgentResult, show_trace: bool, voice: str = VOICE_PLAIN) -> str:
    label = STATUS_LABELS.get(result.status, result.status.upper())
    lines: List[str] = [
        f'Query: "{result.query}"',
        f"Status: {label} | confidence {result.confidence:.2f} | "
        f"{result.revisions} revision(s) | {len(result.passes)} pass(es)",
        f"Agent: {result.message}",
    ]
    if result.plan is not None and result.recommendations:
        lines.append(f"Final plan: {result.plan.describe_prefs()} | mode {result.plan.mode}")
        for note in result.plan.notes:
            if note.startswith("knowledge: retrieved"):
                lines.append(f"Retrieved: {note[len('knowledge: retrieved '):]}")
            elif note.startswith("profile:"):
                lines.append(f"From profile: {note[len('profile: '):]}")
    if result.recommendations:
        lines.extend(["", format_table(list(result.recommendations))])
        lines.extend(["", f"Why these ({voice} voice):"])
        lines.extend(
            f"  {rank}. {text}"
            for rank, text in enumerate(explain_all(result.recommendations, voice), start=1)
        )
    if show_trace:
        lines.extend(["", render_trace(result)])
    return "\n".join(lines)


def main(argv: Sequence[str] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        songs = load_songs(str(SONGS_CSV))
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: could not load songs. {error}", file=sys.stderr)
        return EXIT_LOAD_ERROR
    if args.top < 1:
        print("Error: --top must be at least 1.", file=sys.stderr)
        return EXIT_REJECTED

    index = None if args.no_rag else build_index(songs)
    profile = None
    if args.me or args.profile:
        try:
            profile = load_profile(args.profile)
        except ProfileError as error:
            print(f"Error: {error}", file=sys.stderr)
            return EXIT_PROFILE_ERROR
        print(f"Profile: {profile.describe()}")
        for warning in profile.warnings:
            print(f"  warning: {warning}", file=sys.stderr)

    if profile is not None:
        enrich = make_profile_enricher(profile, index)
    elif index is not None:
        enrich = make_enricher(index)
    else:
        enrich = None

    result = run_agent(args.query, songs, k=args.top, mode=args.mode, enrich=enrich)
    print(render_result(result, show_trace=args.trace, voice=args.voice))
    if not args.no_log:
        log_path = append_trace(result)
        print(f"\nTrace appended to {log_path.relative_to(log_path.parents[1])}")
    return EXIT_CODES.get(result.status, EXIT_OK)


if __name__ == "__main__":
    sys.exit(main())
