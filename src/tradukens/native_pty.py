from __future__ import annotations

import os
import select
import signal
import shutil
import struct
import sys
import termios
import time
import tty
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tradukens.metrics import MetricsRecorder
from tradukens.translation import TranslationPipeline


WriteFn = Callable[[bytes], None]


class NativePtyError(RuntimeError):
    pass


@dataclass
class InputInterceptor:
    pipeline: TranslationPipeline
    metrics: MetricsRecorder
    agent_name: str
    status_text: str = "Traduciendo..."
    clear_delay_seconds: float = 0.03

    def __post_init__(self) -> None:
        self._raw_line = bytearray()
        self._escape_state: str | None = None
        self._escape_buffer = bytearray()
        self._buffer_dirty = False
        self._pending_review = False
        self._in_bracketed_paste = False
        self._skip_next_paste_lf = False

    def handle(
        self,
        data: bytes,
        write_child: WriteFn,
        write_stdout: WriteFn | None = None,
    ) -> None:
        _debug_keys(data)
        write_stdout = write_stdout or write_child
        for byte in data:
            self._handle_byte(byte, write_child, write_stdout)

    def _handle_byte(self, byte: int, write_child: WriteFn, write_stdout: WriteFn) -> None:
        if self._skip_next_paste_lf and byte != 0x0A:
            self._skip_next_paste_lf = False

        if self._escape_state is not None:
            self._handle_escape_byte(byte, write_child, write_stdout)
            return

        if byte == 0x1B:
            self._escape_state = "esc"
            self._escape_buffer = bytearray([byte])
            return

        if byte == 0x0A:
            if self._in_bracketed_paste and self._skip_next_paste_lf:
                self._skip_next_paste_lf = False
                return
            self._insert_newline(write_child)
            return

        if byte == 0x0D:
            if self._in_bracketed_paste:
                self._insert_pasted_carriage_return(write_child)
                return
            self._handle_enter(bytes([byte]), write_child, write_stdout)
            return

        if byte in (0x7F, 0x08):
            if self._raw_line:
                self._remove_last_character()
            write_child(bytes([byte]))
            return

        if byte == 0x03:
            write_child(bytes([byte]))
            self._raw_line.clear()
            self._buffer_dirty = False
            self._pending_review = False
            self._in_bracketed_paste = False
            self._skip_next_paste_lf = False
            return

        if byte == 0x15:
            write_child(bytes([byte]))
            self._kill_line_start()
            return

        if byte >= 0x20:
            self._raw_line.append(byte)
            write_child(bytes([byte]))
            return

        write_child(bytes([byte]))

    def _handle_escape_byte(self, byte: int, write_child: WriteFn, write_stdout: WriteFn) -> None:
        self._escape_buffer.append(byte)

        if self._escape_state == "esc":
            if byte == 0x5B:
                self._escape_state = "csi"
                return
            if byte == 0x5D:
                self._escape_state = "osc"
                return
            if byte in (0x50, 0x58, 0x5E, 0x5F):
                self._escape_state = "string_control"
                return
            if byte == 0x4F:
                self._escape_state = "ss3"
                return
            self._finish_escape(write_child, write_stdout)
            return

        if self._escape_state == "csi":
            if 0x40 <= byte <= 0x7E:
                self._finish_escape(write_child, write_stdout)
            return

        if self._escape_state == "ss3":
            if 0x40 <= byte <= 0x7E:
                self._finish_escape(write_child, write_stdout)
            return

        if self._escape_state == "osc":
            if byte == 0x07:
                self._finish_escape(write_child, write_stdout)
                return
            if byte == 0x1B:
                self._escape_state = "osc_esc"
                return
            return

        if self._escape_state == "osc_esc":
            if byte == 0x5C:
                self._finish_escape(write_child, write_stdout)
                return
            self._escape_state = "osc"
            return

        if self._escape_state == "string_control":
            if byte == 0x1B:
                self._escape_state = "string_control_esc"
            return

        if self._escape_state == "string_control_esc":
            if byte == 0x5C:
                self._finish_escape(write_child, write_stdout)
                return
            self._escape_state = "string_control"
            return

        self._finish_escape(write_child, write_stdout)

    def _finish_escape(self, write_child: WriteFn, write_stdout: WriteFn) -> None:
        sequence = bytes(self._escape_buffer)
        if _is_plain_enter(sequence):
            self._handle_enter(sequence, write_child, write_stdout)
        elif _is_shift_enter(sequence):
            self._insert_newline(write_child)
        elif _is_bracketed_paste_start(sequence):
            self._in_bracketed_paste = True
            self._skip_next_paste_lf = False
            write_child(sequence)
        elif _is_bracketed_paste_end(sequence):
            self._in_bracketed_paste = False
            self._skip_next_paste_lf = False
            write_child(sequence)
        elif not self._raw_line or _is_terminal_response(sequence):
            write_child(sequence)
        elif _is_enhanced_key_release(sequence):
            pass
        else:
            write_child(sequence)
            self._buffer_dirty = True
        self._escape_state = None
        self._escape_buffer.clear()

    def _handle_enter(self, enter: bytes, write_child: WriteFn, write_stdout: WriteFn) -> None:
        current = self._decode_line()
        stripped = current.strip()
        if not stripped:
            write_child(enter)
            self._raw_line.clear()
            self._pending_review = False
            return

        if self._pending_review:
            write_child(enter)
            self._raw_line.clear()
            self._buffer_dirty = False
            self._pending_review = False
            return

        if stripped.startswith("/"):
            write_child(enter)
            self._raw_line.clear()
            self._buffer_dirty = False
            self._pending_review = False
            return

        if self._buffer_dirty:
            write_child(enter)
            self._raw_line.clear()
            self._buffer_dirty = False
            self._pending_review = False
            return

        write_child(_backspace_current_prompt(current))
        if self.clear_delay_seconds > 0:
            time.sleep(self.clear_delay_seconds)
        status = self.status_text.encode("utf-8")
        write_stdout(status)
        result = self.pipeline.process(stripped)
        write_stdout(_erase_displayed_text(self.status_text))
        self.metrics.record(self.agent_name, result)
        output = result.output if result.sendable else stripped
        write_child(_encode_prompt_for_child(output))
        self._raw_line = bytearray(output.encode("utf-8"))
        self._buffer_dirty = False
        self._pending_review = True

    def _insert_newline(self, write_child: WriteFn) -> None:
        self._raw_line.extend(b"\n")
        write_child(b"\n")

    def _insert_pasted_carriage_return(self, write_child: WriteFn) -> None:
        self._raw_line.extend(b"\n")
        write_child(b"\n")
        self._skip_next_paste_lf = True

    def _decode_line(self) -> str:
        return self._raw_line.decode("utf-8", errors="ignore")

    def _remove_last_character(self) -> None:
        current = self._decode_line()
        self._raw_line = bytearray(current[:-1].encode("utf-8"))

    def _kill_line_start(self) -> None:
        current = self._decode_line()
        prefix, separator, suffix = current.rpartition("\n")
        if separator:
            self._raw_line = bytearray((prefix + separator).encode("utf-8"))
        else:
            self._raw_line.clear()


