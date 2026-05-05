from tradukens.native_pty import InputInterceptor, native_command


def erase(text: str) -> bytes:
    return b"\b \b" * len(text)


def backspaces(text: str) -> bytes:
    return b"\x7f" * len(text)


class FakePipeline:
    def __init__(self, output: str):
        self.output = output
        self.inputs: list[str] = []

    def process(self, text: str):
        self.inputs.append(text)
        return FakeResult(text, self.output)


class FakeResult:
    def __init__(self, original: str, output: str):
        self.output = output
        self.action = "translated" if output != original else "unchanged_english"
        self.sendable = True
        self.original_chars = len(original)
        self.output_chars = len(output)
        self.elapsed_ms = 0
        self.warning = None
        self.error = None
        self.detection = FakeDetection()


class FakeDetection:
    language = "es"
    confidence = 0.99
    source = "test"


class FakeMetrics:
    def __init__(self):
        self.events = []

    def record(self, agent: str, result) -> None:
        self.events.append((agent, result.action))


def collect_output(interceptor: InputInterceptor, data: bytes) -> tuple[bytes, bytes]:
    child_chunks: list[bytes] = []
    stdout_chunks: list[bytes] = []
    interceptor.handle(data, child_chunks.append, stdout_chunks.append)
    return b"".join(child_chunks), b"".join(stdout_chunks)


def make_interceptor(pipeline, metrics) -> InputInterceptor:
    return InputInterceptor(
        pipeline,
        metrics,
        "codex",
        clear_delay_seconds=0.0,
    )  # type: ignore[arg-type]


def test_interceptor_replaces_prompt_on_enter():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"hola\r")

    assert child_output == b"hola" + backspaces("hola") + b"hello"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]
    assert metrics.events == [("codex", "translated")]


def test_interceptor_sends_reviewed_prompt_on_next_enter():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"hola\r\r")

    assert child_output == b"hola" + backspaces("hola") + b"hello\r"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]
    assert metrics.events == [("codex", "translated")]


def test_interceptor_treats_lf_as_newline_for_ctrl_j():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"hola\n")

    assert child_output == b"hola\n"
    assert stdout_output == b""
    assert pipeline.inputs == []
    assert metrics.events == []


def test_interceptor_treats_enhanced_enter_as_submit():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"hola\x1b[13;1u")

    assert child_output == b"hola" + backspaces("hola") + b"hello"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]
    assert metrics.events == [("codex", "translated")]


def test_interceptor_ignores_enhanced_key_release_reports_for_translation():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(
        interceptor,
        b"h\x1b[104;1:3uo\x1b[111;1:3ula\x1b[97;1:3u\r",
    )

    assert child_output == b"hola" + backspaces("hola") + b"hello"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]
    assert metrics.events == [("codex", "translated")]


def test_interceptor_does_not_translate_slash_commands():
    pipeline = FakePipeline("translated")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"/model\r")

    assert child_output == b"/model\r"
    assert stdout_output == b""
    assert pipeline.inputs == []
    assert metrics.events == []


def test_interceptor_handles_backspace_before_enter():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"holax\x7f\r")

    assert child_output == b"holax\x7f" + backspaces("hola") + b"hello"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]


def test_interceptor_treats_shift_enter_as_local_newline():
    pipeline = FakePipeline("hello\nworld")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"hola\x1b[13;2umundo\r")

    assert child_output == b"hola\nmundo" + backspaces("hola\nmundo") + b"hello\nworld"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola\nmundo"]
    assert metrics.events == [("codex", "translated")]


def test_interceptor_treats_escape_enter_as_local_newline():
    pipeline = FakePipeline("hello\nworld")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"hola\x1b\rmundo\r")

    assert child_output == b"hola\nmundo" + backspaces("hola\nmundo") + b"hello\nworld"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola\nmundo"]


def test_interceptor_forwards_csi_terminal_response_without_echoing():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"\x1b[4;2R")

    assert child_output == b"\x1b[4;2R"
    assert stdout_output == b""
    assert pipeline.inputs == []


def test_interceptor_keeps_buffer_after_csi_terminal_response():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"ho\x1b[4;2Rla\r")

    assert child_output == b"ho\x1b[4;2Rla" + backspaces("hola") + b"hello"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]


def test_interceptor_keeps_buffer_after_private_csi_terminal_response():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(
        interceptor,
        b"ho\x1b[?62;22;52cla\x1b[?2026;2$y\r",
    )

    assert (
        child_output
        == b"ho\x1b[?62;22;52cla\x1b[?2026;2$y" + backspaces("hola") + b"hello"
    )
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]


def test_interceptor_forwards_osc_terminal_response_without_echoing():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(
        interceptor,
        b"\x1b]10;rgb:ffff/ffff/ffff\x07",
    )

    assert child_output == b"\x1b]10;rgb:ffff/ffff/ffff\x07"
    assert stdout_output == b""
    assert pipeline.inputs == []


def test_interceptor_keeps_buffer_after_osc_terminal_response():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(
        interceptor,
        b"ho\x1b]10;rgb:ffff/ffff/ffff\x07la\r",
    )

    assert (
        child_output
        == b"ho\x1b]10;rgb:ffff/ffff/ffff\x07la" + backspaces("hola") + b"hello"
    )
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]


def test_interceptor_keeps_buffer_after_focus_events():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"ho\x1b[Ila\x1b[O\r")

    assert child_output == b"ho\x1b[Ila\x1b[O" + backspaces("hola") + b"hello"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]


def test_interceptor_keeps_buffer_after_bracketed_paste_markers():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(interceptor, b"\x1b[200~hola\x1b[201~\r")

    assert child_output == b"\x1b[200~hola\x1b[201~" + backspaces("hola") + b"hello"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]


def test_interceptor_keeps_buffer_after_st_terminated_terminal_response():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)

    child_output, stdout_output = collect_output(
        interceptor,
        b"ho\x1bP>|ghostty 1.3.1\x1b\\la\r",
    )

    assert (
        child_output
        == b"ho\x1bP>|ghostty 1.3.1\x1b\\la" + backspaces("hola") + b"hello"
    )
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]


def test_interceptor_ignores_claude_terminal_handshake_before_prompt():
    pipeline = FakePipeline("hello")
    metrics = FakeMetrics()
    interceptor = make_interceptor(pipeline, metrics)
    handshake = (
        b"\x1b[I"
        b"\x1b]10;rgb:ffff/ffff/ffff\x1b\\"
        b"\x1b]11;rgb:2828/2c2c/3434\x1b\\"
        b"\x1b[O"
        b"\x1b[33;3R"
        b"\x1b[I"
        b"\x1bP>|ghostty 1.3.1\x1b\\"
        b"\x1b[?62;22;52c"
        b"\x1b[?2026;2$y"
        b"\x1b[?62;22;52c"
    )

    child_output, stdout_output = collect_output(interceptor, handshake + b"hola\r")

    assert child_output == handshake + b"hola" + backspaces("hola") + b"hello"
    assert stdout_output == b"Traduciendo..." + erase("Traduciendo...")
    assert pipeline.inputs == ["hola"]


def test_native_command_builds_official_agent_command():
    assert native_command("codex", []) == ["codex"]
    assert native_command("claude", ["--", "--model", "opus"]) == ["claude", "--model", "opus"]
