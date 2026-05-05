from tradukens.protection import natural_language_view, protect_code_like_spans


def test_protects_and_restores_code_like_spans():
    original = (
        "arregla `foo_bar()` en ./src/app.py y revisa "
        "https://example.com/docs usando --dry-run"
    )

    protected = protect_code_like_spans(original)

    assert "`foo_bar()`" not in protected.text
    assert "./src/app.py" not in protected.text
    assert "https://example.com/docs" not in protected.text
    assert "--dry-run" not in protected.text
    assert protected.restore(protected.text) == original


def test_protects_fenced_blocks():
    original = "explica esto:\n```python\nprint('hola')\n```\nfin"

    protected = protect_code_like_spans(original)

    assert "print('hola')" not in protected.text
    assert protected.restore(protected.text) == original


def test_natural_language_view_removes_code_like_spans():
    original = "arregla `load_user()` en ./src/app.py sin cambiar --dry-run"

    visible = natural_language_view(original)

    assert "`load_user()`" not in visible
    assert "./src/app.py" not in visible
    assert "--dry-run" not in visible
    assert "arregla" in visible


def test_restore_tolerates_argos_spaces_inside_placeholder():
    protected = protect_code_like_spans("arregla `load_user()`")

    restored = protected.restore("fix ZXQTOKEN 0000ZXQ")

    assert restored == "fix `load_user()`"
