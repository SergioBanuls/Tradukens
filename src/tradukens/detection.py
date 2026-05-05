from __future__ import annotations

import re
import contextlib
import io
from dataclasses import dataclass
from pathlib import Path

from tradukens.lexicon import is_english_short_phrase, is_spanish_short_phrase


FASTTEXT_LID_URL = (
    "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
)


@dataclass(frozen=True)
class DetectionResult:
    language: str
    confidence: float
    source: str


class DetectorUnavailable(RuntimeError):
    pass


class FastTextDetector:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._model = None

    def available(self) -> bool:
        return self.model_path.exists()

    def detect(self, text: str) -> DetectionResult:
        if not text.strip():
            return DetectionResult("unknown", 0.0, "fasttext")
        if not self.model_path.exists():
            raise DetectorUnavailable(f"Missing fastText model: {self.model_path}")

        if self._model is None:
            try:
                import fasttext  # type: ignore[import-untyped]
            except ImportError as exc:
                raise DetectorUnavailable("fasttext-wheel is not installed") from exc
            with contextlib.redirect_stderr(io.StringIO()):
                self._model = fasttext.load_model(str(self.model_path))

        labels, probabilities = self._model.predict(_normalize_for_fasttext(text), k=1)
        if not labels:
            return DetectionResult("unknown", 0.0, "fasttext")

        language = labels[0].replace("__label__", "")
        return DetectionResult(language, float(probabilities[0]), "fasttext")


class HeuristicDetector:
    SPANISH_HINTS = {
        "quiero",
        "hola",
        "adios",
        "buenos",
        "buenas",
        "gracias",
        "favor",
        "puedes",
        "haz",
        "hacer",
        "arregla",
        "corrige",
        "cambia",
        "cambiar",
        "añade",
        "agrega",
        "borra",
        "elimina",
        "sin",
        "con",
        "para",
        "porque",
        "cuando",
        "donde",
        "este",
        "esta",
        "esto",
        "funcione",
        "usuario",
        "promt",
        "prompt",
    }
    ENGLISH_HINTS = {
        "fix",
        "change",
        "add",
        "remove",
        "without",
        "with",
        "for",
        "because",
        "when",
        "where",
        "this",
        "user",
        "prompt",
        "make",
        "implement",
    }

    def detect(self, text: str) -> DetectionResult:
        normalized = text.lower()
        words = set(re.findall(r"[a-záéíóúüñ]+", normalized))
        spanish_score = len(words & self.SPANISH_HINTS)
        english_score = len(words & self.ENGLISH_HINTS)

        if re.search(r"[áéíóúüñ¿¡]", normalized):
            spanish_score += 2

        if spanish_score == 0 and english_score == 0:
            return DetectionResult("unknown", 0.0, "heuristic")

        if spanish_score > english_score:
            confidence = min(0.95, 0.55 + spanish_score * 0.12)
            return DetectionResult("es", confidence, "heuristic")

        confidence = min(0.95, 0.55 + english_score * 0.12)
        return DetectionResult("en", confidence, "heuristic")


class CascadingDetector:
    def __init__(
        self,
        primary: FastTextDetector,
        fallback: HeuristicDetector | None = None,
        fallback_below_confidence: float = 0.70,
    ):
        self.primary = primary
        self.fallback = fallback or HeuristicDetector()
        self.fallback_below_confidence = fallback_below_confidence

    def detect(self, text: str) -> DetectionResult:
        if is_spanish_short_phrase(text):
            return DetectionResult("es", 0.99, "short_phrase")
        if is_english_short_phrase(text):
            return DetectionResult("en", 0.99, "short_phrase")

        try:
            primary_result = self.primary.detect(text)
        except DetectorUnavailable:
            return self.fallback.detect(text)

        if primary_result.confidence >= self.fallback_below_confidence:
            return primary_result

        fallback_result = self.fallback.detect(text)
        if (
            fallback_result.language != "unknown"
            and fallback_result.confidence > primary_result.confidence
        ):
            return DetectionResult(
                fallback_result.language,
                fallback_result.confidence,
                "heuristic_after_low_confidence_fasttext",
            )

        return primary_result


def _normalize_for_fasttext(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())
