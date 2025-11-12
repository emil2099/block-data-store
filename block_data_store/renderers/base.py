"""Renderer interfaces and shared helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from block_data_store.models.block import Block


@dataclass(slots=True)
class RenderOptions:
    recursive: bool = True
    include_metadata: bool = False


class Renderer(Protocol):
    def render(
        self,
        block: Block,
        *,
        options: RenderOptions | None = None,
        **kwargs: Any,
    ) -> str:
        ...


class RendererComponent(Protocol):
    def render(
        self,
        block: Block,
        *,
        engine: Renderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        ...
