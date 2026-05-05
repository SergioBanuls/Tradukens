from __future__ import annotations

from tradukens.agents import AgentAdapter, AgentError
from tradukens.metrics import MetricsRecorder
from tradukens.translation import TranslationPipeline


class TradukensRepl:
    def __init__(
        self,
        agent: AgentAdapter,
        pipeline: TranslationPipeline,
        metrics: MetricsRecorder,
    ):
        self.agent = agent
        self.pipeline = pipeline
        self.metrics = metrics

    def run(self) -> int:
        print(f"Tradukens -> {self.agent.name}. Type :help for commands, :quit to exit.")
        while True:
            try:
                text = input(f"tradukens:{self.agent.name}> ")
            except EOFError:
                print()
                return 0
            except KeyboardInterrupt:
                print()
                continue

            if not text.strip():
                continue

            if text.strip() in {":quit", ":exit"}:
                return 0
            if text.strip() == ":help":
                self._print_help()
                continue
            if text.strip() == ":paste":
                text = self._read_paste_block()
                if not text.strip():
                    continue
            if self._looks_like_tradukens_shell_command(text):
                print(
                    "[tradukens] That is a shell command. Type :quit, then run it in your terminal."
                )
                continue

            result = self.pipeline.process(text)
            self.metrics.record(self.agent.name, result)
            self._print_result_status(result)
            if not result.sendable:
                continue

            try:
                exit_code = self.agent.send(result.output)
            except AgentError as exc:
                print(f"[tradukens] {exc}")
                return 1

            if exit_code != 0:
                print(f"[tradukens] Agent exited with status {exit_code}.")

    def _read_paste_block(self) -> str:
        print("[tradukens] Paste your prompt. End with a line containing :end.")
        lines: list[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == ":end":
                break
            lines.append(line)
        return "\n".join(lines)

    def _print_help(self) -> None:
        print("Commands:")
        print("  :paste  enter a multi-line prompt, ending with :end")
        print("  :quit   exit Tradukens")
        print("  /...    pass slash commands through without translation")

    def _looks_like_tradukens_shell_command(self, text: str) -> bool:
        stripped = text.strip()
        return stripped.startswith("uv run tradukens") or stripped.startswith("tradukens ")

    def _print_result_status(self, result) -> None:
        if result.error:
            print(f"[tradukens] {result.error}")
            return
        if result.warning:
            print(f"[tradukens] {result.warning}")
            return
        if result.action == "translated":
            print(
                "[tradukens] translated "
                f"{result.detection.language}->en "
                f"({result.detection.confidence:.2f}, {result.elapsed_ms} ms)"
            )
