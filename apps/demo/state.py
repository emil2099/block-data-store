"""Shared NiceGUI demo state (store, renderer, seed data)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from block_data_store.db.engine import create_engine, create_session_factory
from block_data_store.db.schema import create_all
from block_data_store.models.block import BlockType
from block_data_store.parser import load_markdown_path
from block_data_store.renderers.markdown import MarkdownRenderer
from block_data_store.repositories.filters import WhereClause
from block_data_store.store import DocumentStore, create_document_store
from sqlalchemy.exc import OperationalError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOTENV_PATH = PROJECT_ROOT / ".env"
DB_PATH = Path(__file__).resolve().parent.parent / "nicegui_demo.db"
SAMPLE_DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_PDFS = [
    SAMPLE_DATA_DIR / "sample-local-pdf.pdf",
    SAMPLE_DATA_DIR / "SYSC 4 General organisational requirements.pdf",
]
DATASET_TARGET = SAMPLE_DATA_DIR / "sample_dataset.csv"
DATASET_SOURCE = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "datasets" / "sample_dataset.csv"


@dataclass(slots=True)
class DemoContext:
    store: DocumentStore
    renderer: MarkdownRenderer


_CONTEXT: Optional[DemoContext] = None


def get_context() -> DemoContext:
    """Return a singleton demo context, seeding data on first access."""

    global _CONTEXT
    if _CONTEXT is None:
        _load_dotenv()
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
        print("[demo] documents already present; skipping markdown seed")
    else:
        print("[demo] seeding markdown samples")
        for path in sorted(SAMPLE_DATA_DIR.glob("*.md")):
            blocks = load_markdown_path(path)
            store.save_blocks(blocks)

    _ingest_sample_pdfs(store)
    _ingest_sample_dataset(store)


__all__ = ["DemoContext", "get_context"]
def _create_store() -> DocumentStore:
    engine = create_engine(sqlite_path=DB_PATH)
    create_all(engine)
    session_factory = create_session_factory(engine)
    return create_document_store(session_factory)


def _document_exists_with_metadata(store: DocumentStore, key: str, value: str) -> bool:
    documents = store.list_documents()
    return any((doc.metadata or {}).get(key) == value for doc in documents)


def _ingest_sample_pdfs(store: DocumentStore) -> None:
    try:
        from block_data_store.parser.azure_di_parser import azure_di_to_blocks
    except ImportError:
        print("[demo] azure-ai-documentintelligence not installed; skipping PDF ingest")
        return

    for pdf_path in SAMPLE_PDFS:
        if not pdf_path.exists():
            print(f"[demo] PDF sample missing: {pdf_path}")
            continue
        marker = f"pdf::{pdf_path.name}"
        if _document_exists_with_metadata(store, "demo_source", marker):
            print(f"[demo] PDF already ingested: {pdf_path.name}")
            continue
        try:
            with pdf_path.open("rb") as handle:
                blocks = azure_di_to_blocks(handle)
        except Exception as exc:
            print(f"[demo] Azure DI parse failed for {pdf_path.name}: {exc}")
            continue

        if not blocks:
            continue
        root = blocks[0]
        metadata = dict(root.metadata)
        metadata["demo_source"] = marker
        blocks[0] = root.model_copy(update={"metadata": metadata})
        store.save_blocks(blocks)
        print(f"[demo] stored PDF document: {pdf_path.name}")


def _ingest_sample_dataset(store: DocumentStore) -> None:
    if not DATASET_TARGET.exists() and DATASET_SOURCE.exists():
        DATASET_TARGET.write_text(DATASET_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    if not DATASET_TARGET.exists():
        print("[demo] dataset sample missing; skipping dataset ingest")
        return

    dataset_roots = store.query_blocks(where=WhereClause(type=BlockType.DATASET))
    for block in dataset_roots:
        if block.parent_id is None and (block.metadata or {}).get("demo_source") == "dataset::sample":
            return

    try:
        from block_data_store.parser.dataset_parser import DatasetParserConfig, dataset_to_blocks
    except ImportError:
        print("[demo] pandas not installed; skipping dataset ingest")
        return

    try:
        blocks = dataset_to_blocks(
            DATASET_TARGET,
            config=DatasetParserConfig(title="Sample Dataset"),
        )
    except Exception as exc:
        print(f"[demo] dataset parse failed: {exc}")
        return

    if not blocks:
        return
    root = blocks[0]
    metadata = dict(root.metadata)
    metadata["demo_source"] = "dataset::sample"
    blocks[0] = root.model_copy(update={"metadata": metadata})
    store.save_blocks(blocks)
    print("[demo] stored sample dataset")


def _load_dotenv() -> None:
    if not DOTENV_PATH.exists():
        return
    for raw_line in DOTENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip()
