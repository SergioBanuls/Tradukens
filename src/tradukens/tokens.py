from __future__ import annotations

from dataclasses import dataclass


DEFAULT_ENCODING = "o200k_base"


@dataclass(frozen=True)
class TokenCount:
    tokens: int
    method: str
    encoding: str
    exact: bool


@dataclass(frozen=True)
class TokenSavings:
    original: TokenCount
    translated: TokenCount
    delta: int
    percent: float


class TokenCounterError(RuntimeError):
    pass


def count_tokens(text: str, encoding_name: str = DEFAULT_ENCODING) -> TokenCount:
    try:
        import tiktoken  # type: ignore[import-untyped]
    except ImportError:
        return TokenCount(_estimate_tokens(text), "chars_per_4", encoding_name, False)

    try:
        encoding = tiktoken.get_encoding(encoding_name)
    except Exception as exc:
        raise TokenCounterError(f"Unknown tokenizer encoding: {encoding_name}") from exc

    return TokenCount(len(encoding.encode(text)), "tiktoken", encoding_name, True)


def compare_token_savings(
    original: str,
    translated: str,
    encoding_name: str = DEFAULT_ENCODING,
) -> TokenSavings:
    original_count = count_tokens(original, encoding_name)
    translated_count = count_tokens(translated, encoding_name)
    delta = original_count.tokens - translated_count.tokens
    percent = (delta / original_count.tokens * 100) if original_count.tokens else 0.0
    return TokenSavings(original_count, translated_count, delta, percent)


def _estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4)) if text else 0
