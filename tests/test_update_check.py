from urllib.error import URLError

from tradukens.update_check import (
    INSTALL_COMMAND,
    check_for_update,
    format_update_notice,
    is_newer_version,
)


def test_version_comparison_handles_v_prefix_and_multi_digit_versions():
    assert is_newer_version("v0.1.10", "0.1.9") is True
    assert is_newer_version("v0.1.1", "0.1.1") is False
    assert is_newer_version("0.1.0", "0.1.1") is False


def test_check_for_update_returns_update_when_latest_is_newer():
    update = check_for_update(
        "0.1.0",
        lambda: {
            "tag_name": "v0.1.1",
            "html_url": "https://github.com/SergioBanuls/Tradukens/releases/tag/v0.1.1",
        },
    )

    assert update is not None
    assert update.current_version == "0.1.0"
    assert update.latest_version == "v0.1.1"


def test_check_for_update_returns_none_when_current_is_latest():
    update = check_for_update("0.1.1", lambda: {"tag_name": "v0.1.1"})

    assert update is None


def test_check_for_update_silently_ignores_network_errors():
    update = check_for_update("0.1.0", lambda: (_ for _ in ()).throw(URLError("offline")))

    assert update is None


def test_format_update_notice_includes_install_command():
    update = check_for_update(
        "0.1.0",
        lambda: {
            "tag_name": "v0.1.1",
            "html_url": "https://github.com/SergioBanuls/Tradukens/releases/tag/v0.1.1",
        },
    )

    notice = format_update_notice(update)

    assert "0.1.0 -> 0.1.1" in notice
    assert INSTALL_COMMAND in notice
    assert "Release notes:" in notice
