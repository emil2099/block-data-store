"""Markdown → Block conversion that mirrors Mistune's AST structure."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import mistune

from block_data_store.models.block import (
    Block,
    BlockProperties,
    BlockType,
    Content,
    block_class_for,
    properties_model_for,
)

MarkdownAst = list[dict[str, Any]]

_DEFAULT_PLUGINS: tuple[str, ...] = ("table",)


def parse_markdown(source: str) -> MarkdownAst:
    """Return Mistune's AST for the provided Markdown source."""
    markdown = mistune.create_markdown(renderer="ast", plugins=_DEFAULT_PLUGINS)
    return markdown(source)


def markdown_to_blocks(
    source: str,
    *,
    workspace_id: UUID | None = None,
    document_id: UUID | None = None,
    timestamp: datetime | None = None,
) -> list[Block]:
    """Convert Markdown source into canonical block models."""
    ast = parse_markdown(source)
    return ast_to_blocks(
        ast,
        workspace_id=workspace_id,
        document_id=document_id,
        timestamp=timestamp,
    )


def load_markdown_path(
    path: str | Path,
    *,
    workspace_id: UUID | None = None,
    document_id: UUID | None = None,
    timestamp: datetime | None = None,
) -> list[Block]:
    """Read Markdown from disk and convert to blocks."""
    content = Path(path).read_text(encoding="utf-8")
    return markdown_to_blocks(
        content,
        workspace_id=workspace_id,
        document_id=document_id,
        timestamp=timestamp,
    )


def ast_to_blocks(
    tokens: MarkdownAst,
    *,
    workspace_id: UUID | None = None,
    document_id: UUID | None = None,
    timestamp: datetime | None = None,
) -> list[Block]:
    """Convert a pre-computed Markdown AST into blocks."""
    document_id = document_id or uuid4()
    timestamp = timestamp or datetime.now(timezone.utc)

    nodes: list[dict[str, Any]] = []
    by_id: dict[UUID, dict[str, Any]] = {}
    children: dict[UUID, list[UUID]] = defaultdict(list)

    def add_node(
        block_type: BlockType,
        parent_id: UUID | None,
        *,
        properties: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        content: Content | None = None,
        node_id: UUID | None = None,
    ) -> UUID:
        block_id = node_id or uuid4()
        record = {
            "id": block_id,
            "type": block_type,
            "parent_id": parent_id,
            "properties": properties if properties is not None else {},
            "metadata": metadata if metadata is not None else {},
            "content": content,
        }
        nodes.append(record)
        by_id[block_id] = record
        if parent_id is not None:
            children[parent_id].append(block_id)
        return block_id

    document_props: dict[str, Any] = {}
    document_node_id = add_node(
        BlockType.DOCUMENT,
        None,
        properties=document_props,
        node_id=document_id,
    )
    heading_stack: list[tuple[int, UUID]] = []

    _process_tokens(
        tokens,
        default_parent=document_node_id,
        heading_stack=heading_stack,
        add_node=add_node,
        by_id=by_id,
        document_id=document_node_id,
        document_props=document_props,
    )

    return _realise_blocks(nodes, children, workspace_id, document_id, timestamp)


