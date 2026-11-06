"""Streamlit front end for the agentic recommender.

Run from the project root:
    streamlit run src/app.py

The CLI (`python -m src.agent_cli`) remains the reference interface; this page is
the same agent with a form around it.
"""

import sys
from pathlib import Path
from typing import Dict, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.hints import make_enricher  # noqa: E402
from src.agent.knowledge import build_index  # noqa: E402
from src.agent.loop import DEFAULT_K, run_agent  # noqa: E402
from src.agent.trace import render_trace  # noqa: E402
from src.agent.types import (  # noqa: E402
    STATUS_ACCEPTED,
    STATUS_BEST_EFFORT,
    STATUS_INFEASIBLE,
    STATUS_REJECTED,
    AgentResult,
)
from src.agent.voices import VOICE_PLAIN, VOICES, explain_all  # noqa: E402
from src.main import SONGS_CSV  # noqa: E402
from src.recommender import WEIGHT_STRATEGIES, load_songs  # noqa: E402

AUTO_MODE = "auto (let the planner choose)"
EXAMPLE_QUERIES = (
    "chill lofi for studying",
    "high energy hip hop to hype me up",
    "chill acoustic 90s stuff for studying, nothing too poppy",
    "1990s instrumental hip-hop",
    "instrumental lyrical music",
)


def result_rows(result: AgentResult, voice: str = VOICE_PLAIN) -> List[Dict]:
    """Flatten recommendations into table rows. Pure, so it is unit-testable."""
    voiced = explain_all(result.recommendations, voice)
    return [
        {
            "Rank": rank,
            "Title": song.get("title", ""),
            "Artist": song.get("artist", ""),
            "Genre": song.get("genre", ""),
            "Decade": song.get("release_decade", ""),
            "Score": round(score, 2),
            "Why": text,
        }
        for rank, ((song, score, _), text) in enumerate(zip(result.recommendations, voiced), start=1)
    ]


def retrieved_notes(result: AgentResult) -> Sequence[str]:
    if result.plan is None:
        return ()
    return tuple(note for note in result.plan.notes if note.startswith("knowledge:"))


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Agentic Music Recommender", page_icon="🎵", layout="wide")
    st.title("🎵 Agentic Music Recommender")
    st.caption(
        "Ask in plain English. The agent plans a search, filters the catalog, scores it, "
        "critiques its own answer and revises when a requirement is unmet."
    )

    try:
        songs = load_songs(str(SONGS_CSV))
    except (FileNotFoundError, ValueError) as error:
        st.error(f"Could not load the catalog: {error}")
        return

    with st.sidebar:
        st.header("Settings")
        voice = st.selectbox("Explanation voice", VOICES, index=VOICES.index(VOICE_PLAIN))
        top_k = st.slider("How many songs", min_value=1, max_value=10, value=DEFAULT_K)
        mode = st.selectbox("Ranking mode", (AUTO_MODE,) + tuple(sorted(WEIGHT_STRATEGIES)))
        use_knowledge = st.checkbox("Use knowledge retrieval", value=True)
        st.caption(f"Catalog: {len(songs)} songs")

    query = st.text_input("What do you want to listen to?", value=EXAMPLE_QUERIES[0])
    st.caption("Examples: " + " · ".join(f"`{example}`" for example in EXAMPLE_QUERIES[1:]))

    if not st.button("Recommend", type="primary"):
        return

    enrich = make_enricher(build_index(songs)) if use_knowledge else None
    result = run_agent(
        query,
        songs,
        k=top_k,
        mode=None if mode == AUTO_MODE else mode,
        enrich=enrich,
    )

    if result.status == STATUS_REJECTED:
        st.error(result.message)
        return
    if result.status == STATUS_INFEASIBLE:
        st.warning(result.message)
        return

    banner = st.success if result.status == STATUS_ACCEPTED else st.info
    banner(result.message)

    left, middle, right = st.columns(3)
    left.metric("Status", result.status.replace("_", " "))
    middle.metric("Confidence", f"{result.confidence:.2f}")
    right.metric("Revisions", result.revisions)

    st.dataframe(result_rows(result, voice), use_container_width=True, hide_index=True)

    if result.surrendered:
        st.warning("Given up to find an answer: " + ", ".join(result.surrendered))

    notes = retrieved_notes(result)
    if notes:
        with st.expander("Knowledge retrieved for this query"):
            for note in notes:
                st.markdown(f"- {note[len('knowledge: '):]}")

    with st.expander("Reasoning trace"):
        st.markdown(render_trace(result))


if __name__ == "__main__":
    main()
