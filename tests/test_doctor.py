import json

from tradukens.config import Paths
from tradukens.doctor import doctor_report_json, format_doctor_report, run_doctor


def make_paths(tmp_path):
    return Paths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def test_doctor_reports_ready_when_core_checks_pass(tmp_path):
    paths = make_paths(tmp_path)
    paths.ensure_base_dirs()
    paths.config_file.write_text("metrics_enabled = true\n", encoding="utf-8")
    paths.fasttext_model.write_text("model", encoding="utf-8")

    report = run_doctor(
        paths,
        executable_finder=lambda name: f"/bin/{name}",
        module_checker=lambda name: True,
        argos_checker=lambda paths: True,
    )

    assert report.ok is True
    assert "[ok] fastText model" in format_doctor_report(report)


def test_doctor_fails_when_models_are_missing(tmp_path):
    paths = make_paths(tmp_path)

    report = run_doctor(
        paths,
        executable_finder=lambda name: None,
        module_checker=lambda name: True,
        argos_checker=lambda paths: False,
    )

    assert report.ok is False
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["fastText model"] == "fail"
    assert statuses["Argos es->en"] == "fail"
    assert statuses["codex"] == "warn"


def test_doctor_json_payload_contains_checks(tmp_path):
    paths = make_paths(tmp_path)
    report = run_doctor(
        paths,
        executable_finder=lambda name: None,
        module_checker=lambda name: False,
        argos_checker=lambda paths: False,
    )

    payload = json.loads(doctor_report_json(report))

    assert payload["ok"] is False
    assert isinstance(payload["checks"], list)
    assert payload["checks"]