def _process_tokens(
    tokens: MarkdownAst,
    *,
    default_parent: UUID,
    heading_stack: list[tuple[int, UUID]] | None,
    add_node: Any,
    by_id: dict[UUID, dict[str, Any]],
    document_id: UUID,
    document_props: dict[str, Any],
) -> None:
    local_heading_stack = heading_stack if heading_stack is not None else []

    for token in tokens:
        token_type = token.get("type")
        if token_type in {"blank_line", "linebreak", "softbreak"}:
            continue

        if token_type == "heading":
            _append_heading(
                add_node,
                token,
                local_heading_stack,
                default_parent=default_parent,
                document_id=document_id,
                document_props=document_props,
                allow_document_title=heading_stack is not None,
            )
            continue

        parent_id = _parent_for_content(local_heading_stack, default_parent)

        if token_type == "paragraph":
            _append_paragraph(add_node, parent_id, token)
            continue

        if token_type == "list":
            _emit_list(add_node, parent_id, token, by_id)
            continue

        if token_type == "block_code":
            _append_code(add_node, parent_id, token)
            continue

        if token_type == "block_quote":
            quote_id = add_node(BlockType.QUOTE, parent_id)
            _process_tokens(
                token.get("children", []),
                default_parent=quote_id,
                heading_stack=None,
                add_node=add_node,
                by_id=by_id,
                document_id=document_id,
                document_props=document_props,
            )
            continue

        if token_type in {"html_block", "block_html"}:
            _append_html(add_node, parent_id, token)
            continue

        if token_type == "table":
            _append_table(add_node, parent_id, token)
            continue

        fallback = _extract_text(token).strip()
        if fallback:
            _append_paragraph(add_node, parent_id, {"raw": fallback})


def _append_paragraph(
    add_node: Any,
    parent_id: UUID,
    token: dict[str, Any],
) -> None:
    text = _extract_text(token).strip()
    if text:
        add_node(
            BlockType.PARAGRAPH,
            parent_id,
            content=Content(plain_text=text),
        )


def _emit_list(
    add_node: Any,
    parent_id: UUID,
    token: dict[str, Any],
    by_id: dict[UUID, dict[str, Any]],
) -> None:
    ordered = bool(token.get("attrs", {}).get("ordered", False))
    item_type = BlockType.NUMBERED_LIST_ITEM if ordered else BlockType.BULLETED_LIST_ITEM

    items = [child for child in token.get("children", []) if child.get("type") == "list_item"]
    for index, item in enumerate(items, start=1):
        item_id = add_node(
            item_type,
            parent_id,
        )
        item_node = by_id[item_id]

        content_assigned = False
        for child in item.get("children", []):
            child_type = child.get("type")
            if child_type in {"block_text", "paragraph"}:
                text = _extract_text(child).strip()
                if not text:
                    continue
                if not content_assigned:
                    item_node["content"] = Content(plain_text=text)
                    content_assigned = True
                else:
                    _append_paragraph(add_node, item_id, {"raw": text})
            elif child_type == "list":
                _emit_list(add_node, item_id, child, by_id)
            else:
                text = _extract_text(child).strip()
                if text:
                    _append_paragraph(add_node, item_id, {"raw": text})


def _parent_for_content(
    heading_stack: list[tuple[int, UUID]] | None,
    fallback_parent: UUID,
) -> UUID:
    if heading_stack:
        return heading_stack[-1][1]
    return fallback_parent


def _append_heading(
    add_node: Any,
    token: dict[str, Any],
    heading_stack: list[tuple[int, UUID]],
    *,
    default_parent: UUID,
    document_id: UUID,
    document_props: dict[str, Any],
    allow_document_title: bool,
) -> None:
    level = int(token.get("attrs", {}).get("level", 1))
    text = _extract_text(token).strip()
    if not text:
        return

    if allow_document_title and default_parent == document_id and level == 1 and not document_props.get("title"):
        document_props["title"] = text
        heading_stack.clear()
        return

    while heading_stack and heading_stack[-1][0] >= level:
        heading_stack.pop()

    parent_id = heading_stack[-1][1] if heading_stack else default_parent
    heading_id = add_node(
        BlockType.HEADING,
        parent_id,
        properties={"level": level},
        content=Content(plain_text=text),
    )
    heading_stack.append((level, heading_id))


def _append_code(
    add_node: Any,
    parent_id: UUID,
    token: dict[str, Any],
) -> None:
    info = (token.get("attrs", {}).get("info") or "").strip()
    raw_text = (token.get("raw") or "").rstrip("\n")
    if not raw_text and not info:
        return

    properties = {"language": info or None}
    add_node(
        BlockType.CODE,
        parent_id,
        properties=properties,
        content=Content(plain_text=raw_text),
    )


