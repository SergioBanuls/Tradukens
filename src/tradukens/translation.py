from __future__ import annotations

import os
import contextlib
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from tradukens.config import Paths, Settings
from tradukens.detection import CascadingDetector, DetectionResult
from tradukens.lexicon import spanish_short_translation
from tradukens.protection import natural_language_view, protect_code_like_spans


SOURCE_TRANSLATION_MIN_CONFIDENCE = 0.35


@dataclass(frozen=True)
class PipelineResult:
    original_chars: int
    output: str
    detection: DetectionResult
    action: str
    elapsed_ms: int
    warning: str | None = None
    error: str | None = None

    @property
    def sendable(self) -> bool:
        return self.error is None

    @property
    def output_chars(self) -> int:
        return len(self.output)


class TranslatorUnavailable(RuntimeError):
    pass


class ArgosTranslator:
    def __init__(self, packages_dir: Path, source_lang: str = "es", target_lang: str = "en"):
        self.packages_dir = packages_dir
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._translation = None

    def available(self) -> bool:
        try:
            return self._find_translation() is not None
        except TranslatorUnavailable:
            return False

    def translate(self, text: str) -> str:
        translation = self._find_translation()
        if translation is None:
            raise TranslatorUnavailable(
                f"Missing Argos package {self.source_lang}->{self.target_lang}. "
                "Run `tradukens setup --lang es`."
            )
        with _silence_third_party_output():
            return str(translation.translate(text))

    def _find_translation(self):
        if self._translation is not None:
            return self._translation

        self._configure_argos_env()
        try:
            from argostranslate import translate  # type: ignore[import-untyped]
        except ImportError as exc:
            raise TranslatorUnavailable("argostranslate is not installed") from exc

        with _silence_third_party_output():
            installed_languages = translate.get_installed_languages()
        from_language = next(
            (language for language in installed_languages if language.code == self.source_lang),
            None,
        )
        to_language = next(
            (language for language in installed_languages if language.code == self.target_lang),
            None,
        )
        if from_language is None or to_language is None:
            return None

        with _silence_third_party_output():
            self._translation = from_language.get_translation(to_language)
        return self._translation

    def _configure_argos_env(self) -> None:
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        os.environ["ARGOS_PACKAGE_DIR"] = str(self.packages_dir)
        os.environ["ARGOS_PACKAGES_DIR"] = str(self.packages_dir)
        os.environ["ARGOS_TRANSLATE_PACKAGES_DIR"] = str(self.packages_dir)
        os.environ.setdefault("ARGOS_DEVICE_TYPE", "cpu")
        os.environ.setdefault("ARGOS_COMPUTE_TYPE", "int8")
        logging.getLogger("stanza").setLevel(logging.ERROR)
        logging.getLogger("argostranslate").setLevel(logging.ERROR)


@contextlib.contextmanager
def _silence_third_party_output():
    previous_disable_level = logging.root.manager.disable
    logging.disable(logging.WARNING)
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            yield
    finally:
        logging.disable(previous_disable_level)


class TranslationPipeline:
    def __init__(
        self,
        settings: Settings,
        detector: CascadingDetector,
        translator: ArgosTranslator,
    ):
        self.settings = settings
        self.detector = detector
        self.translator = translator

    def process(self, text: str) -> PipelineResult:
        started = perf_counter()
        stripped = text.strip()
        if not stripped:
            return self._result(started, text, text, DetectionResult("unknown", 0.0, "none"), "empty")

        if stripped.startswith(("/", ":")):
            return self._result(
                started,
                text,
                text,
                DetectionResult("command", 1.0, "prefix"),
                "skipped_command",
            )

        detection_input = natural_language_view(text) or text
        detection = self.detector.detect(detection_input)
        if (
            detection.language == self.settings.target_lang
            and detection.confidence >= self.settings.min_confidence
        ):
            return self._result(started, text, text, detection, "unchanged_english")

        if detection.language != self.settings.source_lang:
            return self._result(
                started,
                text,
                text,
                detection,
                "unchanged_unknown_language",
                warning=f"Language detection was {detection.language} ({detection.confidence:.2f}); sent original.",
            )

        lexicon_translation = spanish_short_translation(text)
        if lexicon_translation is not None:
            return self._result(
                started,
                text,
                lexicon_translation,
                detection,
                "translated_lexicon",
            )

        if detection.confidence < SOURCE_TRANSLATION_MIN_CONFIDENCE:
            return self._result(
                started,
                text,
                text,
                detection,
                "low_confidence",
                warning=f"Low Spanish confidence ({detection.confidence:.2f}); sent original.",
            )

        protected = protect_code_like_spans(text)
        try:
            translated = self.translator.translate(protected.text)
        except TranslatorUnavailable as exc:
            return self._result(
                started,
                text,
                text,
                detection,
                "translation_error",
                error=str(exc),
            )

        output = protected.restore(translated)
        return self._result(started, text, output, detection, "translated")

    def _result(
        self,
        started: float,
        original: str,
        output: str,
        detection: DetectionResult,
        action: str,
        warning: str | None = None,
        error: str | None = None,
    ) -> PipelineResult:
        return PipelineResult(
            original_chars=len(original),
            output=output,
            detection=detection,
            action=action,
            elapsed_ms=int((perf_counter() - started) * 1000),
            warning=warning,
            error=error,
        )


def build_pipeline(paths: Paths, settings: Settings) -> TranslationPipeline:
    from tradukens.detection import FastTextDetector, HeuristicDetector

    detector = CascadingDetector(FastTextDetector(paths.fasttext_model), HeuristicDetector())
    translator = ArgosTranslator(
        paths.argos_packages_dir,
        source_lang=settings.source_lang,
        target_lang=settings.target_lang,
    )
    return TranslationPipeline(settings, detector, translator)
