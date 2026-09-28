"""Configuration for tracing data calculations."""

from dataclasses import dataclass


# Cost per 1K tokens (configurable, default Claude pricing)
DEFAULT_COST_PER_1K_INPUT = 0.003  # $3 per 1M input tokens
DEFAULT_COST_PER_1K_OUTPUT = 0.015  # $15 per 1M output tokens
DEFAULT_COST_PER_1K_CACHE = 0.0003  # $0.30 per 1M cache read tokens


@dataclass
class TracingConfig:
    """Configuration for tracing data calculations."""

    cost_per_1k_input: float = DEFAULT_COST_PER_1K_INPUT
    cost_per_1k_output: float = DEFAULT_COST_PER_1K_OUTPUT
    cost_per_1k_cache: float = DEFAULT_COST_PER_1K_CACHE
