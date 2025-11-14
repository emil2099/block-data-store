"""Shared NiceGUI demo state (store, renderer, seed data)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.exc import OperationalError

from block_data_store.db.engine import create_engine, create_session_factory
from block_data_store.db.schema import create_all
from block_data_store.parser import load_markdown_path
from block_data_store.renderers.markdown import MarkdownRenderer
from block_data_store.store import DocumentStore, create_document_store

DB_PATH = Path(__file__).resolve().parent.parent / "nicegui_demo.db"
SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@dataclass(slots=True)
class DemoContext:
    store: DocumentStore
    renderer: MarkdownRenderer


_CONTEXT: Optional[DemoContext] = None


def get_context() -> DemoContext:
    """Return a singleton demo context, seeding data on first access."""

    global _CONTEXT
    if _CONTEXT is None:
        _CONTEXT = _bootstrap_context()
    return _CONTEXT


def _bootstrap_context() -> DemoContext:
    store = _create_store()
    try:
        _seed_documents(store)
    except OperationalError:
        # Likely schema drift (old DB without new columns). Reset the demo DB.
        if DB_PATH.exists():
            DB_PATH.unlink()
        store = _create_store()
        _seed_documents(store)
    renderer = MarkdownRenderer()
    return DemoContext(store=store, renderer=renderer)


def _seed_documents(store: DocumentStore) -> None:
    if store.list_documents():
        return
    for path in sorted(SAMPLE_DATA_DIR.glob("*.md")):
        blocks = load_markdown_path(path)
        store.save_blocks(blocks)


__all__ = ["DemoContext", "get_context"]
def _create_store() -> DocumentStore:
    engine = create_engine(sqlite_path=DB_PATH)
    create_all(engine)
    session_factory = create_session_factory(engine)
    return create_document_store(session_factory)