def _append_html(
    add_node: Any,
    parent_id: UUID,
    token: dict[str, Any],
) -> None:
    raw_text = (token.get("raw") or "").rstrip("\n")
    if not raw_text:
        return
    add_node(
        BlockType.HTML,
        parent_id,
        content=Content(plain_text=raw_text),
    )


def _append_table(
    add_node: Any,
    parent_id: UUID,
    token: dict[str, Any],
) -> None:
    headers: list[list[str]] = []
    rows: list[list[str]] = []
    alignments: list[str | None] = []

    for section in token.get("children", []):
        section_type = section.get("type")
        if section_type == "table_head":
            header_rows, aligns = _table_section_rows(section)
            headers = header_rows
            if aligns:
                alignments = aligns
        elif section_type == "table_body":
            body_rows, _ = _table_section_rows(section)
            rows.extend(body_rows)

    table_object: dict[str, Any] = {
        "headers": headers[0] if headers else [],
        "rows": rows,
    }
    if alignments:
        table_object["align"] = alignments

    add_node(
        BlockType.TABLE,
        parent_id,
        content=Content(object=table_object),
    )


def _table_section_rows(section: dict[str, Any]) -> tuple[list[list[str]], list[str | None]]:
    rows: list[list[str]] = []
    alignments: list[str | None] = []
    children = section.get("children", [])
    if children and children[0].get("type") == "table_cell":
        current_row: list[str] = []
        for index, cell in enumerate(children):
            text = _extract_text(cell).strip()
            current_row.append(text)
            align_value = cell.get("attrs", {}).get("align")
            if len(alignments) <= index:
                alignments.append(_normalise_alignment(align_value))
            elif align_value is not None:
                alignments[index] = _normalise_alignment(align_value)
        rows.append(current_row)
        return rows, alignments

    for row in children:
        if row.get("type") != "table_row":
            continue
        current_row = []
        for index, cell in enumerate(row.get("children", [])):
            text = _extract_text(cell).strip()
            current_row.append(text)
            attrs = cell.get("attrs", {})
            align_value = attrs.get("align")
            if len(alignments) <= index:
                alignments.append(_normalise_alignment(align_value))
            elif align_value is not None:
                alignments[index] = _normalise_alignment(align_value)
        rows.append(current_row)
    return rows, alignments


def _normalise_alignment(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).lower()
    if text in {"left", "center", "right"}:
        return text
    return None


def _realise_blocks(
    nodes: list[dict[str, Any]],
    children: dict[UUID, list[UUID]],
    workspace_id: UUID | None,
    document_id: UUID,
    timestamp: datetime,
) -> list[Block]:
    realised: list[Block] = []
    for record in nodes:
        block_type: BlockType = record["type"]
        block_cls = block_class_for(block_type)
        properties = record["properties"]

        if isinstance(properties, BlockProperties):
            props_model = properties
        else:
            props_cls = properties_model_for(block_type) or BlockProperties
            props_model = props_cls(**properties)

        block = block_cls(
            id=record["id"],
            type=block_type,
            parent_id=record["parent_id"],
            root_id=document_id,
            children_ids=tuple(children.get(record["id"], [])),
            workspace_id=workspace_id,
            version=0,
            created_time=timestamp,
            last_edited_time=timestamp,
            created_by=None,
            last_edited_by=None,
            properties=props_model,
            metadata=dict(record["metadata"]),
            content=record["content"],
        )
        realised.append(block)
    return realised


def _extract_text(token: dict[str, Any]) -> str:
    token_type = token.get("type")
    if token_type in {"softbreak", "linebreak"}:
        return "\n"
    raw = token.get("raw")
    if isinstance(raw, str):
        return raw
    parts: list[str] = []
    for child in token.get("children", []):
        parts.append(_extract_text(child))
    return "".join(parts)


__all__ = [
    "MarkdownAst",
    "parse_markdown",
    "markdown_to_blocks",
    "ast_to_blocks",
    "load_markdown_path",
]
