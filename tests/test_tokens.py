import pytest

from tradukens.tokens import TokenCounterError, compare_token_savings, count_tokens


def test_count_tokens_uses_tiktoken_encoding():
    result = count_tokens("hello")

    assert result.tokens > 0
    assert result.method == "tiktoken"
    assert result.encoding == "o200k_base"
    assert result.exact is True


def test_compare_token_savings_returns_delta_and_percent():
    savings = compare_token_savings("arregla este bug sin cambiar la API pública", "fix this bug")

    assert savings.original.tokens > savings.translated.tokens
    assert savings.delta == savings.original.tokens - savings.translated.tokens
    assert savings.percent > 0


def test_count_tokens_rejects_unknown_encoding():
    with pytest.raises(TokenCounterError):
        count_tokens("hello", "not-a-real-encoding")
