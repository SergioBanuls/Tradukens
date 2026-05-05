from __future__ import annotations

import re
import unicodedata


SPANISH_SHORT_TRANSLATIONS = {
    "hola": "hello",
    "adios": "goodbye",
    "buenos dias": "good morning",
    "buenas tardes": "good afternoon",
    "buenas noches": "good evening",
    "gracias": "thank you",
    "muchas gracias": "thank you very much",
    "si": "yes",
    "vale": "ok",
    "de acuerdo": "ok",
    "perfecto": "perfect",
    "por favor": "please",
}

ENGLISH_SHORT_PHRASES = {
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank you",
    "yes",
    "no",
    "ok",
    "okay",
    "perfect",
}


def normalize_phrase(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    without_marks = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    without_punctuation = re.sub(r"[^\w\s]", " ", without_marks)
    return " ".join(without_punctuation.split())


def spanish_short_translation(text: str) -> str | None:
    direct = SPANISH_SHORT_TRANSLATIONS.get(normalize_phrase(text))
    if direct is not None:
        return direct

    if "\n" not in text:
        return None

    translated_lines: list[str] = []
    found_translatable_line = False
    for line in text.split("\n"):
        if not line.strip():
            translated_lines.append(line)
            continue
        translated = SPANISH_SHORT_TRANSLATIONS.get(normalize_phrase(line))
        if translated is None:
            return None
        translated_lines.append(translated)
        found_translatable_line = True

    if not found_translatable_line:
        return None
    return "\n".join(translated_lines)


def is_spanish_short_phrase(text: str) -> bool:
    return spanish_short_translation(text) is not None


def is_english_short_phrase(text: str) -> bool:
    return normalize_phrase(text) in ENGLISH_SHORT_PHRASES
