from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable


LATEST_RELEASE_URL = "https://api.github.com/repos/SergioBanuls/Tradukens/releases/latest"
INSTALL_COMMAND = (
    "uv tool install --python 3.12 --force "
    "git+https://github.com/SergioBanuls/Tradukens.git"
)


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    release_url: str


ReleaseFetcher = Callable[[], dict]


def check_for_update(
    current_version: str,
    fetch_release: ReleaseFetcher | None = None,
) -> UpdateInfo | None:
    try:
        release = fetch_release() if fetch_release is not None else _fetch_latest_release()
    except (OSError, TimeoutError, urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None

    latest_version = str(release.get("tag_name") or release.get("name") or "").strip()
    release_url = str(release.get("html_url") or "").strip()
    if not latest_version or not is_newer_version(latest_version, current_version):
        return None

    return UpdateInfo(
        current_version=current_version,
        latest_version=latest_version,
        release_url=release_url,
    )


def format_update_notice(update: UpdateInfo) -> str:
    lines = [
        (
            "[tradukens] Update available: "
            f"{update.current_version} -> {update.latest_version.lstrip('vV')}"
        ),
        f"[tradukens] Update with: {INSTALL_COMMAND}",
    ]
    if update.release_url:
        lines.append(f"[tradukens] Release notes: {update.release_url}")
    return "\n".join(lines)


def is_newer_version(candidate: str, current: str) -> bool:
    return _version_key(candidate) > _version_key(current)


def _fetch_latest_release() -> dict:
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "tradukens-update-check",
        },
    )
    with urllib.request.urlopen(request, timeout=0.75) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _version_key(version: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", version)
    if not numbers:
        return (0,)
    return tuple(int(number) for number in numbers)
