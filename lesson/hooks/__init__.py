"""Hook helpers shared across platform adapters."""

from .adapter import NormalizedEvent, handle_post_tool_use

__all__ = ["NormalizedEvent", "handle_post_tool_use"]
