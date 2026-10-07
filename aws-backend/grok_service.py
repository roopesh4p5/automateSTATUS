"""Backward compatibility alias for groq_service."""

from groq_service import (
    DEFAULT_GROQ_BASE_URL,
    DEFAULT_GROQ_MODEL,
    generate_rule_based_analysis,
    parse_groq_response,
    parse_grok_response,
    summarize_with_groq,
    summarize_with_grok,
)

__all__ = [
    "DEFAULT_GROQ_BASE_URL",
    "DEFAULT_GROQ_MODEL",
    "generate_rule_based_analysis",
    "parse_groq_response",
    "parse_grok_response",
    "summarize_with_groq",
    "summarize_with_grok",
]
