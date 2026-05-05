from __future__ import annotations

import re
from dataclasses import dataclass


PLACEHOLDER_TEMPLATE = "ZXQTOKEN{index:04d}ZXQ"


@dataclass(frozen=True)
class ProtectedText:
    text: str
    replacements: dict[str, str]

    def restore(self, translated: str) -> str:
        restored = translated
        for placeholder, original in self.replacements.items():
            restored = restored.replace(placeholder, original)
            restored = _restore_spaced_placeholder(restored, placeholder, original)
        return restored


PATTERNS = [
    re.compile(r"```.*?```", re.DOTALL),
    re.compile(r"~~~.*?~~~", re.DOTALL),
    re.compile(r"`[^`\n]+`"),
    re.compile(r"https?://[^\s`]+"),
    re.compile(r"(?<!\w)(?:\.{1,2}/|/|~/)[^\s`]+"),
    re.compile(r"(?<!\w)--[A-Za-z0-9][\w-]*(?:=[^\s`]+)?"),
    re.compile(r"(?<!\w)-[A-Za-z](?!\w)"),
]


def protect_code_like_spans(text: str) -> ProtectedText:
    replacements: dict[str, str] = {}
    protected = text

    for pattern in PATTERNS:
        protected = pattern.sub(lambda match: _replace(match.group(0), replacements), protected)

    return ProtectedText(protected, replacements)


def natural_language_view(text: str) -> str:
    visible = text
    for pattern in PATTERNS:
        visible = pattern.sub(" ", visible)
    return " ".join(visible.split())


def _replace(value: str, replacements: dict[str, str]) -> str:
    placeholder = PLACEHOLDER_TEMPLATE.format(index=len(replacements))
    replacements[placeholder] = value
    return placeholder


def _restore_spaced_placeholder(text: str, placeholder: str, original: str) -> str:
    match = re.fullmatch(r"ZXQTOKEN(\d{4})ZXQ", placeholder)
    if match is None:
        return text
    pattern = re.compile(rf"ZXQTOKEN\s*{match.group(1)}\s*ZXQ")
    return pattern.sub(original, text)
