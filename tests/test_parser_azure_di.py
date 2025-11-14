from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable
from uuid import UUID

import pytest

from block_data_store.models.block import Block, BlockType
from block_data_store.parser import markdown_to_blocks
from block_data_store.parser.azure_di_parser import azure_di_to_blocks
from block_data_store.renderers import MarkdownRenderer


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


def test_canonical_round_trip_matches_markdown(
    monkeypatch: pytest.MonkeyPatch,
    azure_di_payload: dict,
) -> None:
    _patch_cached_result(monkeypatch, azure_di_payload)

    blocks = azure_di_to_blocks("unused", grouping="canonical")
    document = _hydrate(blocks)

    renderer = MarkdownRenderer()
    rendered = renderer.render(document)

    assert _normalize(rendered) == _normalize(azure_di_payload.get("content", ""))

    expected_pages = len(azure_di_payload.get("pages", []) or [])
    assert sum(1 for block in blocks if block.type is BlockType.GROUP_INDEX) == (1 if expected_pages else 0)
    assert sum(1 for block in blocks if block.type is BlockType.PAGE_GROUP) == expected_pages


def test_canonical_page_tags_align_with_page_content(
    monkeypatch: pytest.MonkeyPatch,
    azure_di_payload: dict,
) -> None:
    _patch_cached_result(monkeypatch, azure_di_payload)

    blocks = azure_di_to_blocks("unused", grouping="canonical")
    document = _hydrate(blocks)

    page_texts = _page_texts_from_payload(azure_di_payload)
    if not page_texts:
        pytest.skip("Fixture has no page spans to validate")

    page_groups = [block for block in blocks if block.type is BlockType.PAGE_GROUP]
    assert page_groups, "Expected page groups to exist"

    lookup = {block.properties.page_number: block.id for block in page_groups}
    for page_number, page_text in enumerate(page_texts, start=1):
        page_id = lookup.get(page_number)
        assert page_id is not None, f"Missing page block for page {page_number}"

        expected_sequence = _block_plain_text_sequence(markdown_to_blocks(page_text)[1:])
        actual_sequence = _page_block_text_sequence(document, page_id)

        assert actual_sequence, f"No blocks tagged for page {page_number}"
        actual_norm = [entry for entry in _normalize_list(actual_sequence) if entry]
        expected_norm = [entry for entry in _normalize_list(expected_sequence) if entry]
        assert actual_norm == expected_norm


def test_page_first_assigns_page_tags(monkeypatch: pytest.MonkeyPatch, azure_di_payload: dict) -> None:
    _patch_cached_result(monkeypatch, azure_di_payload)

    blocks = azure_di_to_blocks("unused", grouping="page")
    page_groups = [block for block in blocks if block.type is BlockType.PAGE_GROUP]
    expected_pages = len(azure_di_payload.get("pages", []) or [])
    assert len(page_groups) == expected_pages

    content_blocks = [
        block
        for block in blocks
        if block.type not in {BlockType.DOCUMENT, BlockType.GROUP_INDEX, BlockType.PAGE_GROUP}
    ]
    assert content_blocks, "Expected content blocks"

    for block in content_blocks:
        groups = getattr(block.properties, "groups", [])
        assert groups, f"Content block {block.id} missing page tags in page-first mode"


@pytest.mark.azure_di
def test_live_azure_di_smoke() -> None:
    pytest.importorskip("azure.ai.documentintelligence")

    if not os.getenv("AZURE_DI_ENDPOINT") or not os.getenv("AZURE_DI_KEY"):
        pytest.skip("Azure DI credentials not configured")

    sample_pdf = Path("data/sample-local-pdf.pdf")
    if not sample_pdf.exists():
        pytest.skip("Sample PDF missing")

    blocks = azure_di_to_blocks(sample_pdf, grouping="canonical")
    document = _hydrate(blocks)
    renderer = MarkdownRenderer()
    rendered = renderer.render(document)

    assert rendered.strip(), "Rendered content should not be empty"


# ---------------------------------------------------------------------------
# Helpers


def _page_texts_from_payload(payload: dict) -> list[str]:
    content: str = payload.get("content", "") or ""
    texts: list[str] = []
    for page in payload.get("pages", []) or []:
        spans = page.get("spans") or []
        if not spans:
            continue
        span = spans[0]
        offset = max(0, int(span.get("offset", 0)))
        length = max(0, int(span.get("length", 0)))
        if length <= 0:
            continue
        texts.append(content[offset : offset + length])
    return texts


def _page_block_text_sequence(root: Block, page_id) -> list[str]:
    sequence: list[str] = []
    for block in _walk(root):
        groups = getattr(block.properties, "groups", None)
        if not groups or page_id not in groups:
            continue
        text = _block_plain_text(block)
        if text:
            sequence.append(text)
    return sequence


def _block_plain_text_sequence(blocks: Iterable[Block]) -> list[str]:
    sequence: list[str] = []
    for block in blocks:
        text = _block_plain_text(block)
        if text:
            sequence.append(text)
    return sequence


def _block_plain_text(block: Block) -> str | None:
    if block.content and block.content.plain_text:
        text = block.content.plain_text.strip()
        return text or None
    return None


def _walk(block: Block) -> Iterable[Block]:
    stack = [block]
    visited = set()
    while stack:
        current = stack.pop()
        if current.id in visited:
            continue
        visited.add(current.id)
        yield current
        children = current.children()
        for child in reversed(children):
            stack.append(child)


def _normalize(text: str) -> str:
    text = _strip_di_markers(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _normalize_list(values: Iterable[str]) -> list[str]:
    return [_normalize(value) for value in values]


_DI_MARKER_RE = re.compile(
    r"^\s*<!--\s*(PageBreak|PageNumber\s*=\s*\".*?\"|PageFooter\s*=\s*\".*?\")\s*-->\s*$",
    re.MULTILINE,
)


def _strip_di_markers(text: str) -> str:
    return re.sub(_DI_MARKER_RE, "", text)


def _hydrate(blocks: list[Block]) -> Block:
    if not blocks:
        raise AssertionError("Parser returned no blocks")

    by_id = {block.id: block for block in blocks}
    wired: dict[UUID, Block] = {}

    def resolve_one(block_id: UUID | None):
        if block_id is None:
            return None
        return wired.get(block_id) or by_id.get(block_id)

    def resolve_many(block_ids: Iterable[UUID]):
        resolved = []
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
