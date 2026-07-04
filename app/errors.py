from __future__ import annotations


class KnowledgeBaseNotReadyError(RuntimeError):
    """Raised when grounded questions cannot run with the current local state."""


class GeminiQueryError(RuntimeError):
    """Raised when Gemini cannot produce a valid grounded response."""
