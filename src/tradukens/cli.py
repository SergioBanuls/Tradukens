from __future__ import annotations

import argparse
import json
import sys

from tradukens import __version__
from tradukens.agents import AgentError, build_agent
from tradukens.config import default_paths, load_settings
from tradukens.doctor import doctor_report_json, format_doctor_report, run_doctor
from tradukens.metrics import MetricsRecorder
from tradukens.native_pty import NativePtyError, native_command, run_native_agent
from tradukens.repl import TradukensRepl
from tradukens.setup import SetupError, setup_spanish
from tradukens.tokens import DEFAULT_ENCODING, TokenCounterError, TokenSavings, compare_token_savings
from tradukens.translation import build_pipeline
from tradukens.update_check import check_for_update, format_update_notice


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 2

    paths = default_paths()
    settings = load_settings(paths)

    if args.command == "setup":
        if args.lang != "es":
            print("Only Spanish setup is supported in v1.", file=sys.stderr)
            return 2
        try:
            for message in setup_spanish(paths):
                print(message)
        except SetupError as exc:
            print(f"Setup failed: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.command == "doctor":
        report = run_doctor(paths)
        if args.json:
            print(doctor_report_json(report))
        else:
            print(format_doctor_report(report))
        return 0 if report.ok else 1

    if (
        args.command in {"codex", "claude", "opencode"}
        and not args.no_update_check
        and not args.dry_run
    ):
        _print_update_notice()

    pipeline = build_pipeline(paths, settings)
    metrics = MetricsRecorder(paths.metrics_file, enabled=settings.metrics_enabled)

    if args.command == "translate":
        text = _read_prompt_text(args.text)
        result = pipeline.process(text)
        metrics.record("translate", result)
        if args.json:
            print(
                json.dumps(
                    {
                        "action": result.action,
                        "detected_language": result.detection.language,
                        "confidence": result.detection.confidence,
                        "output": result.output,
                        "warning": result.warning,
                        "error": result.error,
                    },
                    ensure_ascii=False,
                )
            )
        else:
            if result.warning:
                print(f"[tradukens] {result.warning}", file=sys.stderr)
            if result.error:
                print(f"[tradukens] {result.error}", file=sys.stderr)
                return 1
            print(result.output)
        return 0 if result.sendable else 1

    if args.command == "savings":
        text = _read_prompt_text(args.text)
        result = pipeline.process(text)
        output = result.output if result.sendable else text
        try:
            savings = compare_token_savings(text, output, args.encoding)
        except TokenCounterError as exc:
            print(f"[tradukens] {exc}", file=sys.stderr)
            return 2

        if args.json:
            print(
                json.dumps(
                    _savings_payload(result, savings, output),
                    ensure_ascii=False,
                )
            )
        else:
            if result.warning:
                print(f"[tradukens] {result.warning}", file=sys.stderr)
            if result.error:
                print(f"[tradukens] {result.error}", file=sys.stderr)
            print(_format_savings_report(result, savings, output))
        return 0 if result.sendable else 1

    if args.command in {"codex", "claude", "opencode"}:
        if args.mode == "native" and not args.dry_run:
            try:
                return run_native_agent(
                    args.command,
                    native_command(args.command, args.agent_args),
                    pipeline,
                    metrics,
                )
            except NativePtyError as exc:
                print(f"[tradukens] {exc}", file=sys.stderr)
                return 1

        try:
            agent = build_agent(args.command, user_args=args.agent_args, dry_run=args.dry_run)
        except AgentError as exc:
            print(f"[tradukens] {exc}", file=sys.stderr)
            return 1
        return TradukensRepl(agent, pipeline, metrics).run()

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tradukens")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    setup_parser = subparsers.add_parser("setup", help="download local models")
    setup_parser.add_argument("--lang", default="es", help="source language to configure")

    doctor_parser = subparsers.add_parser("doctor", help="check installation health")
    doctor_parser.add_argument("--json", action="store_true", help="emit JSON")

    translate_parser = subparsers.add_parser("translate", help="translate a prompt")
    translate_parser.add_argument("text", nargs="*", help="text to translate; use - for stdin")
    translate_parser.add_argument("--json", action="store_true", help="emit JSON")

    savings_parser = subparsers.add_parser(
        "savings",
        help="compare token count before and after translation",
    )
    savings_parser.add_argument("text", nargs="*", help="text to compare; use - for stdin")
    savings_parser.add_argument(
        "--encoding",
        default=DEFAULT_ENCODING,
        help=f"tiktoken encoding to use; default: {DEFAULT_ENCODING}",
    )
    savings_parser.add_argument("--json", action="store_true", help="emit JSON")

    for agent_name in ("codex", "claude", "opencode"):
        agent_parser = subparsers.add_parser(
            agent_name,
            help=f"start {agent_name} through Tradukens",
        )
        agent_parser.add_argument(
            "--mode",
            choices=["native", "exec"],
            default="native",
            help="native runs the official TUI through a PTY; exec uses the older non-interactive wrapper",
        )
        agent_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="print exec-mode agent commands instead of executing them",
        )
        agent_parser.add_argument(
            "--no-update-check",
            action="store_true",
            help="skip the GitHub release update check on startup",
        )
        agent_parser.add_argument(
            "agent_args",
            nargs=argparse.REMAINDER,
            help="arguments passed to the underlying agent after --",
        )

    return parser


def _read_prompt_text(parts: list[str]) -> str:
    if not parts:
        if not sys.stdin.isatty():
            return sys.stdin.read()
        raise SystemExit("Provide text or pipe stdin.")
    if parts == ["-"]:
        return sys.stdin.read()
    return " ".join(parts)


def _print_update_notice() -> None:
    update = check_for_update(__version__)
    if update is not None:
        print(format_update_notice(update), file=sys.stderr)


def _savings_payload(result, savings: TokenSavings, output: str) -> dict:
    return {
        "action": result.action,
        "detected_language": result.detection.language,
        "confidence": result.detection.confidence,
        "detection_source": result.detection.source,
        "tokenizer": savings.original.encoding,
        "tokenizer_method": savings.original.method,
        "tokenizer_exact": savings.original.exact,
        "original_chars": result.original_chars,
        "translated_chars": len(output),
        "original_tokens": savings.original.tokens,
        "translated_tokens": savings.translated.tokens,
        "token_delta": savings.delta,
        "token_savings_percent": round(savings.percent, 2),
        "output": output,
        "warning": result.warning,
        "error": result.error,
    }


def _format_savings_report(result, savings: TokenSavings, output: str) -> str:
    direction = "saved" if savings.delta >= 0 else "extra"
    absolute_delta = abs(savings.delta)
    exactness = "exact" if savings.original.exact else "estimated"
    return "\n".join(
        [
            f"Action: {result.action}",
            (
                "Detected: "
                f"{result.detection.language} "
                f"({result.detection.confidence:.2f}, {result.detection.source})"
            ),
            (
                "Tokenizer: "
                f"{savings.original.encoding} "
                f"({savings.original.method}, {exactness})"
            ),
            f"Original: {savings.original.tokens} tokens, {result.original_chars} chars",
            f"Translated: {savings.translated.tokens} tokens, {len(output)} chars",
            f"Delta: {absolute_delta} tokens {direction} ({abs(savings.percent):.2f}%)",
            "",
            "Translated prompt:",
            output,
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