def run_native_agent(
    agent_name: str,
    command: list[str],
    pipeline: TranslationPipeline,
    metrics: MetricsRecorder,
) -> int:
    executable = shutil.which(command[0])
    if executable is None:
        raise NativePtyError(f"Executable not found: {command[0]}")

    pid, fd = os.forkpty()
    if pid == 0:
        os.execvp(executable, command)

    _sync_window_size(fd)
    previous_winch = signal.getsignal(signal.SIGWINCH)

    def handle_winch(signum, frame):
        _sync_window_size(fd)
        if callable(previous_winch):
            previous_winch(signum, frame)

    signal.signal(signal.SIGWINCH, handle_winch)
    interceptor = InputInterceptor(pipeline, metrics, agent_name)

    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()
    previous_termios = termios.tcgetattr(stdin_fd)

    try:
        tty.setraw(stdin_fd)
        while True:
            readable, _, _ = select.select([stdin_fd, fd], [], [])
            if fd in readable:
                try:
                    output = os.read(fd, 65536)
                except OSError:
                    break
                if not output:
                    break
                os.write(stdout_fd, output)

            if stdin_fd in readable:
                user_input = os.read(stdin_fd, 4096)
                if not user_input:
                    break
                interceptor.handle(
                    user_input,
                    lambda chunk: os.write(fd, chunk),
                    lambda chunk: os.write(stdout_fd, chunk),
                )
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, previous_termios)
        signal.signal(signal.SIGWINCH, previous_winch)

    _, status = os.waitpid(pid, 0)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1


