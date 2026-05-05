from __future__ import annotations

from tradukens.config import Settings
from tradukens.detection import DetectionResult
from tradukens.translation import TranslationPipeline


class StaticDetector:
    def __init__(self, result: DetectionResult):
        self.result = result

    def detect(self, text: str) -> DetectionResult:
        return self.result


class ReplacingTranslator:
    def translate(self, text: str) -> str:
        return (
            text.replace("arregla", "fix")
            .replace("este bug", "this bug")
            .replace("sin cambiar", "without changing")
            .replace("la API pública", "the public API")
        )


def build_pipeline(result: DetectionResult) -> TranslationPipeline:
    return TranslationPipeline(
        Settings(min_confidence=0.75),
        StaticDetector(result),  # type: ignore[arg-type]
        ReplacingTranslator(),  # type: ignore[arg-type]
    )


def test_translates_high_confidence_spanish():
    pipeline = build_pipeline(DetectionResult("es", 0.93, "test"))

    result = pipeline.process("arregla este bug sin cambiar la API pública")

    assert result.action == "translated"
    assert result.output == "fix this bug without changing the public API"


def test_translates_short_spanish_phrase_with_lexicon():
    pipeline = build_pipeline(DetectionResult("es", 0.99, "short_phrase"))

    result = pipeline.process("hola")

    assert result.action == "translated_lexicon"
    assert result.output == "hello"


def test_translates_multiline_short_spanish_phrases_with_lexicon():
    pipeline = build_pipeline(DetectionResult("es", 0.99, "short_phrase"))

    result = pipeline.process("hola\nadios")

    assert result.action == "translated_lexicon"
    assert result.output == "hello\ngoodbye"


def test_preserves_inline_code_during_translation():
    pipeline = build_pipeline(DetectionResult("es", 0.93, "test"))

    result = pipeline.process("arregla este bug en `load_user()` sin cambiar la API pública")

    assert result.action == "translated"
    assert "`load_user()`" in result.output


def test_keeps_english_unchanged():
    pipeline = build_pipeline(DetectionResult("en", 0.98, "test"))

    result = pipeline.process("fix this bug without changing the public API")

    assert result.action == "unchanged_english"
    assert result.output == "fix this bug without changing the public API"


def test_moderate_confidence_spanish_is_translated():
    pipeline = build_pipeline(DetectionResult("es", 0.40, "test"))

    result = pipeline.process("arregla este bug")

    assert result.action == "translated"
    assert result.output == "fix this bug"


def test_very_low_confidence_sends_original_with_warning():
    pipeline = build_pipeline(DetectionResult("es", 0.20, "test"))

    result = pipeline.process("arregla este bug")

    assert result.action == "low_confidence"
    assert result.output == "arregla este bug"
    assert result.warning is not None


def test_slash_command_is_not_translated():
    pipeline = build_pipeline(DetectionResult("es", 0.99, "test"))

    result = pipeline.process("/clear")

    assert result.action == "skipped_command"
    assert result.output == "/clear"
