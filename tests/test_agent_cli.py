import pytest

from src.agent_cli import EXIT_OK, EXIT_REJECTED, build_parser, main


def test_cli_prints_a_table_for_a_good_query(capsys):
    code = main(["chill lofi for studying", "--no-log"])

    output = capsys.readouterr().out
    assert code == EXIT_OK
    assert "Status: ACCEPTED" in output
    assert "Library Rain" in output
    assert "Rank" in output


def test_cli_reports_revisions_for_an_over_constrained_query(capsys):
    code = main(["chill acoustic 90s stuff for studying, nothing too poppy", "--no-log"])

    output = capsys.readouterr().out
    assert code == EXIT_OK
    assert "Status: BEST EFFORT" in output
    assert "revision(s)" in output


def test_cli_rejects_an_empty_query_with_a_nonzero_exit_code(capsys):
    code = main(["", "--no-log"])

    output = capsys.readouterr().out
    assert code == EXIT_REJECTED
    assert "Status: REJECTED" in output
    assert "Try something like" in output


def test_cli_rejects_unknown_vocabulary(capsys):
    code = main(["asdfghjkl qwerty", "--no-log"])

    assert code == EXIT_REJECTED
    assert "recognise" in capsys.readouterr().out


def test_cli_rejects_a_nonsense_top_k(capsys):
    code = main(["chill lofi", "--top", "0", "--no-log"])

    assert code == EXIT_REJECTED
    assert "--top must be at least 1" in capsys.readouterr().err


def test_cli_trace_flag_prints_the_reasoning_trace(capsys):
    main(["moody 1990s jazz", "--trace", "--no-log"])

    output = capsys.readouterr().out
    assert "Reasoning trace" in output
    assert "CRITIC:" in output


def test_cli_mode_flag_is_validated():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["chill lofi", "--mode", "not_a_mode"])


def test_retrieval_changes_the_ranking_for_a_situational_query(capsys):
    main(["something for deep focus while coding", "--no-rag", "--no-log", "-k", "3"])
    without_rag = capsys.readouterr().out

    main(["something for deep focus while coding", "--no-log", "-k", "3"])
    with_rag = capsys.readouterr().out

    # Without the corpus the top pick is a vocal acoustic track, which is wrong for
    # focus listening; retrieval pushes the instrumental tracks up.
    assert "Porch Light Letters" in without_rag
    assert "Porch Light Letters" not in with_rag
    assert "Instrumentalness proximity" in with_rag
    assert "Retrieved:" in with_rag and "Retrieved:" not in without_rag
