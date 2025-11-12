"""Renderer entry-point wiring Markdown components."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from block_data_store.models.block import Block, BlockType
from block_data_store.renderers.base import RenderOptions, Renderer, RendererComponent

from .components import DEFAULT_COMPONENTS, GenericComponent


def _default_components() -> dict[BlockType, RendererComponent]:
    return dict(DEFAULT_COMPONENTS)


@dataclass(slots=True)
class MarkdownRenderer(Renderer):
    _components: dict[BlockType, RendererComponent] = field(default_factory=dict)
    _fallback_component: RendererComponent | None = None

    def __post_init__(self) -> None:
        if not self._components:
            self._components = _default_components()
        if self._fallback_component is None:
            self._fallback_component = GenericComponent()

    def register(self, block_type: BlockType, component: RendererComponent) -> None:
        self._components[block_type] = component

    def render(
        self,
        block: Block,
        *,
        options: RenderOptions | None = None,
        **kwargs: Any,
    ) -> str:
        opts = options or RenderOptions()
        extra = dict(kwargs)
        return self._render_block(block, opts, extra).strip()

    # Internal helpers -------------------------------------------------
    def _render_block(
        self,
        block: Block,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        component = self._components.get(block.type, self._fallback_component)
        assert component is not None, "Fallback component must be configured"
        rendered = component.render(block, engine=self, options=options, extra=extra)

        if options.include_metadata and block.metadata:
            metadata_lines = "\n".join(f"> {k}: {v}" for k, v in sorted(block.metadata.items()))
            rendered = _join_sections([rendered, metadata_lines])

        return rendered


def _join_sections(sections: Sequence[str]) -> str:
    cleaned = [section.strip() for section in sections if section and section.strip()]
    if not cleaned:
        return ""

    output = cleaned[0]
    for section in cleaned[1:]:
        separator = "\n\n"
        prev_kind = _section_kind(output.splitlines()[-1])
        next_kind = _section_kind(section.splitlines()[0])
        if prev_kind and prev_kind == next_kind and prev_kind in {"bullet", "numbered"}:
            separator = "\n"
        output = f"{output}{separator}{section}"
    return output


def _section_kind(line: str) -> str | None:
    stripped = line.lstrip()
    if not stripped:
        return None
    if stripped[0] in "-*+" and (len(stripped) == 1 or stripped[1].isspace()):
        return "bullet"
    number_prefix = stripped.split(" ", 1)[0]
    if number_prefix.endswith(".") and number_prefix[:-1].isdigit():
        return "numbered"
    return None


__all__ = ["MarkdownRenderer"]
