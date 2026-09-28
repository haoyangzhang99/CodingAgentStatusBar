"""
Data validators for analytics indexing.

Provides validation functions to ensure data quality and detect anomalies.
DQ-001: Token validation for reasonable ranges.
"""

from typing import Optional, Tuple
from ...utils.logger import info


# Token validation thresholds
TOKEN_MAX_INPUT = 100_000  # 100K tokens is very large for input
TOKEN_MAX_OUTPUT = 50_000  # 50K tokens is very large for output
TOKEN_MAX_REASONING = 100_000  # Extended thinking can be large


def validate_token_counts(
    tokens_input: Optional[int],
    tokens_output: Optional[int],
    tokens_reasoning: Optional[int] = None,
    context: str = "",
) -> Tuple[int, int, int]:
    """Validate and sanitize token counts.

    Ensures tokens are:
    - Non-negative (converts None to 0)
    - Within reasonable ranges (logs warnings for suspicious values)

    Args:
        tokens_input: Input token count
        tokens_output: Output token count
        tokens_reasoning: Reasoning token count (optional)
        context: Context for logging (e.g., "message msg_123")

    Returns:
        Tuple of (validated_input, validated_output, validated_reasoning)
    """
    # Convert None to 0 and ensure non-negative
    input_tokens = max(0, tokens_input or 0)
    output_tokens = max(0, tokens_output or 0)
    reasoning_tokens = max(0, tokens_reasoning or 0)

    # Check for suspicious values
    if input_tokens > TOKEN_MAX_INPUT:
        info(
            f"[TokenValidator] Suspicious input tokens: {input_tokens} "
            f"(>{TOKEN_MAX_INPUT:,}) {context}"
        )

    if output_tokens > TOKEN_MAX_OUTPUT:
        info(
            f"[TokenValidator] Suspicious output tokens: {output_tokens} "
            f"(>{TOKEN_MAX_OUTPUT:,}) {context}"
        )

    if reasoning_tokens > TOKEN_MAX_REASONING:
        info(
            f"[TokenValidator] Suspicious reasoning tokens: {reasoning_tokens} "
            f"(>{TOKEN_MAX_REASONING:,}) {context}"
        )

    return input_tokens, output_tokens, reasoning_tokens


def get_token_summary(
    tokens_input: int, tokens_output: int, tokens_reasoning: int = 0
) -> str:
    """Get human-readable token summary.

    Args:
        tokens_input: Input tokens
        tokens_output: Output tokens
        tokens_reasoning: Reasoning tokens

    Returns:
        Summary string like "in: 1.2K, out: 3.4K, reasoning: 500"
    """
    total = tokens_input + tokens_output + tokens_reasoning

    def format_tokens(count: int) -> str:
        if count >= 1000:
            return f"{count / 1000:.1f}K"
        return str(count)

    parts = [
        f"in: {format_tokens(tokens_input)}",
        f"out: {format_tokens(tokens_output)}",
    ]

    if tokens_reasoning > 0:
        parts.append(f"reasoning: {format_tokens(tokens_reasoning)}")

    parts.append(f"total: {format_tokens(total)}")

    return ", ".join(parts)
