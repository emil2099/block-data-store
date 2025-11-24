"""Minimal demo script for parsing markdown and persisting blocks."""

from __future__ import annotations

import argparse
from pathlib import Path

from block_data_store.db.engine import create_engine, create_session_factory
from block_data_store.db.schema import create_all
from block_data_store.parser import load_markdown_path
from block_data_store.store import create_document_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Markdown into the block data store.")
    parser.add_argument("path", type=Path, help="Path to a Markdown document.")
    args = parser.parse_args()

    blocks = load_markdown_path(args.path)

    engine = create_engine()
    create_all(engine)
    session_factory = create_session_factory(engine)
    store = create_document_store(session_factory)
    store.upsert_blocks(blocks)

    document = store.get_root_tree(blocks[0].id)
    if document is None:
        raise SystemExit("Failed to load document from repository.")

    print(f"Persisted document {document.id} with {len(blocks)} blocks:\n")
    _print_tree(document, indent=0)


def _print_tree(block, indent: int) -> None:
    prefix = " " * indent
    title = getattr(block.properties, "title", None)
    label = title or getattr(block.properties, "category", None)
    if not label and block.content and block.content.plain_text:
        label = block.content.plain_text.splitlines()[0][:60]
    block_type = block.type.value if hasattr(block.type, "value") else str(block.type)
    print(f"{prefix}- {block_type} ({block.id})", end="")
    if label:
        print(f": {label}")
    else:
        print()
    for child in block.children():
        _print_tree(child, indent=indent + 2)


if __name__ == "__main__":
    main()
