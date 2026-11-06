from pathlib import Path

from src.agent.loop import run_agent
from src.agent.trace import append_trace, render_trace
from src.recommender import load_songs


def test_render_trace_includes_every_stage_label():
    songs = load_songs("data/songs.csv")
    result = run_agent("chill acoustic 90s stuff for studying, nothing too poppy", songs)

    markdown = render_trace(result)

    for label in ("PLAN:", "ACT:", "CRITIC:", "ACTION:", "Reasoning trace"):
        assert label in markdown
    assert result.query in markdown
    assert "Pass 1" in markdown


def test_render_trace_explains_a_rejected_query():
    markdown = render_trace(run_agent("   ", []))

    assert "rejected" in markdown
    assert "guardrail" in markdown


def test_append_trace_creates_the_log_and_keeps_earlier_runs(tmp_path):
    songs = load_songs("data/songs.csv")
    log = tmp_path / "logs" / "agent_traces.md"

    append_trace(run_agent("chill lofi", songs), log)
    append_trace(run_agent("moody 1990s jazz", songs), log)

    content = log.read_text(encoding="utf-8")
    assert content.startswith("# Agent reasoning traces")
    assert content.count("## Query:") == 2
    assert "chill lofi" in content and "moody 1990s jazz" in content
