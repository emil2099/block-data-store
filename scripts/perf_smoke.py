"""Cumulative corpus performance smoke test for the Block Data Store POC.

The script ingests the same Markdown document repeatedly, keeps every copy in
the database, and records per-document timings (fetch, render, targeted filters)
at configurable iteration checkpoints. This aligns with the POC risk: "does the
system remain responsive as the corpus grows?"
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

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    parser = argparse.ArgumentParser(description="Cumulative corpus performance smoke test")
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
        help="Comma-separated iteration checkpoints (e.g. 1,10,100,1000).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=10,
        help="Number of documents to sample when calculating averages (default 10).",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Optional SQLAlchemy URL (e.g. Postgres). Defaults to in-memory SQLite.",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=None,
        help="Optional SQLite file path (ignored if --database-url is provided).",
    )
    parser.add_argument(
        "--reset-schema",
        action="store_true",
        help="Drop and recreate tables before starting (useful for persisted DBs).",
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
        default=50,
        help="Log progress every N iterations (default 50).",
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


def measure_sample(
    store,
    renderer: MarkdownRenderer,
    document_ids: list[Any],
    heading_hint: str,
) -> dict[str, float]:
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
        paragraphs = store.query_blocks(
            where=WhereClause(type=BlockType.PARAGRAPH, root_id=str(doc_id))
        )
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
    logger = logging.getLogger("perf_smoke")

    steps = sorted({int(chunk.strip()) for chunk in args.steps.split(",") if chunk.strip()})
    if not steps:
        raise ValueError("No valid checkpoints provided via --steps")
    max_iterations = max(steps)

    if args.database_url:
        engine = create_engine(args.database_url)
    else:
        engine = create_engine(sqlite_path=args.sqlite_path) if args.sqlite_path else create_engine()

    ensure_schema(engine, args.reset_schema)
    session_factory = create_session_factory(engine)
    store = create_document_store(session_factory)
    renderer = MarkdownRenderer()

    document_path = args.document.resolve()
    document_text = document_path.read_text(encoding="utf-8")

    checkpoints: list[dict[str, Any]] = []
    document_ids: list[Any] = []
    blocks_per_document = None

    for iteration in range(1, max_iterations + 1):
        parse_start = time.perf_counter()
        blocks = markdown_to_blocks(document_text)
        parse_ms = (time.perf_counter() - parse_start) * 1000

        ingest_start = time.perf_counter()
        store.upsert_blocks(blocks)
        ingest_ms = (time.perf_counter() - ingest_start) * 1000

        document_block = next((b for b in blocks if b.type is BlockType.DOCUMENT), None)
        if document_block is None:
            raise RuntimeError("Document block not found in parsed content.")
        document_ids.append(document_block.id)

        if blocks_per_document is None:
            blocks_per_document = len(blocks)

        if not args.quiet and args.log_interval and iteration % args.log_interval == 0:
            logger.info("Iter %d | parse=%.3fms ingest=%.3fms", iteration, parse_ms, ingest_ms)

        if iteration in steps:
            sample_size = min(args.sample_size, len(document_ids))
            sample_ids = document_ids[-sample_size:]
            metrics = measure_sample(store, renderer, sample_ids, "Onboarding")

            checkpoints.append(
                {
                    "documents": iteration,
                    "sample_size": sample_size,
                    **metrics,
                    "total_blocks": iteration * (blocks_per_document or 0),
                }
            )

    payload = {
        "document": str(document_path),
        "database": args.database_url or (f"sqlite://{args.sqlite_path}" if args.sqlite_path else "sqlite://:memory:"),
        "checkpoints": checkpoints,
        "steps": steps,
        "sample_size": args.sample_size,
    }

    output = json.dumps(payload, indent=2)
    if args.output:
        args.output.write_text(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
