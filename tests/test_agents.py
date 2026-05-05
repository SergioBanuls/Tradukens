from tradukens.agents import CommandAgentAdapter, build_agent


def test_codex_adapter_uses_exec_then_resume():
    adapter = build_agent("codex", dry_run=True)

    assert isinstance(adapter, CommandAgentAdapter)
    assert adapter.executable == "codex"
    assert adapter.base_args == ["exec", "--skip-git-repo-check"]
    assert adapter.continue_args == ["exec", "resume", "--last", "--skip-git-repo-check"]


def test_codex_adapter_dry_run_includes_skip_git_repo_check(capsys):
    adapter = build_agent("codex", dry_run=True)

    assert adapter.send("hola") == 0

    output = capsys.readouterr().out
    assert "codex exec --skip-git-repo-check hola" in output


def test_claude_adapter_uses_print_continue():
    adapter = build_agent("claude", user_args=["--", "--model", "opus"], dry_run=True)

    assert isinstance(adapter, CommandAgentAdapter)
    assert adapter.executable == "claude"
    assert adapter.base_args == ["-p"]
    assert adapter.continue_args == ["-p", "--continue"]
    assert adapter.user_args == ["--model", "opus"]


def test_opencode_adapter_uses_run_continue():
    adapter = build_agent("opencode", dry_run=True)

    assert isinstance(adapter, CommandAgentAdapter)
    assert adapter.executable == "opencode"
    assert adapter.base_args == ["run"]
    assert adapter.continue_args == ["run", "--continue"]
