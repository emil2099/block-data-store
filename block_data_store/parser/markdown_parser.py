"""Minimal Markdown → Block conversion tailored for the POC."""

from __future__ import annotations

import json
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


def parse_markdown(source: str) -> MarkdownAst:
    """Return Mistune's AST for the provided Markdown source."""
    markdown = mistune.create_markdown(renderer="ast")
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
    document_node = by_id[document_node_id]

    heading_stack: list[tuple[int, UUID]] = []

    def current_parent() -> UUID:
        return heading_stack[-1][1] if heading_stack else document_node_id

    for token in tokens:
        token_type = token.get("type")
        if token_type == "heading":
            level = int(token.get("attrs", {}).get("level", 1))
            text = _extract_text(token).strip()
            if not text:
                continue
            if level == 1 and not document_props.get("title"):
                document_props["title"] = text
                heading_stack.clear()
                continue
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_id = add_node(
                BlockType.HEADING,
                current_parent(),
                properties={"level": level},
                content=Content(text=text),
            )
            heading_stack.append((level, heading_id))
            continue

        if token_type == "paragraph":
            _append_paragraph(add_node, current_parent(), token)
            continue

        if token_type == "list":
            _emit_list(add_node, current_parent(), token, children, by_id)
            continue

        if token_type == "block_code":
            _handle_block_code(add_node, current_parent(), token, children, by_id)
            continue

        fallback = _extract_text(token).strip()
        if fallback:
            _append_paragraph(add_node, current_parent(), {"raw": fallback})

    return _realise_blocks(nodes, children, workspace_id, document_id, timestamp)


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
            content=Content(text=text),
        )


def _emit_list(
    add_node: Any,
    parent_id: UUID,
    token: dict[str, Any],
    children: dict[UUID, list[UUID]],
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
                    item_node["content"] = Content(text=text)
                    content_assigned = True
                else:
                    _append_paragraph(add_node, item_id, {"raw": text})
            elif child_type == "list":
                _emit_list(add_node, item_id, child, children, by_id)
            else:
                text = _extract_text(child).strip()
                if text:
                    _append_paragraph(add_node, item_id, {"raw": text})


def _handle_block_code(
    add_node: Any,
    parent_id: UUID,
    token: dict[str, Any],
    children: dict[UUID, list[UUID]],
    by_id: dict[UUID, dict[str, Any]],
) -> None:
    info = (token.get("attrs", {}).get("info") or "").strip()
    raw_text = (token.get("raw") or "").strip()
    if not raw_text and not info:
        return

    if info.startswith("dataset:"):
        dataset_type = info.split(":", 1)[1].strip() or "default"
        payload = _parse_dataset_payload(raw_text)
        dataset_content = Content(text=raw_text) if raw_text else None
        dataset_id = add_node(
            BlockType.DATASET,
            parent_id,
            properties={"dataset_type": dataset_type},
            content=dataset_content,
        )
        if isinstance(payload, dict):
            records = payload.get("records")
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict):
                        add_node(
                            BlockType.RECORD,
                            dataset_id,
                            content=Content(data=dict(record)),
                        )
        return

    if raw_text:
        add_node(
            BlockType.PARAGRAPH,
            parent_id,
            content=Content(text=raw_text),
            metadata={"code_block": True, "info": info or None},
        )


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
    raw = token.get("raw")
    if isinstance(raw, str):
        return raw
    parts: list[str] = []
    for child in token.get("children", []):
        parts.append(_extract_text(child))
    return "".join(parts)


def _parse_dataset_payload(raw_text: str) -> Any:
    stripped = raw_text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return stripped


__all__ = [
    "MarkdownAst",
    "parse_markdown",
    "markdown_to_blocks",
    "ast_to_blocks",
    "load_markdown_path",
]
