from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from tradukens.config import Paths, default_paths
from tradukens.translation import ArgosTranslator


CheckStatus = str


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    status: CheckStatus
    message: str


@dataclass(frozen=True)
class DoctorReport:
    checks: list[DiagnosticCheck]

    @property
    def ok(self) -> bool:
        return not any(check.status == "fail" for check in self.checks)


ExecutableFinder = Callable[[str], str | None]
ModuleChecker = Callable[[str], bool]
ArgosChecker = Callable[[Paths], bool]


def run_doctor(
    paths: Paths | None = None,
    executable_finder: ExecutableFinder = shutil.which,
    module_checker: ModuleChecker | None = None,
    argos_checker: ArgosChecker | None = None,
) -> DoctorReport:
    paths = paths or default_paths()
    module_checker = module_checker or _module_available
    argos_checker = argos_checker or _argos_available

    checks = [
        _python_check(),
        _executable_check("uv", executable_finder, required=False),
        _config_check(paths),
        _fasttext_check(paths),
        _argos_check(paths, argos_checker),
        _module_check("tiktoken", module_checker),
        _writable_path_check(paths.state_dir, "state directory"),
        _writable_path_check(paths.cache_dir, "cache directory"),
    ]
    checks.extend(
        _executable_check(agent, executable_finder, required=False)
        for agent in ("codex", "claude", "opencode")
    )
    return DoctorReport(checks)


def format_doctor_report(report: DoctorReport) -> str:
    lines = ["Tradukens doctor"]
    for check in report.checks:
        lines.append(f"[{check.status}] {check.name}: {check.message}")
    lines.append("")
    lines.append("Result: ready" if report.ok else "Result: setup required")
    return "\n".join(lines)


def doctor_report_json(report: DoctorReport) -> str:
    return json.dumps(
        {
            "ok": report.ok,
            "checks": [asdict(check) for check in report.checks],
        },
        ensure_ascii=False,
    )


def _python_check() -> DiagnosticCheck:
    version = platform.python_version()
    if (3, 12) <= sys.version_info[:2] < (3, 13):
        return DiagnosticCheck("python", "ok", version)
    return DiagnosticCheck("python", "fail", f"{version}; expected >=3.12,<3.13")


def _executable_check(
    executable: str,
    executable_finder: ExecutableFinder,
    required: bool,
) -> DiagnosticCheck:
    path = executable_finder(executable)
    if path:
        return DiagnosticCheck(executable, "ok", path)
    status = "fail" if required else "warn"
    return DiagnosticCheck(executable, status, "not found on PATH")


def _config_check(paths: Paths) -> DiagnosticCheck:
    if paths.config_file.exists():
        return DiagnosticCheck("config", "ok", str(paths.config_file))
    return DiagnosticCheck("config", "warn", f"missing; run setup to create {paths.config_file}")


def _fasttext_check(paths: Paths) -> DiagnosticCheck:
    if paths.fasttext_model.exists():
        return DiagnosticCheck("fastText model", "ok", str(paths.fasttext_model))
    return DiagnosticCheck(
        "fastText model",
        "fail",
        f"missing; run `tradukens setup --lang es`",
    )


def _argos_check(paths: Paths, argos_checker: ArgosChecker) -> DiagnosticCheck:
    try:
        available = argos_checker(paths)
    except Exception as exc:
        return DiagnosticCheck("Argos es->en", "fail", str(exc))
    if available:
        return DiagnosticCheck("Argos es->en", "ok", str(paths.argos_packages_dir))
    return DiagnosticCheck("Argos es->en", "fail", "missing; run `tradukens setup --lang es`")


def _module_check(module_name: str, module_checker: ModuleChecker) -> DiagnosticCheck:
    if module_checker(module_name):
        return DiagnosticCheck(module_name, "ok", "importable")
    return DiagnosticCheck(module_name, "fail", "not importable")


def _writable_path_check(path: Path, label: str) -> DiagnosticCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".tradukens-doctor.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        return DiagnosticCheck(label, "fail", f"not writable: {exc}")
    return DiagnosticCheck(label, "ok", str(path))


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _argos_available(paths: Paths) -> bool:
    os.environ["ARGOS_PACKAGE_DIR"] = str(paths.argos_packages_dir)
    os.environ["ARGOS_PACKAGES_DIR"] = str(paths.argos_packages_dir)
    os.environ["ARGOS_TRANSLATE_PACKAGES_DIR"] = str(paths.argos_packages_dir)
    return ArgosTranslator(paths.argos_packages_dir).available()
