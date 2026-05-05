from __future__ import annotations

import os
import shutil
import urllib.request
from pathlib import Path

from tradukens.config import Paths, write_default_config
from tradukens.detection import FASTTEXT_LID_URL


class SetupError(RuntimeError):
    pass


def setup_spanish(paths: Paths) -> list[str]:
    paths.ensure_base_dirs()
    config_path = write_default_config(paths)

    messages = [f"Config: {config_path}"]
    messages.append(_ensure_fasttext_model(paths.fasttext_model, paths.downloads_dir))
    messages.append(_ensure_argos_package(paths.argos_packages_dir, "es", "en"))
    return messages


def _ensure_fasttext_model(model_path: Path, downloads_dir: Path) -> str:
    if model_path.exists():
        return f"fastText model already installed: {model_path}"

    downloads_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = downloads_dir / f"{model_path.name}.tmp"
    urllib.request.urlretrieve(FASTTEXT_LID_URL, tmp_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp_path), str(model_path))
    return f"Installed fastText model: {model_path}"


def _ensure_argos_package(packages_dir: Path, source_lang: str, target_lang: str) -> str:
    _configure_argos_env(packages_dir)
    try:
        from argostranslate import package, translate  # type: ignore[import-untyped]
    except ImportError as exc:
        raise SetupError("argostranslate is not installed") from exc

    installed_languages = translate.get_installed_languages()
    from_language = next(
        (language for language in installed_languages if language.code == source_lang),
        None,
    )
    to_language = next(
        (language for language in installed_languages if language.code == target_lang),
        None,
    )
    if from_language is not None and to_language is not None:
        try:
            from_language.get_translation(to_language)
            return f"Argos package already installed: {source_lang}->{target_lang}"
        except Exception:
            pass

    package.update_package_index()
    available = package.get_available_packages()
    selected = next(
        (
            candidate
            for candidate in available
            if candidate.from_code == source_lang and candidate.to_code == target_lang
        ),
        None,
    )
    if selected is None:
        raise SetupError(f"No Argos package found for {source_lang}->{target_lang}")

    downloaded_path = selected.download()
    package.install_from_path(downloaded_path)
    return f"Installed Argos package: {source_lang}->{target_lang}"


def _configure_argos_env(packages_dir: Path) -> None:
    packages_dir.mkdir(parents=True, exist_ok=True)
    os.environ["ARGOS_PACKAGE_DIR"] = str(packages_dir)
    os.environ["ARGOS_PACKAGES_DIR"] = str(packages_dir)
    os.environ["ARGOS_TRANSLATE_PACKAGES_DIR"] = str(packages_dir)
    os.environ.setdefault("ARGOS_DEVICE_TYPE", "cpu")
    os.environ.setdefault("ARGOS_COMPUTE_TYPE", "int8")
