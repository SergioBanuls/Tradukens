from tradukens.repl import TradukensRepl


def test_detects_tradukens_shell_commands_inside_repl():
    repl = TradukensRepl(None, None, None)  # type: ignore[arg-type]

    assert repl._looks_like_tradukens_shell_command("uv run tradukens codex")
    assert repl._looks_like_tradukens_shell_command("tradukens codex")
    assert not repl._looks_like_tradukens_shell_command("arregla este bug")