def native_command(agent_name: str, user_args: list[str]) -> list[str]:
    args = _clean_remainder(user_args)
    if agent_name == "codex":
        return ["codex", *args]
    if agent_name == "claude":
        return ["claude", *args]
    if agent_name == "opencode":
        return ["opencode", *args]
    raise NativePtyError(f"Unsupported agent: {agent_name}")


def _clean_remainder(args: list[str]) -> list[str]:
    if args and args[0] == "--":
        return args[1:]
    return args


def _sync_window_size(fd: int) -> None:
    try:
        size = fcntl_ioctl_winsize(sys.stdout.fileno())
    except OSError:
        return
    try:
        import fcntl

        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
    except OSError:
        return


def fcntl_ioctl_winsize(fd: int) -> bytes:
    import fcntl

    return fcntl.ioctl(fd, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))


def _erase_displayed_text(text: str) -> bytes:
    lines = text.split("\n")
    if len(lines) == 1:
        return b"\b \b" * len(text)

    chunks: list[bytes] = [b"\r\x1b[K"]
    for _line in reversed(lines[:-1]):
        chunks.append(b"\x1b[1A\r\x1b[K")
    return b"".join(chunks)


def _encode_prompt_for_child(prompt: str) -> bytes:
    return prompt.replace("\n", "\x0a").encode("utf-8")


def _backspace_current_prompt(prompt: str) -> bytes:
    return b"\x7f" * len(prompt)


def _is_terminal_response(sequence: bytes) -> bool:
    return (
        _is_csi_terminal_response(sequence)
        or _is_osc_terminal_response(sequence)
        or _is_st_terminated_terminal_response(sequence)
        or _is_focus_event(sequence)
        or _is_bracketed_paste_marker(sequence)
    )


def _is_plain_enter(sequence: bytes) -> bool:
    return sequence in {
        b"\x1b[13u",
        b"\x1b[13;0u",
        b"\x1b[13;1u",
        b"\x1b[13~",
        b"\x1b[13;0~",
        b"\x1b[13;1~",
        b"\x1b[27;1;13~",
    }


def _is_shift_enter(sequence: bytes) -> bool:
    return sequence in {
        b"\x1b[13;2u",
        b"\x1b[13;2~",
        b"\x1b[27;2;13~",
        b"\x1b\r",
        b"\x1b\n",
    }


def _is_enhanced_key_release(sequence: bytes) -> bool:
    if not sequence.startswith(b"\x1b[") or not sequence.endswith(b"u"):
        return False
    body = sequence[2:-1]
    return body.endswith(b":3") or b":3;" in body


def _is_csi_terminal_response(sequence: bytes) -> bool:
    if not sequence.startswith(b"\x1b[") or len(sequence) < 4:
        return False
    final = sequence[-1:]
    body = sequence[2:-1]
    if not body:
        return False
    if final == b"R":
        return all(byte in b"0123456789;" for byte in body)
    if final == b"c":
        return all(byte in b"0123456789;?>" for byte in body)
    if final == b"y":
        return all(byte in b"0123456789;?$" for byte in body)
    return False


def _is_focus_event(sequence: bytes) -> bool:
    return sequence in {b"\x1b[I", b"\x1b[O"}


def _is_bracketed_paste_marker(sequence: bytes) -> bool:
    return sequence in {b"\x1b[200~", b"\x1b[201~"}


def _is_bracketed_paste_start(sequence: bytes) -> bool:
    return sequence == b"\x1b[200~"


def _is_bracketed_paste_end(sequence: bytes) -> bool:
    return sequence == b"\x1b[201~"


def _is_st_terminated_terminal_response(sequence: bytes) -> bool:
    return sequence.startswith((b"\x1bP", b"\x1bX", b"\x1b^", b"\x1b_")) and sequence.endswith(
        b"\x1b\\"
    )


def _is_osc_terminal_response(sequence: bytes) -> bool:
    if not sequence.startswith(b"\x1b]"):
        return False
    if sequence.endswith(b"\x07"):
        body = sequence[2:-1]
    elif sequence.endswith(b"\x1b\\"):
        body = sequence[2:-2]
    else:
        return False
    return b";rgb:" in body


def _debug_keys(data: bytes) -> None:
    if os.environ.get("TRADUKENS_DEBUG_KEYS") != "1":
        return
    path = Path.home() / ".local" / "state" / "tradukens" / "keys.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(data.hex(" ") + "\n")
