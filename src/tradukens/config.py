from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "tradukens"


@dataclass(frozen=True)
class Paths:
    config_dir: Path
    data_dir: Path
    state_dir: Path
    cache_dir: Path

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.toml"

    @property
    def model_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def fasttext_model(self) -> Path:
        return self.model_dir / "fasttext" / "lid.176.ftz"

    @property
    def argos_packages_dir(self) -> Path:
        return self.model_dir / "argos" / "packages"

    @property
    def downloads_dir(self) -> Path:
        return self.cache_dir / "downloads"

    @property
    def metrics_file(self) -> Path:
        return self.state_dir / "metrics.jsonl"

    def ensure_base_dirs(self) -> None:
        for path in (
            self.config_dir,
            self.data_dir,
            self.state_dir,
            self.cache_dir,
            self.fasttext_model.parent,
            self.argos_packages_dir,
            self.downloads_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Settings:
    source_lang: str = "es"
    target_lang: str = "en"
    min_confidence: float = 0.75
    low_confidence_action: str = "warn_send_original"
    metrics_enabled: bool = True


def default_paths() -> Paths:
    home = Path.home()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    state_home = Path(os.environ.get("XDG_STATE_HOME", home / ".local" / "state"))
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))
    return Paths(
        config_dir=config_home / APP_NAME,
        data_dir=data_home / APP_NAME,
        state_dir=state_home / APP_NAME,
        cache_dir=cache_home / APP_NAME,
    )


def load_settings(paths: Paths | None = None) -> Settings:
    paths = paths or default_paths()
    if not paths.config_file.exists():
        return Settings()

    with paths.config_file.open("rb") as handle:
        data = tomllib.load(handle)

    return Settings(
        source_lang=str(data.get("source_lang", Settings.source_lang)),
        target_lang=str(data.get("target_lang", Settings.target_lang)),
        min_confidence=float(data.get("min_confidence", Settings.min_confidence)),
        low_confidence_action=str(
            data.get("low_confidence_action", Settings.low_confidence_action)
        ),
        metrics_enabled=bool(data.get("metrics_enabled", Settings.metrics_enabled)),
    )


def write_default_config(paths: Paths | None = None) -> Path:
    paths = paths or default_paths()
    paths.ensure_base_dirs()
    if paths.config_file.exists():
        return paths.config_file

    content = "\n".join(
        [
            'source_lang = "es"',
            'target_lang = "en"',
            "min_confidence = 0.75",
            'low_confidence_action = "warn_send_original"',
            "metrics_enabled = true",
            "",
        ]
    )
    paths.config_file.write_text(content, encoding="utf-8")
    return paths.config_file
