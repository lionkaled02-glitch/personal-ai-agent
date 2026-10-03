"""Model provider layer: vendor-neutral interface plus adapters.

Only the mock provider exists in Phase 0. Real adapters (OpenAI, Anthropic,
local models) are planned for Phase 1 and must implement
:class:`ModelProvider` without changing any other module.
"""

from .base import (
    Capability,
    ChatMessage,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)
from .mock import MockModelProvider

__all__ = [
    "Capability",
    "ChatMessage",
    "MockModelProvider",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
]
