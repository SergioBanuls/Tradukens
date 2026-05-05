from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from tradukens.translation import PipelineResult


@dataclass(frozen=True)
class MetricEvent:
    timestamp: str
    agent: str
    detected_language: str
    detection_confidence: float
    detection_source: str
    action: str
    original_chars: int
    output_chars: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    elapsed_ms: int


class MetricsRecorder:
    def __init__(self, path: Path, enabled: bool = True):
        self.path = path
        self.enabled = enabled

    def record(self, agent: str, result: PipelineResult) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = MetricEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent=agent,
            detected_language=result.detection.language,
            detection_confidence=round(result.detection.confidence, 4),
            detection_source=result.detection.source,
            action=result.action,
            original_chars=result.original_chars,
            output_chars=result.output_chars,
            estimated_input_tokens=_estimate_tokens(result.original_chars),
            estimated_output_tokens=_estimate_tokens(result.output_chars),
            elapsed_ms=result.elapsed_ms,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")


def _estimate_tokens(chars: int) -> int:
    return max(1, round(chars / 4)) if chars else 0
