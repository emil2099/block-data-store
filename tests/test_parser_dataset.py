from __future__ import annotations

from pathlib import Path
from typing import Iterable
from uuid import UUID

import pytest

from block_data_store.models.block import Block, BlockType
from block_data_store.parser.dataset_parser import DatasetParserConfig, dataset_to_blocks
from block_data_store.renderers import MarkdownRenderer


_SAMPLE_CSV = Path("tests/fixtures/datasets/sample_dataset.csv")


@pytest.fixture(scope="module")
def sample_csv_path() -> Path:
    if not _SAMPLE_CSV.exists():
        pytest.skip("Dataset sample fixture missing")
    return _SAMPLE_CSV


def test_dataset_parser_creates_dataset_root(sample_csv_path: Path) -> None:
    blocks = dataset_to_blocks(sample_csv_path)
    dataset = _hydrate(blocks)

    assert dataset.type is BlockType.DATASET
    records = dataset.children()
    assert len(records) == 4
    assert all(record.type is BlockType.RECORD for record in records)
    assert any(record.content.data.get("location") is None for record in records)

    renderer = MarkdownRenderer()
    rendered = renderer.render(dataset)
    assert "| Name | Role | Location | Score |" in rendered
    assert rendered.count("|") > 10  # crude check for table rows


def test_dataset_parser_select_columns(sample_csv_path: Path) -> None:
    config = DatasetParserConfig(select_columns=["name", "score"])
    blocks = dataset_to_blocks(sample_csv_path, config=config)
    dataset = _hydrate(blocks)
    records = dataset.children()
    assert records
    for record in records:
        assert set(record.content.data.keys()) == {"name", "score"}


# ---------------------------------------------------------------------------
# Helpers


def _hydrate(blocks: list[Block]) -> Block:
    if not blocks:
        raise AssertionError("parser returned no blocks")

    by_id = {block.id: block for block in blocks}
    wired: dict[UUID, Block] = {}

    def resolve_one(block_id: UUID | None) -> Block | None:
        if block_id is None:
            return None
        return wired.get(block_id) or by_id.get(block_id)

    def resolve_many(block_ids: Iterable[UUID]) -> list[Block]:
        resolved: list[Block] = []
        for block_id in block_ids:
            block = resolve_one(block_id)
            if block is not None:
                resolved.append(block)
        return resolved

    for block_id, block in by_id.items():
        wired[block_id] = block.with_resolvers(
            resolve_one=resolve_one,
            resolve_many=resolve_many,
        )

    return wired[blocks[0].id]
