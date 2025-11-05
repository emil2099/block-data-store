"""Performance smoke test for the Block Data Store POC.

Runs repeated ingestion, query, and render cycles against one or more markdown
samples and emits JSON telemetry. Supports both in-memory SQLite (default) and
external databases via SQLAlchemy connection URLs.
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

from sqlalchemy import delete

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
    parser = argparse.ArgumentParser(description="Block Data Store performance smoke test")
    parser.add_argument(
        "--document",
        type=Path,
        default=Path("data/poc_long_showcase.md"),
        help="Path to the markdown document to ingest each iteration.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of ingest/query/render iterations to execute.",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Optional SQLAlchemy database URL (e.g. Postgres). Defaults to in-memory SQLite.",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=None,
        help="Optional SQLite file path. Ignored when --database-url is provided.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output file. Defaults to stdout.",
    )
    parser.add_argument(
        "--reset-schema",
        action="store_true",
        help="Drop and recreate tables before the test starts (useful for persistent DBs).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-iteration logs; emit only JSON telemetry.",
    )
    parser.add_argument(
        "--log-interval",
        type=int,
        default=1,
        help="Log every N iterations (default 1). Ignored when --quiet is set.",
    )
    return parser.parse_args()


def cleanup_blocks(store) -> None:
    """Remove all rows from the blocks table to keep iteration state isolated."""

    session_factory = store._repository._session_factory  # type: ignore[attr-defined]
    with session_factory() as session:
        session.execute(delete(DbBlock))
        session.commit()


def run_iterations(
    document_path: Path,
    iterations: int,
    *,
    database_url: str | None,
    sqlite_path: Path | None,
    reset_schema: bool,
    logger: logging.Logger,
    log_interval: int,
) -> dict[str, Any]:
    if database_url:
        engine = create_engine(database_url)
    else:
        engine = create_engine(sqlite_path=sqlite_path) if sqlite_path else create_engine()

    if reset_schema:
        DbBlock.__table__.drop(engine, checkfirst=True)

    create_all(engine)
    session_factory = create_session_factory(engine)
    store = create_document_store(session_factory)
    renderer = MarkdownRenderer(resolve_reference=lambda ref: store.get_block(ref, depth=1) if ref else None)

    iteration_times: list[float] = []
    parse_times: list[float] = []
    ingest_times: list[float] = []
    query_paragraph_times: list[float] = []
    query_parent_times: list[float] = []
    render_document_times: list[float] = []
    render_block_times: list[float] = []
    cleanup_times: list[float] = []

    block_counts: list[int] = []
    paragraph_counts: list[int] = []
    heading_paragraph_counts: list[int] = []
    render_lengths: list[int] = []

    document_path = document_path.resolve()
    if not document_path.exists():
        raise FileNotFoundError(f"Document not found: {document_path}")

    document_text = document_path.read_text(encoding="utf-8")

    for index in range(iterations):
        start = time.perf_counter()

        parse_start = time.perf_counter()
        blocks = markdown_to_blocks(document_text)
        parse_elapsed = time.perf_counter() - parse_start
        parse_times.append(parse_elapsed)

        ingest_start = time.perf_counter()
        store.save_blocks(blocks)
        ingest_elapsed = time.perf_counter() - ingest_start
        ingest_times.append(ingest_elapsed)

        document_block = next((b for b in blocks if b.type is BlockType.DOCUMENT), None)
        if document_block is None:
            raise RuntimeError("Document block not found in parsed content.")

        query_paragraph_start = time.perf_counter()
        paragraphs = store.query_blocks(
            where=WhereClause(type=BlockType.PARAGRAPH, root_id=str(document_block.id))
        )
        query_paragraph_times.append(time.perf_counter() - query_paragraph_start)

        query_parent_start = time.perf_counter()
        onboarding_paragraphs = store.query_blocks(
            where=WhereClause(type=BlockType.PARAGRAPH),
            parent=ParentFilter(
                where=WhereClause(type=BlockType.HEADING),
                property_filter=PropertyFilter(
                    path="content.text",
                    value="Onboarding",
                    operator=FilterOperator.CONTAINS,
                ),
            ),
        )
        query_parent_times.append(time.perf_counter() - query_parent_start)

        render_document_start = time.perf_counter()
        rendered_document = renderer.render(
            store.get_root_tree(document_block.id, depth=None),
            options=RenderOptions(),
        )
        render_document_times.append(time.perf_counter() - render_document_start)

        render_block_elapsed = 0.0
        if paragraphs:
            render_block_start = time.perf_counter()
            renderer.render(paragraphs[0], options=RenderOptions())
            render_block_elapsed = time.perf_counter() - render_block_start
        render_block_times.append(render_block_elapsed)
        render_lengths.append(len(rendered_document))

        elapsed = time.perf_counter() - start
        iteration_times.append(elapsed)
        block_counts.append(len(blocks))
        paragraph_counts.append(len(paragraphs))
        heading_paragraph_counts.append(len(onboarding_paragraphs))
        cleanup_start = time.perf_counter()
        cleanup_blocks(store)
        cleanup_times.append(time.perf_counter() - cleanup_start)

        if log_interval > 0 and ((index + 1) % log_interval == 0 or index == 0 or index + 1 == iterations):
            logger.info(
                "Iteration %d/%d | parse=%.3fms ingest=%.3fms query_paragraphs=%.3fms query_parent=%.3fms render_document=%.3fms render_block=%.3fms",
                index + 1,
                iterations,
                parse_elapsed * 1000,
                ingest_elapsed * 1000,
                query_paragraph_times[-1] * 1000,
                query_parent_times[-1] * 1000,
                render_document_times[-1] * 1000,
                render_block_elapsed * 1000,
            )

    total_seconds = sum(iteration_times)

    def summarise(values: list[float]) -> dict[str, float]:
        return {
            "total_seconds": sum(values),
            "avg_seconds": statistics.mean(values) if values else 0.0,
            "min_seconds": min(values) if values else 0.0,
            "max_seconds": max(values) if values else 0.0,
        }

    telemetry = {
        "document": str(document_path),
        "iterations": iterations,
        "database_url": database_url or (f"sqlite://{sqlite_path}" if sqlite_path else "sqlite://:memory:"),
        "durations": {
            "parse": summarise(parse_times),
            "ingest": summarise(ingest_times),
            "query_paragraphs": summarise(query_paragraph_times),
            "query_parent": summarise(query_parent_times),
            "render_document": summarise(render_document_times),
            "render_block": summarise(render_block_times),
            "cleanup": summarise(cleanup_times),
            "iteration_total": summarise(iteration_times),
        },
        "counts": {
            "avg_blocks": statistics.mean(block_counts) if block_counts else 0,
            "avg_paragraphs": statistics.mean(paragraph_counts) if paragraph_counts else 0,
            "avg_onboarding_paragraphs": statistics.mean(heading_paragraph_counts) if heading_paragraph_counts else 0,
            "avg_render_length": statistics.mean(render_lengths) if render_lengths else 0,
        },
    }

    return telemetry


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO if not args.quiet else logging.WARNING,
        format="[%(levelname)s] %(message)s",
    )
    logger = logging.getLogger("perf_smoke")

    telemetry = run_iterations(
        args.document,
        args.iterations,
        database_url=args.database_url,
        sqlite_path=args.sqlite_path,
        reset_schema=args.reset_schema,
        logger=logger,
        log_interval=0 if args.quiet else max(1, args.log_interval),
    )

    output = json.dumps(telemetry, indent=2)
    if args.output:
        args.output.write_text(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
