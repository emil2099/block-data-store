"""Azure Document Intelligence parser entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import re
from pathlib import Path
from typing import IO, Any, Literal, Sequence
from uuid import UUID, uuid4

from block_data_store.models.block import Block, BlockType
from block_data_store.models.blocks import (
    GroupIndexBlock,
    GroupIndexProps,
    PageGroupBlock,
    PageGroupProps,
)

from .markdown_parser import markdown_to_blocks


@dataclass(slots=True)
class AzureDiConfig:
    """Runtime configuration for Azure DI calls and caching."""

    endpoint: str | None = None
    key: str | None = None
    model_id: str = "prebuilt-layout"
    content_format: str = "markdown"
    cache_dir: Path = Path(".cache") / "azure_di"

    def __post_init__(self) -> None:
        if self.endpoint is None:
            self.endpoint = os.getenv("AZURE_DI_ENDPOINT")
        if self.key is None:
            self.key = os.getenv("AZURE_DI_KEY")


def analyze_with_cache(
    source: str | Path | bytes | IO[bytes],
    *,
    config: AzureDiConfig | None = None,
    client: Any = None,
) -> dict[str, Any]:
    """Return a cached-or-fresh AnalyzeResult payload with only the needed fields."""

    cfg = config or AzureDiConfig()
    data, tag = _read_source_bytes(source)
    cache_key = _cache_key(data, cfg.model_id, cfg.content_format, tag)
    cache_path = cfg.cache_dir / f"{cache_key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    payload = _run_analyze_request(data, cfg, client)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def azure_di_to_blocks(
    source: str | Path | bytes | IO[bytes],
    *,
    grouping: Literal["canonical", "page"] = "canonical",
    create_page_groups: bool = True,
    workspace_id: UUID | None = None,
    document_id: UUID | None = None,
    timestamp: datetime | None = None,
    config: AzureDiConfig | None = None,
    client: Any = None,
    strip_marker_html: bool = True,
) -> list[Block]:
    """Parse source bytes via Azure DI and convert to Decipher blocks."""

    cfg = config or AzureDiConfig()
    payload = analyze_with_cache(source, config=cfg, client=client)

    ts = timestamp or datetime.now(timezone.utc)
    doc_id = document_id or uuid4()
    content = payload.get("content", "") or ""
    page_texts = _page_texts(payload)

    if grouping == "page" and not page_texts:
        grouping = "canonical"

    if grouping == "page":
        create_page_groups = True

    page_groups = _page_group_ids(len(page_texts), create_page_groups)

    if grouping == "page" and page_texts:
        blocks = _page_first_blocks(
            page_texts=page_texts,
            page_groups=page_groups,
            workspace_id=workspace_id,
            document_id=doc_id,
            timestamp=ts,
        )
    else:
        blocks = markdown_to_blocks(
            content,
            workspace_id=workspace_id,
            document_id=doc_id,
            timestamp=ts,
        )
        if page_groups:
            blocks = _tag_blocks_canonical(
                blocks,
                page_texts=page_texts,
                page_groups=page_groups,
                workspace_id=workspace_id,
                timestamp=ts,
            )

    if page_groups:
        blocks = _attach_page_group_blocks(blocks, page_groups)

    if strip_marker_html:
        blocks = _remove_marker_html_blocks(blocks)

    return _with_metadata(blocks, payload, grouping)


# ---- helpers -----------------------------------------------------------------


def _read_source_bytes(source: str | Path | bytes | IO[bytes]) -> tuple[bytes, str | None]:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source), None

    if isinstance(source, (str, Path)):
        path = Path(source)
        data = path.read_bytes()
        return data, str(path.resolve())

    if isinstance(source, io.BufferedReader):
        return source.read(), None

    if hasattr(source, "read"):
        data = source.read()
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("Expected bytes from stream")
        return bytes(data), None

    raise TypeError("Unsupported source type for Azure DI parser")


def _cache_key(
    data: bytes,
    model_id: str,
    content_format: str,
    tag: str | None,
) -> str:
    h = hashlib.sha256()
    h.update(data)
    h.update(model_id.encode("utf-8"))
    h.update(content_format.encode("utf-8"))
    if tag:
        h.update(tag.encode("utf-8"))
    return h.hexdigest()


def _run_analyze_request(
    data: bytes,
    config: AzureDiConfig,
    client: Any,
) -> dict[str, Any]:
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
        from azure.core.credentials import AzureKeyCredential
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("azure-ai-documentintelligence is required for this parser") from exc

    endpoint = config.endpoint
    key = config.key
    if not endpoint or not key:
        raise RuntimeError("Azure DI endpoint and key must be configured")

    di_client = client
    if di_client is None:
        credential = AzureKeyCredential(key)
        di_client = DocumentIntelligenceClient(endpoint=endpoint, credential=credential)

    poller = di_client.begin_analyze_document(
        model_id=config.model_id,
        body=AnalyzeDocumentRequest(bytes_source=data),
        output_content_format=config.content_format,
    )
    result = poller.result()
    return _result_payload(result)


def _result_payload(result: Any) -> dict[str, Any]:
    pages_payload: list[dict[str, Any]] = []
    for page in getattr(result, "pages", []) or []:
        spans_payload: list[dict[str, int]] = []
        for span in getattr(page, "spans", []) or []:
            offset = _get_attr(span, "offset", 0)
            length = _get_attr(span, "length", 0)
            spans_payload.append({"offset": int(offset), "length": int(length)})
        pages_payload.append({"spans": spans_payload})

    payload = {
        "content": getattr(result, "content", "") or "",
        "pages": pages_payload,
        "model_id": getattr(result, "model_id", None),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    return payload


def _get_attr(obj: Any, key: str, default: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _page_texts(payload: dict[str, Any]) -> list[str]:
    content: str = payload.get("content", "") or ""
    texts: list[str] = []
    for page in payload.get("pages", []) or []:
        spans = page.get("spans") or []
        if not spans:
            continue
        span = spans[0]
        offset = max(0, int(_get_attr(span, "offset", 0)))
        length = max(0, int(_get_attr(span, "length", 0)))
        if length <= 0:
            continue
        texts.append(content[offset : offset + length])
    return texts


def _page_group_ids(page_count: int, create_groups: bool) -> dict[int, UUID]:
    if not create_groups or page_count <= 0:
        return {}
    return {number: uuid4() for number in range(1, page_count + 1)}


def _page_first_blocks(
    *,
    page_texts: Sequence[str],
    page_groups: dict[int, UUID],
    workspace_id: UUID | None,
    document_id: UUID,
    timestamp: datetime,
) -> list[Block]:
    if not page_texts:
        return markdown_to_blocks(
            "",
            workspace_id=workspace_id,
            document_id=document_id,
            timestamp=timestamp,
        )

    document_block: Block | None = None
    children: list[UUID] = []
    collected: list[Block] = []

    for index, page_text in enumerate(page_texts, start=1):
        page_blocks = markdown_to_blocks(
            page_text,
            workspace_id=workspace_id,
            document_id=document_id,
            timestamp=timestamp,
        )
        page_document = page_blocks[0]
        if document_block is None:
            document_block = page_document

        page_children = [block.id for block in page_blocks[1:] if block.parent_id == document_id]
        children.extend(page_children)

        group_id = page_groups.get(index)
        for block in page_blocks[1:]:
            collected.append(_add_group(block, group_id))

    assert document_block is not None  # nosec - guarded by page_texts
    document_block = document_block.model_copy(update={"children_ids": tuple(children)})
    blocks = [document_block]
    blocks.extend(collected)
    return blocks


def _tag_blocks_canonical(
    blocks: Sequence[Block],
    *,
    page_texts: Sequence[str],
    page_groups: dict[int, UUID],
    workspace_id: UUID | None,
    timestamp: datetime,
) -> list[Block]:
    if not page_texts or not page_groups or not blocks:
        return list(blocks)

    updated = list(blocks)
    content_indices = [index for index, block in enumerate(updated) if _block_plain_text(block)]
    pointer = 0

    for page_number, page_text in enumerate(page_texts, start=1):
        group_id = page_groups.get(page_number)
        if group_id is None:
            continue
        snippet_blocks = markdown_to_blocks(
            page_text,
            workspace_id=workspace_id,
            document_id=uuid4(),
            timestamp=timestamp,
        )
        snippet_texts = [
            _normalise_text(text)
            for text in (_block_plain_text(block) for block in snippet_blocks)
            if text
        ]
        for snippet_text in snippet_texts:
            pointer = _assign_group_to_next_match(
                updated,
                content_indices,
                pointer,
                snippet_text,
                group_id,
            )

    return updated


def _assign_group_to_next_match(
    blocks: list[Block],
    content_indices: list[int],
    pointer: int,
    target_text: str,
    group_id: UUID,
) -> int:
    total = len(content_indices)
    normalised_target = _normalise_text(target_text)
    while pointer < total:
        block_index = content_indices[pointer]
        pointer += 1
        block = blocks[block_index]
        block_text = _block_plain_text(block)
        if block_text and _normalise_text(block_text) == normalised_target:
            blocks[block_index] = _add_group(block, group_id)
            break
    return pointer


def _attach_page_group_blocks(blocks: Sequence[Block], page_groups: dict[int, UUID]) -> list[Block]:
    if not page_groups or not blocks:
        return list(blocks)

    document = blocks[0]
    child_ids = list(document.children_ids)
    group_index_id = uuid4()
    child_ids.append(group_index_id)
    document = document.model_copy(update={"children_ids": tuple(child_ids)})

    sorted_pages = [number for number in sorted(page_groups)]
    group_children = tuple(page_groups[number] for number in sorted_pages)
    base_kwargs = {
        "root_id": document.root_id,
        "workspace_id": document.workspace_id,
        "created_time": document.created_time,
        "last_edited_time": document.last_edited_time,
        "created_by": document.created_by,
        "last_edited_by": document.last_edited_by,
        "version": 0,
        "in_trash": False,
        "metadata": {},
        "content": None,
    }

    group_index = GroupIndexBlock(
        id=group_index_id,
        parent_id=document.id,
        children_ids=group_children,
        properties=GroupIndexProps(group_index_type="page"),
        **base_kwargs,
    )

    page_blocks: list[PageGroupBlock] = []
    for number in sorted_pages:
        page_blocks.append(
            PageGroupBlock(
                id=page_groups[number],
                parent_id=group_index_id,
                children_ids=tuple(),
                properties=PageGroupProps(page_number=number),
                **base_kwargs,
            )
        )

    updated = [document]
    updated.extend(blocks[1:])
    updated.append(group_index)
    updated.extend(page_blocks)
    return updated


def _add_group(block: Block, group_id: UUID | None) -> Block:
    if group_id is None:
        return block
    props = block.properties
    if not hasattr(props, "groups"):
        return block
    current = list(getattr(props, "groups", []))
    if group_id in current:
        return block
    current.append(group_id)
    new_props = props.model_copy(update={"groups": current})
    return block.model_copy(update={"properties": new_props})


def _block_plain_text(block: Block) -> str | None:
    if block.content and block.content.plain_text:
        text = block.content.plain_text.strip()
        return text if text else None
    return None


def _normalise_text(text: str) -> str:
    return " ".join(text.split())


def _remove_marker_html_blocks(blocks: Sequence[Block]) -> list[Block]:
    pattern = re.compile(
        r"^\s*<!--\s*(PageBreak|PageNumber\s*=\s*\".*?\"|PageFooter\s*=\s*\".*?\")\s*-->\s*$"
    )
    ids_to_remove: set[UUID] = set()
    for block in blocks:
        if block.type is BlockType.HTML and block.content and block.content.plain_text:
            if pattern.match(block.content.plain_text.strip()):
                ids_to_remove.add(block.id)
    if not ids_to_remove:
        return list(blocks)

    updated: list[Block] = []
    for block in blocks:
        if block.id in ids_to_remove:
            continue
        if block.children_ids:
            children = tuple(child_id for child_id in block.children_ids if child_id not in ids_to_remove)
            if children != block.children_ids:
                block = block.model_copy(update={"children_ids": children})
        updated.append(block)
    return updated


def _with_metadata(blocks: Sequence[Block], payload: dict[str, Any], grouping: str) -> list[Block]:
    if not blocks:
        return list(blocks)
    document = blocks[0]
    metadata = dict(document.metadata)
    metadata.setdefault("source", payload.get("source_name") or "azure_di")
    metadata["grouping"] = grouping
    updated_document = document.model_copy(update={"metadata": metadata})
    updated = [updated_document]
    updated.extend(blocks[1:])
    return updated


__all__ = ["AzureDiConfig", "analyze_with_cache", "azure_di_to_blocks"]
