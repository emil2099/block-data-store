from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from block_data_store.models.block import BlockType
from block_data_store.parser.azure_di_parser import azure_di_to_blocks


_FIXTURE_PATH = Path("tests/fixtures/azure_di/sample_local_pdf.json")


@pytest.fixture(scope="module")
def azure_di_payload() -> dict:
    if not _FIXTURE_PATH.exists():
        pytest.skip("Azure DI fixture missing; run scripts/di_probe.py first")
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _patch_cached_result(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    def _fake_analyze(source: object, *, config=None, client=None):  # type: ignore[override]
        return payload

    monkeypatch.setattr("block_data_store.parser.azure_di_parser.analyze_with_cache", _fake_analyze)


def test_canonical_grouping_tags_blocks(monkeypatch: pytest.MonkeyPatch, azure_di_payload: dict) -> None:
    _patch_cached_result(monkeypatch, azure_di_payload)

    blocks = azure_di_to_blocks("unused", grouping="canonical")

    document = blocks[0]
    assert document.type is BlockType.DOCUMENT
    assert document.metadata.get("source") == "azure_di"
    assert document.metadata.get("di_pages") == len(azure_di_payload.get("pages", []))

    group_index = [block for block in blocks if block.type is BlockType.GROUP_INDEX]
    assert len(group_index) == 1

    page_groups = [block for block in blocks if block.type is BlockType.PAGE_GROUP]
    assert len(page_groups) == len(azure_di_payload.get("pages", []))

    tagged = [
        block
        for block in blocks
        if hasattr(block.properties, "groups") and getattr(block.properties, "groups")
    ]
    assert tagged, "Expected at least one block to receive page tags"


def test_page_grouping_tags_every_page(monkeypatch: pytest.MonkeyPatch, azure_di_payload: dict) -> None:
    _patch_cached_result(monkeypatch, azure_di_payload)

    blocks = azure_di_to_blocks("unused", grouping="page")

    page_groups = [block for block in blocks if block.type is BlockType.PAGE_GROUP]
    assert len(page_groups) == len(azure_di_payload.get("pages", []))

    def _group_ids(block) -> tuple[UUID, ...]:
        if hasattr(block.properties, "groups"):
            return tuple(getattr(block.properties, "groups"))
        return tuple()

    content_blocks = [block for block in blocks if block.type not in {BlockType.DOCUMENT, BlockType.GROUP_INDEX, BlockType.PAGE_GROUP}]
    assert content_blocks, "Expected parsed content blocks"
    assert all(_group_ids(block) for block in content_blocks), "Every block should have at least one page tag"


@pytest.mark.azure_di
def test_live_azure_di_smoke() -> None:
    pytest.importorskip("azure.ai.documentintelligence")

    if not os.getenv("AZURE_DI_ENDPOINT") or not os.getenv("AZURE_DI_KEY"):
        pytest.skip("Azure DI credentials not configured")

    sample_pdf = Path("data/sample-local-pdf.pdf")
    if not sample_pdf.exists():
        pytest.skip("Sample PDF missing")

    blocks = azure_di_to_blocks(sample_pdf, grouping="canonical")
    assert blocks

    group_index = [block for block in blocks if block.type is BlockType.GROUP_INDEX]
    assert group_index, "Group index should be present"
