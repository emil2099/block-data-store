"""Seed the sample secondary-tree scenario and print summary views."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from block_data_store.db.engine import create_engine, create_session_factory
from block_data_store.db.schema import create_all
from block_data_store.models.block import (
    Block,
    BlockType,
    Content,
    block_class_for,
    properties_model_for,
)
from block_data_store.store import create_document_store

DEFAULT_SPEC_PATH = Path("data/secondary_tree_example.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec",
        type=Path,
        default=DEFAULT_SPEC_PATH,
        help="Path to the JSON spec (default: data/secondary_tree_example.json)",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=None,
        help="Optional SQLite file to persist the example (defaults to in-memory).",
    )
    args = parser.parse_args()

    blocks = load_blocks(args.spec)

    engine = (
        create_engine(sqlite_path=args.sqlite_path)
        if args.sqlite_path
        else create_engine()
    )
    create_all(engine)
    session_factory = create_session_factory(engine)
    store = create_document_store(session_factory)
    store.save_blocks(blocks)

    document_ids = [block.id for block in blocks if block.type is BlockType.DOCUMENT]
    if document_ids:
        document = store.get_root_tree(document_ids[0], depth=None)
        print(f"Loaded document {document.properties.title or document.id}\n")
        _print_tree(document)
        print()

    page_group_ids = [block.id for block in blocks if block.type is BlockType.PAGE_GROUP]
    for page_group_id in page_group_ids:
        view = store.get_slice(page_group_id, resolve_synced=True, target_depth=None)
        print(f"Page group: {view.page_group.properties.title or view.page_group.id}")
        for resolved in view.resolved_children:
            title = getattr(resolved.target.properties, "title", None)
            print(f"  - {resolved.target.type.value}: {title or resolved.target.id}")
        print()

    if args.sqlite_path:
        print(f"Example persisted to sqlite:///{args.sqlite_path}")


def load_blocks(path: Path) -> list[Block]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_blocks: Iterable[dict[str, Any]] = data.get("blocks", [])
    timestamp = datetime.now(timezone.utc)
    blocks: list[Block] = []
    for entry in raw_blocks:
        block_type = BlockType(entry["type"])
        block_cls = block_class_for(block_type)
        parent_id = _maybe_uuid(entry.get("parent_id"))
        root_id = _require_uuid(entry.get("root_id"))
        children_ids = tuple(_maybe_uuid(child) for child in entry.get("children_ids", []))
        properties_cls = properties_model_for(block_type)
        properties = properties_cls(**(entry.get("properties") or {}))
        content_spec = entry.get("content") or None
        content = _build_content(content_spec)

        block = block_cls(
            id=_require_uuid(entry["id"]),
            type=block_type,
            parent_id=parent_id,
            root_id=root_id,
            children_ids=tuple(child_id for child_id in children_ids if child_id),
            workspace_id=None,
            version=0,
            created_time=timestamp,
            last_edited_time=timestamp,
            created_by=None,
            last_edited_by=None,
            properties=properties,
            metadata=entry.get("metadata") or {},
            content=content,
        )
        blocks.append(block)
    return blocks


def _build_content(spec: dict[str, Any] | None) -> Content | None:
    if spec is None:
        return None
    payload = dict(spec)
    if payload.get("synced_from"):
        payload["synced_from"] = UUID(payload["synced_from"])
    return Content(**payload)


def _maybe_uuid(value: str | None) -> UUID | None:
    return UUID(value) if value else None


def _require_uuid(value: str | None) -> UUID:
    if value is None:
        raise ValueError("UUID is required in example spec")
    return UUID(value)


def _print_tree(block: Block, indent: int = 0) -> None:
    prefix = " " * indent
    title = getattr(block.properties, "title", None)
    label = title or (block.content.text if block.content and block.content.text else None)
    print(f"{prefix}- {block.type.value}: {label or block.id}")
    for child in block.children():
        _print_tree(child, indent + 2)


if __name__ == "__main__":
    main()
