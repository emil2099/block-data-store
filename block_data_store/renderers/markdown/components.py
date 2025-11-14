"""Markdown renderer component implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence, TYPE_CHECKING

from block_data_store.models.block import Block, BlockType, Content
from block_data_store.renderers.base import RenderOptions, RendererComponent

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from .renderer import MarkdownRenderer


# ---------------------------------------------------------------------------
# Rendering context & base component


@dataclass(slots=True)
class RenderContext:
    engine: "MarkdownRenderer"
    options: RenderOptions
    extra: Mapping[str, Any]

    def child_kwargs(self) -> dict[str, Any]:
        return dict(self.extra)

    def render_children(self, block: Block) -> list[str]:
        if not self.options.recursive:
            return []
        child_kwargs = self.child_kwargs()
        rendered_children = [
            self.engine.render(child, options=self.options, **child_kwargs)
            for child in block.children()
        ]
        return [child for child in rendered_children if child.strip()]

    def join(self, sections: Sequence[str]) -> str:
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

    def indent(self, text: str, *, spaces: int = 4) -> str:
        indent = " " * spaces
        return "\n".join(f"{indent}{line}" if line else line for line in text.splitlines())

    def quote(self, text: str) -> str:
        lines = text.splitlines() or [""]
        quoted = [f"> {line}" if line else ">" for line in lines]
        return "\n".join(quoted)

    def render_block(self, block: Block) -> str:
        return self.engine.render(block, options=self.options, **self.child_kwargs())


class BaseComponent(RendererComponent):
    def render(
        self,
        block: Block,
        *,
        engine: "MarkdownRenderer",
        options: RenderOptions,
        extra: Mapping[str, Any],
    ) -> str:
        ctx = RenderContext(engine=engine, options=options, extra=extra)
        return self.render_block(block, ctx)

    def render_block(self, block: Block, ctx: RenderContext) -> str:  # pragma: no cover - abstract
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Component implementations


class DocumentComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        title = getattr(block.properties, "title", None)
        heading = f"# {title}" if title else f"# Document {block.id}"
        sections = [heading]
        for child in block.children():
            if child.type in {BlockType.GROUP_INDEX, BlockType.PAGE_GROUP}:
                continue
            rendered = ctx.render_block(child)
            if rendered.strip():
                sections.append(rendered)
        return ctx.join(sections)


class HeadingComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        props = block.properties
        level = getattr(props, "level", 2) if props is not None else 2
        level = max(1, min(level, 6))
        text = block.content.plain_text if block.content and block.content.plain_text else f"Heading {block.id}"
        prefix = "#" * level
        sections = [f"{prefix} {text}"]
        sections.extend(ctx.render_children(block))
        return ctx.join(sections)


class ParagraphComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        text = block.content.plain_text if block.content and block.content.plain_text else ""
        sections = [text] if text else []
        sections.extend(ctx.render_children(block))
        return ctx.join(sections)


class QuoteComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        sections = ctx.render_children(block)
        body = ctx.join(sections)
        if not body and block.content and block.content.plain_text:
            body = block.content.plain_text
        if not body:
            return ""
        return ctx.quote(body)


class CodeComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        language = getattr(block.properties, "language", None) or ""
        code_text = block.content.plain_text if block.content and block.content.plain_text else ""
        fence = f"```{language}" if language else "```"
        section = "\n".join([fence, code_text, "```"]).strip("\n")
        sections = [section]
        sections.extend(ctx.render_children(block))
        return ctx.join(sections)


class TableComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        table = block.content.object if block.content and block.content.object else {}
        headers = list(table.get("headers") or [])
        rows = [list(row) for row in table.get("rows") or []]
        width = len(headers) or (len(rows[0]) if rows else 0)
        if width == 0:
            return ""
        alignments = table.get("align") or []
        header_line = format_table_row(headers or ["" for _ in range(width)], width)
        align_line = format_alignment_row(alignments, width)
        body_lines = [format_table_row(row, width) for row in rows]
        sections = ["\n".join([header_line, align_line, *body_lines])]
        sections.extend(ctx.render_children(block))
        return ctx.join(sections)


class HtmlComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        html_text = block.content.plain_text if block.content and block.content.plain_text else ""
        sections = [html_text] if html_text else []
        sections.extend(ctx.render_children(block))
        return ctx.join(sections)


class DatasetComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        props = block.properties
        title = getattr(props, "title", None)
        schema_columns = dataset_columns_from_schema(props)

        record_children: list[Block] = []
        other_children: list[Block] = []
        if ctx.options.recursive:
            for child in block.children():
                if child.type is BlockType.RECORD:
                    record_children.append(child)
                else:
                    other_children.append(child)

        columns = schema_columns or infer_dataset_columns(record_children)
        table_markdown = render_dataset_table(columns, record_children)

        sections: list[str] = []
        if title:
            sections.append(f"### {title}")
        if table_markdown:
            sections.append(table_markdown)
        elif not columns:
            sections.append("_No records_")

        for child in other_children:
            rendered = ctx.render_block(child)
            if rendered.strip():
                sections.append(rendered)

        return ctx.join(sections)


class RecordComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        data = block.content.data if block.content and block.content.data else {}
        if not data:
            return ""
        ordered_keys = list(data.keys())
        row = [stringify_cell(data.get(key)) for key in ordered_keys]
        return format_table_row(row, len(row))


class ObjectComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        sections: list[str] = []
        summary = None
        if block.content and block.content.plain_text:
            summary = block.content.plain_text
        elif getattr(block.properties, "category", None):
            summary = getattr(block.properties, "category")
        if summary:
            sections.append(summary)

        if block.content and block.content.object:
            payload = json.dumps(block.content.object, indent=2, sort_keys=True)
            sections.append("\n".join(["```json", payload, "```"]))

        sections.extend(ctx.render_children(block))
        return ctx.join(sections)


class StructuralComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:  # noqa: ARG002
        return ""


class UnsupportedComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:  # noqa: ARG002
        return "[unsupported content]"


class GenericComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        label = getattr(block.properties, "title", None) or block.type.value
        text = block.content.plain_text if isinstance(block.content, Content) and block.content.plain_text else ""
        sections = [f"### {label}"]
        if text:
            sections.append(text)
        sections.extend(ctx.render_children(block))
        return ctx.join(sections)


class PageGroupComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        root = _find_root(block)
        ordered = _ordered_blocks(root)
        sections: list[str] = []
        for candidate in ordered:
            if candidate.id == block.id:
                continue
            groups = getattr(candidate.properties, "groups", None)
            if not groups or block.id not in groups:
                continue
            if candidate.type in {BlockType.GROUP_INDEX, BlockType.PAGE_GROUP}:
                continue
            rendered = ctx.render_block(candidate)
            if rendered.strip():
                sections.append(rendered)
        return ctx.join(sections)


class GroupIndexComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        index_type = getattr(block.properties, "group_index_type", None)
        if index_type != "page":
            return ""
        sections: list[str] = []
        for child in block.children():
            rendered = ctx.render_block(child)
            if rendered.strip():
                sections.append(rendered)
        return ctx.join(sections)


class BulletedListItemComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        text = _block_text(block)
        line = f"* {text}".rstrip()
        sections = [line]
        for child in block.children():
            rendered = ctx.render_block(child)
            if not rendered.strip():
                continue
            sections.append(ctx.indent(rendered))
        return "\n".join(sections)


class NumberedListItemComponent(BaseComponent):
    def render_block(self, block: Block, ctx: RenderContext) -> str:
        index = _ordered_index(block)
        text = _block_text(block)
        line = f"{index}. {text}".rstrip()
        sections = [line]
        for child in block.children():
            rendered = ctx.render_block(child)
            if not rendered.strip():
                continue
            sections.append(ctx.indent(rendered))
        return "\n".join(sections)


# ---------------------------------------------------------------------------
# Dataset/table helpers


@dataclass(slots=True)
class DatasetColumn:
    key: str
    header: str


def dataset_columns_from_schema(props: Any) -> list[DatasetColumn]:
    if props is None:
        return []
    schema = getattr(props, "schema", None) or getattr(props, "data_schema", None)
    if not schema:
        return []
    return _normalise_dataset_schema(schema)


def infer_dataset_columns(records: list[Block]) -> list[DatasetColumn]:
    ordered_keys: list[str] = []
    for record in records:
        data = record.content.data if record.content and record.content.data else {}
        for key in data.keys():
            if key not in ordered_keys:
                ordered_keys.append(key)
    return [DatasetColumn(key, _pretty_label(key)) for key in ordered_keys]


def render_dataset_table(columns: list[DatasetColumn], records: list[Block]) -> str:
    if not columns:
        return ""
    width = len(columns)
    headers = [column.header for column in columns]
    header_line = format_table_row(headers, width)
    align_line = format_alignment_row(["left"] * width, width)
    body_lines: list[str] = []
    for record in records:
        data = record.content.data if record.content and record.content.data else {}
        row = [stringify_cell(data.get(column.key)) for column in columns]
        body_lines.append(format_table_row(row, width))
    return "\n".join([header_line, align_line, *body_lines])


def format_table_row(values: list[Any], width: int) -> str:
    cells = ["" if value is None else str(value) for value in values]
    if len(cells) < width:
        cells.extend([""] * (width - len(cells)))
    elif len(cells) > width:
        cells = cells[:width]
    return f"| {' | '.join(cells)} |"


def format_alignment_row(alignments: list[Any], width: int) -> str:
    markers = []
    for index in range(width):
        alignment = alignments[index] if index < len(alignments) else None
        markers.append(_alignment_marker(alignment))
    return f"| {' | '.join(markers)} |"


def stringify_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, sort_keys=True)


def _normalise_dataset_schema(schema: Any) -> list[DatasetColumn]:
    columns_data: list[Any] = []
    if isinstance(schema, dict):
        for key in ("columns", "fields"):
            value = schema.get(key)
            if isinstance(value, list):
                columns_data = value
                break
    elif isinstance(schema, list):
        columns_data = schema

    columns: list[DatasetColumn] = []
    for entry in columns_data:
        if isinstance(entry, dict):
            key = entry.get("key") or entry.get("id") or entry.get("name")
            header = entry.get("title") or entry.get("name") or entry.get("label")
        elif isinstance(entry, str):
            key = entry
            header = None
        else:
            continue
        if not key:
            continue
        columns.append(DatasetColumn(str(key), str(header or _pretty_label(str(key)))))
    return columns


# ---------------------------------------------------------------------------
# Misc helpers (kept local to this module)


def _block_text(block: Block) -> str:
    if block.content and block.content.plain_text:
        return block.content.plain_text.strip()
    return ""


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


def _alignment_marker(alignment: Any) -> str:
    mapping = {
        None: "---",
        "left": ":---",
        "center": ":---:",
        "right": "---:",
    }
    key = str(alignment).lower() if alignment is not None else None
    return mapping.get(key, "---")


def _pretty_label(key: str) -> str:
    text = key.replace("_", " ").replace("-", " ").strip()
    return text.title() if text else key


def _find_root(block: Block) -> Block:
    current = block
    while True:
        parent = current.parent()
        if parent is None:
            return current
        current = parent


def _ordered_blocks(root: Block) -> list[Block]:
    ordered: list[Block] = []

    def walk(node: Block) -> None:
        ordered.append(node)
        for child in node.children():
            walk(child)

    walk(root)
    return ordered


DEFAULT_COMPONENTS: dict[BlockType, RendererComponent] = {
    BlockType.DOCUMENT: DocumentComponent(),
    BlockType.HEADING: HeadingComponent(),
    BlockType.PARAGRAPH: ParagraphComponent(),
    BlockType.BULLETED_LIST_ITEM: BulletedListItemComponent(),
    BlockType.NUMBERED_LIST_ITEM: NumberedListItemComponent(),
    BlockType.QUOTE: QuoteComponent(),
    BlockType.CODE: CodeComponent(),
    BlockType.TABLE: TableComponent(),
    BlockType.HTML: HtmlComponent(),
    BlockType.DATASET: DatasetComponent(),
    BlockType.RECORD: RecordComponent(),
    BlockType.OBJECT: ObjectComponent(),
    BlockType.DERIVED_CONTENT_CONTAINER: StructuralComponent(),
    BlockType.GROUP_INDEX: GroupIndexComponent(),
    BlockType.PAGE_GROUP: PageGroupComponent(),
    BlockType.CHUNK_GROUP: StructuralComponent(),
    BlockType.UNSUPPORTED: UnsupportedComponent(),
}


__all__ = [
    "DEFAULT_COMPONENTS",
    "GenericComponent",
]
