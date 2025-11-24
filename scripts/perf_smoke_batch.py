"""Batched corpus performance smoke test for the Block Data Store POC.

This variant ingests documents in configurable batches so we can stress the
bulk upsert path (Postgres ON CONFLICT) and only sample metrics at key corpus
sizes. Output schema mirrors ``scripts/perf_smoke.py`` for apples-to-apples
comparisons.
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from pathlib import Path
from typing import Any
import os

from dotenv import load_dotenv

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from block_data_store.db.engine import create_engine, create_session_factory
from block_data_store.db.schema import DbBlock, create_all
from block_data_store.models.block import BlockType
from block_data_store.parser import markdown_to_blocks
from block_data_store.renderers.base import RenderOptions
from block_data_store.renderers.markdown import MarkdownRenderer
from block_data_store.repositories.filters import (
    FilterOperator,
    ParentFilter,
    PropertyFilter,
    WhereClause,
)
from block_data_store.store import create_document_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batched corpus performance smoke test")
    parser.add_argument(
        "--document",
        type=Path,
        default=Path("data/poc_long_showcase.md"),
        help="Markdown document to ingest repeatedly.",
    )
    parser.add_argument(
        "--steps",
        type=str,
        default="1,10,100,1000",
        help="Comma-separated corpus checkpoints (e.g. 1,10,100,1000).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=10,
        help="Number of documents to sample when calculating averages.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Documents to ingest per batch (default 25).",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Optional SQLAlchemy URL (e.g. Postgres). Defaults to env DATABASE_URL then in-memory SQLite.",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=None,
        help="Optional SQLite file path (ignored if --database-url provided).",
    )
    parser.add_argument(
        "--clear-db",
        action="store_true",
        help="Drop existing tables before running (safe for Postgres).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path (defaults to stdout).",
    )
    parser.add_argument(
        "--log-interval",
        type=int,
        default=5,
        help="Log progress every N batches (default 5).",
    )
    parser.add_argument(
        "--log-every-batch",
        action="store_true",
        help="Log ingest timings for every batch regardless of log-interval.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress logs; only emit JSON telemetry.",
    )
    return parser.parse_args()


def ensure_schema(engine, reset: bool) -> None:
    if reset:
        DbBlock.__table__.drop(engine, checkfirst=True)
    create_all(engine)


def average(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def measure_sample(store, renderer: MarkdownRenderer, document_ids: list[Any], heading_hint: str) -> dict[str, float]:
    fetch_times: list[float] = []
    render_times: list[float] = []
    render_lengths: list[int] = []
    filter_paragraph_times: list[float] = []
    filter_parent_times: list[float] = []
    paragraph_counts: list[int] = []
    parent_counts: list[int] = []

    for doc_id in document_ids:
        fetch_start = time.perf_counter()
        document_block = store.get_root_tree(doc_id, depth=None)
        fetch_times.append((time.perf_counter() - fetch_start) * 1000)

        render_start = time.perf_counter()
        rendered_doc = renderer.render(document_block, options=RenderOptions())
        render_times.append((time.perf_counter() - render_start) * 1000)
        render_lengths.append(len(rendered_doc))

        filter_start = time.perf_counter()
        paragraphs = store.query_blocks(where=WhereClause(type=BlockType.PARAGRAPH, root_id=str(doc_id)))
        filter_paragraph_times.append((time.perf_counter() - filter_start) * 1000)
        paragraph_counts.append(len(paragraphs))

        parent_start = time.perf_counter()
        onboarding = store.query_blocks(
            where=WhereClause(type=BlockType.PARAGRAPH, root_id=str(doc_id)),
            parent=ParentFilter(
                where=WhereClause(type=BlockType.HEADING, root_id=str(doc_id)),
                property_filter=PropertyFilter(
                    path="content.plain_text",
                    value=heading_hint,
                    operator=FilterOperator.CONTAINS,
                ),
            ),
        )
        filter_parent_times.append((time.perf_counter() - parent_start) * 1000)
        parent_counts.append(len(onboarding))

    return {
        "avg_fetch_ms": average(fetch_times),
        "avg_render_ms": average(render_times),
        "avg_render_length": average(render_lengths),
        "avg_filter_paragraph_ms": average(filter_paragraph_times),
        "avg_filter_parent_ms": average(filter_parent_times),
        "avg_paragraph_count": average(paragraph_counts),
        "avg_parent_count": average(parent_counts),
    }


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO if not args.quiet else logging.WARNING,
        format="[%(levelname)s] %(message)s",
    )
    logger = logging.getLogger("perf_smoke_batch")

    steps = sorted({int(chunk.strip()) for chunk in args.steps.split(",") if chunk.strip()})
    if not steps:
        raise ValueError("No valid checkpoints provided via --steps")

    batch_size = max(1, args.batch_size)
    max_documents = max(steps)

    database_url = args.database_url or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_TEST_URL")

    if database_url:
        logger.info("Using database: %s", database_url)
        engine = create_engine(database_url)
    else:
        logger.info("Using database: sqlite://:memory:")
        engine = create_engine(sqlite_path=args.sqlite_path) if args.sqlite_path else create_engine()

    ensure_schema(engine, args.clear_db)
    session_factory = create_session_factory(engine)
    store = create_document_store(session_factory)
    renderer = MarkdownRenderer()

    document_path = args.document.resolve()
    document_text = document_path.read_text(encoding="utf-8")

    checkpoints: list[dict[str, Any]] = []
    document_ids: list[Any] = []
    blocks_per_document: int | None = None

    steps_iter = iter(steps)
    current_step = next(steps_iter)
    documents_ingested = 0
    batch_index = 0

    while documents_ingested < max_documents:
        remaining = max_documents - documents_ingested
        docs_this_batch = min(batch_size, remaining)
        batch_blocks: list[Any] = []
        batch_doc_ids: list[Any] = []
        parse_ms_total = 0.0

        for _ in range(docs_this_batch):
            parse_start = time.perf_counter()
            blocks = markdown_to_blocks(document_text)
            parse_ms_total += (time.perf_counter() - parse_start) * 1000

            doc_block = next((b for b in blocks if b.type is BlockType.DOCUMENT), None)
            if doc_block is None:
                raise RuntimeError("Document block not found in parsed content.")
            batch_doc_ids.append(doc_block.id)
            batch_blocks.extend(blocks)

            if blocks_per_document is None:
                blocks_per_document = len(blocks)

        ingest_start = time.perf_counter()
        store.upsert_blocks(batch_blocks)
        ingest_ms = (time.perf_counter() - ingest_start) * 1000

        document_ids.extend(batch_doc_ids)
        documents_ingested += docs_this_batch
        batch_index += 1

        should_log = (args.log_interval and batch_index % args.log_interval == 0) or args.log_every_batch
        if not args.quiet and should_log:
            total_blocks = (blocks_per_document or 0) * documents_ingested
            logger.info(
                "Batch %d | docs=%d (cumulative=%d) blocks=%d | parse=%.2fms/doc ingest=%.2fms",
                batch_index,
                docs_this_batch,
                documents_ingested,
                total_blocks,
                parse_ms_total / docs_this_batch,
                ingest_ms,
            )

        while current_step is not None and documents_ingested >= current_step:
            sample_size = min(args.sample_size, len(document_ids))
            sample_ids = document_ids[-sample_size:]
            metrics = measure_sample(store, renderer, sample_ids, "Onboarding")
            checkpoints.append(
                {
                    "documents": current_step,
                    "sample_size": sample_size,
                    **metrics,
                    "total_blocks": current_step * (blocks_per_document or 0),
                }
            )
            current_step = next(steps_iter, None)

    payload = {
        "document": str(document_path),
        "database": database_url or (f"sqlite://{args.sqlite_path}" if args.sqlite_path else "sqlite://:memory:"),
        "checkpoints": checkpoints,
        "steps": steps,
        "sample_size": args.sample_size,
        "batch_size": batch_size,
    }

    output = json.dumps(payload, indent=2)
    if args.output:
        args.output.write_text(output)
    else:
        default_path = CURRENT_DIR.parent / "telemetry.json"
        default_path.write_text(output)
        logger.info("Wrote telemetry to %s", default_path)
        print(output)


if __name__ == "__main__":
    main()
