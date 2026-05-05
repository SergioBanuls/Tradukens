from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Protocol


class AgentError(RuntimeError):
    pass


class AgentAdapter(Protocol):
    name: str

    def send(self, prompt: str) -> int:
        pass


@dataclass
class CommandAgentAdapter:
    name: str
    executable: str
    base_args: list[str]
    continue_args: list[str]
    user_args: list[str] = field(default_factory=list)
    dry_run: bool = False
    _has_session: bool = False

    def send(self, prompt: str) -> int:
        if shutil.which(self.executable) is None:
            raise AgentError(f"Executable not found: {self.executable}")

        args = self.continue_args if self._has_session else self.base_args
        command = [self.executable, *args, *self.user_args, prompt]
        if self.dry_run:
            print(" ".join(_shell_quote(part) for part in command))
            self._has_session = True
            return 0

        completed = subprocess.run(command, check=False)
        if completed.returncode == 0:
            self._has_session = True
        return int(completed.returncode)


def build_agent(name: str, user_args: list[str] | None = None, dry_run: bool = False) -> AgentAdapter:
    user_args = _clean_remainder(user_args or [])
    if name == "codex":
        return CommandAgentAdapter(
            name="codex",
            executable="codex",
            base_args=["exec", "--skip-git-repo-check"],
            continue_args=["exec", "resume", "--last", "--skip-git-repo-check"],
            user_args=user_args,
            dry_run=dry_run,
        )
    if name == "claude":
        return CommandAgentAdapter(
            name="claude",
            executable="claude",
            base_args=["-p"],
            continue_args=["-p", "--continue"],
            user_args=user_args,
            dry_run=dry_run,
        )
    if name == "opencode":
        return CommandAgentAdapter(
            name="opencode",
            executable="opencode",
            base_args=["run"],
            continue_args=["run", "--continue"],
            user_args=user_args,
            dry_run=dry_run,
        )
    raise AgentError(f"Unsupported agent: {name}")


def _clean_remainder(args: list[str]) -> list[str]:
    if args and args[0] == "--":
        return args[1:]
    return args


def _shell_quote(value: str) -> str:
    if not value:
        return "''"
    safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-=/:.,")
    if all(character in safe for character in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"
