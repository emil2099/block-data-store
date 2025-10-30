"""Markdown renderer built with component classes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from uuid import UUID

from block_data_store.models.block import Block, BlockType, Content
from block_data_store.renderers.base import RenderOptions, Renderer, RendererComponent

ResolveReference = Callable[[UUID], Block | None]


@dataclass(slots=True)
class MarkdownRenderer(Renderer):
    resolve_reference: ResolveReference | None = None
    _components: dict[BlockType, RendererComponent] = field(default_factory=dict)
    _fallback_component: RendererComponent | None = None

    def __post_init__(self) -> None:
        if not self._components:
            self._components = {
                BlockType.DOCUMENT: DocumentComponent(),
                BlockType.HEADING: HeadingComponent(),
                BlockType.PARAGRAPH: ParagraphComponent(),
                BlockType.BULLETED_LIST_ITEM: BulletedListItemComponent(),
                BlockType.NUMBERED_LIST_ITEM: NumberedListItemComponent(),
                BlockType.DATASET: DatasetComponent(),
                BlockType.RECORD: RecordComponent(),
                BlockType.PAGE_GROUP: PageGroupComponent(),
                BlockType.SYNCED: SyncedComponent(),
                BlockType.PAGE: PageComponent(),
            }
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


# ---------------------------------------------------------------------------
# Components


class DocumentComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        title = getattr(block.properties, "title", None)
        heading = f"# {title}" if title else f"# Document {block.id}"
        body = block.content.text if block.content and block.content.text else ""
        sections = [heading]
        if body:
            sections.append(body)
        sections.extend(_render_children(engine, block, options, extra))
        return _join_sections(sections)


class HeadingComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        props = block.properties
        level = getattr(props, "level", 2) if props is not None else 2
        level = max(1, min(level, 6))
        text = block.content.text if block.content and block.content.text else f"Heading {block.id}"
        prefix = "#" * level
        sections = [f"{prefix} {text}"]
        sections.extend(_render_children(engine, block, options, extra))
        return _join_sections(sections)


class ParagraphComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        text = block.content.text if block.content and block.content.text else ""
        sections = [text] if text else []
        sections.extend(_render_children(engine, block, options, extra))
        return _join_sections(sections)


class DatasetComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        dataset_type = getattr(block.properties, "dataset_type", None) or "default"
        if block.content and block.content.text:
            formatted = block.content.text
        else:
            records = [
                record.content.data
                for record in block.children()
                if record.type is BlockType.RECORD and record.content and record.content.data
            ]
            payload = {"records": records} if records else {}
            formatted = json.dumps(payload, indent=2) if payload else ""
        dataset_section = "\n".join([
            f"```dataset:{dataset_type}",
            formatted,
            "```",
        ])
        sections = [dataset_section]
        sections.extend(_render_children(engine, block, options, extra))
        return _join_sections(sections)


class RecordComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        data = block.content.data if block.content and block.content.data else {}
        sections: list[str] = []
        if data:
            title_key = next((key for key in ("title", "name", "id") if key in data), None)
            if title_key:
                title_value = data.get(title_key)
                if isinstance(title_value, str):
                    sections.append(f"#### {title_value}")
            lines = [
                f"- **{k}**: {v}"
                for k, v in sorted(data.items())
                if k != title_key
            ]
            if lines:
                sections.append("\n".join(lines))
        sections.extend(_render_children(engine, block, options, extra))
        return _join_sections(sections)


class PageGroupComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        title = getattr(block.properties, "title", None) or f"Page Group {block.id}"
        intro = block.content.text if block.content and block.content.text else ""
        sections = [f"## Page Group: {title}"]
        if intro:
            sections.append(intro)
        sections.extend(_render_children(engine, block, options, extra))
        return _join_sections(sections)


class SyncedComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        if (
            options.resolve_synced
            and block.content
            and block.content.synced_from
            and engine.resolve_reference
        ):
            resolved = engine.resolve_reference(block.content.synced_from)
            if resolved is not None and resolved.id != block.id:
                resolved_text = engine.render(resolved, options=options, **dict(extra))
                notice = f"> Synced from {block.content.synced_from}"
                return _join_sections([notice, resolved_text])
        label = block.content.synced_from if block.content else None
        sections = [f"> Unresolved synced block ({label or block.id})"]
        sections.extend(_render_children(engine, block, options, extra))
        return _join_sections(sections)


class PageComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        title = getattr(block.properties, "title", None) or f"Page {block.id}"
        sections = [f"## {title}"]
        sections.extend(_render_children(engine, block, options, extra))
        return _join_sections(sections)


class GenericComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        label = getattr(block.properties, "title", None) or block.type.value
        text = block.content.text if isinstance(block.content, Content) and block.content.text else ""
        sections = [f"### {label}"]
        if text:
            sections.append(text)
        sections.extend(_render_children(engine, block, options, extra))
        return _join_sections(sections)


# Helper utilities -----------------------------------------------------------

def _render_children(
    engine: MarkdownRenderer,
    block: Block,
    options: RenderOptions,
    extra: Mapping[str, Any],
) -> list[str]:
    if not options.recursive:
        return []
    child_kwargs = dict(extra)
    rendered_children = [
        engine.render(child, options=options, **child_kwargs) for child in block.children()
    ]
    return [child for child in rendered_children if child.strip()]


def _join_sections(sections: list[str]) -> str:
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


def _indent_markdown(text: str, spaces: int = 2) -> str:
    indent = " " * spaces
    return "\n".join(f"{indent}{line}" if line else line for line in text.splitlines())


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


def _block_text(block: Block) -> str:
    if block.content and block.content.text:
        return block.content.text.strip()
    return ""


def _bullet_marker(block: Block) -> str:
    parent = block.parent()
    if parent and parent.type is BlockType.NUMBERED_LIST_ITEM:
        # Nested ordered lists should still render bullets for unordered children
        return "-"
    return "-"


def _ordered_index(block: Block) -> int:
    parent = block.parent()
    if parent is None:
        return 1
    index = 0
    for sibling in parent.children():
        if sibling.type is BlockType.NUMBERED_LIST_ITEM:
            index += 1
        if sibling.id == block.id:
            return index or 1
    return 1
# List item components -------------------------------------------------------


class BulletedListItemComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        bullet = _bullet_marker(block)
        text = _block_text(block)
        line = f"{bullet} {text}".rstrip()
        sections = [line]

        for child in block.children():
            rendered = engine.render(child, options=options, **dict(extra))
            if not rendered.strip():
                continue
            sections.append(_indent_markdown(rendered, spaces=4))

        return "\n".join(sections)


class NumberedListItemComponent:
    def render(
        self,
        block: Block,
        *,
        engine: MarkdownRenderer,
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        index = _ordered_index(block)
        text = _block_text(block)
        line = f"{index}. {text}".rstrip()
        sections = [line]

        for child in block.children():
            rendered = engine.render(child, options=options, **dict(extra))
            if not rendered.strip():
                continue
            sections.append(_indent_markdown(rendered, spaces=4))

        return "\n".join(sections)
