import json

from tradukens.config import Settings
from tradukens.detection import DetectionResult
from tradukens.metrics import MetricsRecorder
from tradukens.translation import TranslationPipeline


class StaticDetector:
    def detect(self, text: str) -> DetectionResult:
        return DetectionResult("es", 0.99, "test")


class StaticTranslator:
    def translate(self, text: str) -> str:
        return "fix the bug"


def test_metrics_do_not_store_prompt_text(tmp_path):
    pipeline = TranslationPipeline(
        Settings(),
        StaticDetector(),  # type: ignore[arg-type]
        StaticTranslator(),  # type: ignore[arg-type]
    )
    result = pipeline.process("arregla el bug secreto")
    metrics_path = tmp_path / "metrics.jsonl"

    MetricsRecorder(metrics_path).record("codex", result)

    raw = metrics_path.read_text(encoding="utf-8")
    event = json.loads(raw)
    assert "arregla" not in raw
    assert "secreto" not in raw
    assert event["agent"] == "codex"
    assert event["action"] == "translated"
    assert event["original_chars"] > 0
