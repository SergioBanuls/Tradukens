from tradukens.lexicon import (
    is_english_short_phrase,
    is_spanish_short_phrase,
    normalize_phrase,
    spanish_short_translation,
)


def test_normalize_phrase_removes_accents_and_punctuation():
    assert normalize_phrase("¡Sí!") == "si"


def test_spanish_short_translation():
    assert spanish_short_translation("hola") == "hello"
    assert spanish_short_translation("¡Gracias!") == "thank you"


def test_short_phrase_detection_helpers():
    assert is_spanish_short_phrase("buenos días")
    assert is_english_short_phrase("hello")
