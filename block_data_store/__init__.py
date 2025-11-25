"""Top-level package for the block data store prototype."""

__version__ = "0.1.0"

from .startup import ensure_workspace  # noqa: E402

__all__ = ["__version__", "ensure_workspace"]
