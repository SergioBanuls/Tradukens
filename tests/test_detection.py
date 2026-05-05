from tradukens.detection import CascadingDetector, DetectionResult, HeuristicDetector


class LowConfidencePrimary:
    def detect(self, text: str) -> DetectionResult:
        return DetectionResult("sr", 0.55, "test")


def test_cascading_detector_uses_heuristic_for_low_confidence_fasttext():
    detector = CascadingDetector(  # type: ignore[arg-type]
        LowConfidencePrimary(),
        HeuristicDetector(),
    )

    result = detector.detect("arregla en sin cambiar")

    assert result.language == "es"
    assert result.source == "heuristic_after_low_confidence_fasttext"


def test_cascading_detector_detects_short_spanish_phrase_before_fasttext():
    detector = CascadingDetector(  # type: ignore[arg-type]
        LowConfidencePrimary(),
        HeuristicDetector(),
    )

    result = detector.detect("hola")

    assert result.language == "es"
    assert result.confidence == 0.99
    assert result.source == "short_phrase"


def test_cascading_detector_detects_multiline_short_spanish_phrases_before_fasttext():
    detector = CascadingDetector(  # type: ignore[arg-type]
        LowConfidencePrimary(),
        HeuristicDetector(),
    )

    result = detector.detect("hola\nadios")

    assert result.language == "es"
    assert result.confidence == 0.99
    assert result.source == "short_phrase"
