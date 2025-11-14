"""NiceGUI showcase app for the Block Data Store POC.

This page acts as a guided tour of the end-to-end architecture, highlighting
how Markdown content flows through the parser, repository, DocumentStore,
and renderer layers. Each UI section is paired with brief documentation so
visitors can understand what is happening behind the scenes.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Callable, Iterable
from uuid import UUID

from nicegui import events, ui

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from block_data_store.db.engine import create_engine, create_session_factory
from block_data_store.db.schema import create_all
from block_data_store.models.block import Block, BlockType, Content
from block_data_store.parser import load_markdown_path, markdown_to_blocks
from block_data_store.parser.azure_di_parser import azure_di_to_blocks
from block_data_store.parser.dataset_parser import dataset_to_blocks
from block_data_store.renderers.base import RenderOptions
from block_data_store.renderers.markdown import MarkdownRenderer
from block_data_store.repositories.filters import (
    FilterOperator,
    ParentFilter,
    PropertyFilter,
    RootFilter,
    WhereClause,
)
from block_data_store.store import DocumentStore, create_document_store

DB_PATH = Path(__file__).resolve().parent / "nicegui_demo.db"
SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# Documentation helpers

OVERVIEW_TEXT = """
### 🧭 Overview — End-to-End Flow

1. **Markdown ingestion** via `parser.load_markdown_path`.
2. **Typed blocks** persisted through the SQLAlchemy repository.
3. **DocumentStore** orchestrates canonical + secondary trees.
4. **Renderers** present blocks for UI / AI surfaces.

This demo seeds sample Markdown files into SQLite on first launch and lets you
explore the canonical tree, issue repository-grade filters, inspect/update
blocks, and preview renderer output.
"""

OVERVIEW_CODE = """
from pathlib import Path
from block_data_store.db.engine import create_engine, create_session_factory
from block_data_store.db.schema import create_all
from block_data_store.parser import load_markdown_path
from block_data_store.store import create_document_store

sqlite_path = Path("nicegui_demo.db")
engine = create_engine(sqlite_path=sqlite_path)
create_all(engine)
store = create_document_store(create_session_factory(engine))

blocks = load_markdown_path("data/sample.md")
store.save_blocks(blocks)
"""

FILTERS_TEXT = """
**How filtering works**

- Uses `DocumentStore.query_blocks`, which wraps repository `WhereClause`,
  `ParentFilter`, and `RootFilter` support.
- Block filters target the selected document by default (root scoping).
- Parent and root filters mirror the same JSON path operators, so you can
  express queries like “paragraphs whose parent heading title contains _Risk_
  inside documents titled _Controls Handbook_”.
"""

FILTERS_CODE = """
from block_data_store.repositories.filters import (
    WhereClause, ParentFilter, RootFilter, PropertyFilter
)

blocks = store.query_blocks(
    where=WhereClause(type=BlockType.PARAGRAPH),
    parent=ParentFilter(
        property_filter=PropertyFilter(path="properties.title", value="Risk")
    ),
    root=RootFilter(
        property_filter=PropertyFilter(path="properties.title", value="Controls Handbook")
    ),
)
"""

INSPECTOR_TEXT = """
**Inspector (DocumentStore + Pydantic models)**

- Block metadata is shown as Markdown for quick scanning.
- Editable JSON panes let you tweak `properties`, `metadata`, and `content`.
- Saving issues an upsert through `DocumentStore.save_blocks`, bumping the
  version and timestamps.
"""

INSPECTOR_CODE = """
updated_block = block.model_copy(update={"properties": new_props})
store.save_blocks([updated_block])
"""

PREVIEW_TEXT = """
**Renderer preview (block-level)**

- Uses the Markdown renderer with optional metadata output.
- The focused block preview respects the recursive toggle, so you can inspect a
  single node or its full subtree.
"""

PREVIEW_CODE = """
from block_data_store.renderers.markdown import MarkdownRenderer

renderer = MarkdownRenderer()
markdown = renderer.render(block, options=RenderOptions(recursive=True))
"""

DOCUMENT_PREVIEW_TEXT = """
**Document snapshot**

- Shows renderer output for the selected document.
- Updates whenever you pick a different document on the sidebar.
"""

DOCUMENT_PREVIEW_CODE = """
document = store.get_root_tree(document_id, depth=None)
renderer.render(document, options=RenderOptions())
"""

SIDEBAR_HELP_MD = """
**Canonical tree**

- Pick a document to load its canonical hierarchy.
- Tree selection drives the inspector and preview panes.
- The IDs shown in the inspector line up with repository queries.
"""


# ---------------------------------------------------------------------------
# Application state


@dataclass
class AppState:
    store: DocumentStore
    renderer: MarkdownRenderer
    show_trashed: bool = False
    documents: list[Block] = field(default_factory=list)
    documents_by_id: dict[str, Block] = field(default_factory=dict)
    document_label_to_id: dict[str, str] = field(default_factory=dict)
    selected_document_id: str | None = None
    selected_block_id: str | None = None
    block_cache: dict[str, Block] = field(default_factory=dict)
    filter_results: list[Block] = field(default_factory=list)
    filter_summary: str = ""

    # UI handles -----------------------------------------------------------
    document_select: Any | None = None
    tree_component: Any | None = None
    filter_results_container: Any | None = None
    details_markdown: Any | None = None
    properties_area: Any | None = None
    metadata_area: Any | None = None
    data_area: Any | None = None
    markdown_view: Any | None = None
    document_markdown_view: Any | None = None
    include_metadata_checkbox: Any | None = None
    include_children_checkbox: Any | None = None
    render_block_children: bool = True


# ---------------------------------------------------------------------------
# Utility helpers


def _document_label(block: Block) -> str:
    title = getattr(block.properties, "title", None)
    prefix = "Dataset" if block.type is BlockType.DATASET else "Document"
    base = title or f"{prefix} {block.id}"
    if getattr(block, "in_trash", False):
        base += " (trashed)"
    return base


def _block_label(block: Block) -> str:
    if block.type is BlockType.DOCUMENT:
        title = getattr(block.properties, "title", None)
        if title:
            return f"{block.type.value}: {title}"

    if block.content:
        if block.content.plain_text:
            summary = block.content.plain_text.strip().splitlines()[0][:40]
            if summary:
                return f"{block.type.value}: {summary}"
        data = block.content.data
        if isinstance(data, dict) and data:
            key, value = next(iter(data.items()))
            return f"{block.type.value}: {key}={value}"
    label = f"{block.type.value}: {block.id}"
    if getattr(block, "in_trash", False):
        label += " (trashed)"
    return label


def _attach_source_metadata(blocks: list[Block], source_name: str | None) -> list[Block]:
    if not blocks or not source_name:
        return blocks
    root = blocks[0]
    metadata = dict(root.metadata)
    metadata["source"] = source_name
    blocks[0] = root.model_copy(update={"metadata": metadata})
    return blocks


def _short_id(value: UUID | str | None) -> str:
    if value is None:
        return "?"
    return str(value)[:8]


def _resolve_block(state: AppState, block_id: str | None) -> Block | None:
    if not block_id:
        return None
    cached = state.block_cache.get(block_id)
    if cached is not None:
        return cached
    try:
        fetched = state.store.get_block(UUID(block_id), depth=1, include_trashed=state.show_trashed)
    except Exception:
        return None
    if fetched is not None:
        state.block_cache[block_id] = fetched
    return fetched


def _set_filter_results(state: AppState, blocks: Iterable[Block], summary: str) -> None:
    state.filter_results = list(blocks)
    state.filter_summary = summary
    _render_filter_results(state)


def _build_property_filter_from_inputs(
    path_value: str | None,
    operator_value: str | None,
    raw_value: str | None,
) -> PropertyFilter | None:
    path = (path_value or "").strip()
    value_text = (raw_value or "").strip()
    if not path or not value_text:
        return None

    operator = FilterOperator.CONTAINS if operator_value == "contains" else FilterOperator.EQUALS

    coerced_value: Any = value_text
    try:
        coerced_value = json.loads(value_text)
    except Exception:
        lowered = value_text.lower()
        if lowered == "true":
            coerced_value = True
        elif lowered == "false":
            coerced_value = False

    try:
        return PropertyFilter(path=path, value=coerced_value, operator=operator)
    except Exception as exc:  # pragma: no cover - user-facing validation
        raise ValueError(f"Invalid filter definition for '{path}': {exc}") from exc


# ---------------------------------------------------------------------------
# State bootstrapping


def _bootstrap_state() -> AppState:
    engine = create_engine(sqlite_path=DB_PATH)
    create_all(engine)
    session_factory = create_session_factory(engine)
    store = create_document_store(session_factory)
    renderer = MarkdownRenderer()
    state = AppState(store=store, renderer=renderer)
    _seed_documents(state)
    return state


def _seed_documents(state: AppState) -> None:
    if state.store.list_documents():
        return
    for path in sorted(SAMPLE_DATA_DIR.glob("*.md")):
        blocks = load_markdown_path(path)
        blocks = _attach_source_metadata(blocks, path.name)
        state.store.save_blocks(blocks)


# ---------------------------------------------------------------------------
# Tree and selection handling


def _build_tree(cache: dict[str, Block], block: Block) -> dict[str, Any]:
    block_id = str(block.id)
    cache[block_id] = block
    children = [_build_tree(cache, child) for child in block.children()]
    return {"id": block_id, "label": _block_label(block), "children": children}


def _set_tree_nodes(tree_element: Any | None, nodes: list[dict[str, Any]]) -> None:
    if tree_element is None:
        return
    tree_element._props["nodes"] = nodes
    tree_element.update()
    tree_element.expand()


def _render_block(state: AppState, block: Block) -> None:
    if state.markdown_view is None:
        return
    include_metadata = bool(state.include_metadata_checkbox.value) if state.include_metadata_checkbox else False
    recursive = state.render_block_children
    options = RenderOptions(
        include_metadata=include_metadata,
        recursive=recursive,
    )
    rendered = state.renderer.render(block, options=options)
    state.markdown_view.set_content(rendered or "_(empty block)_")


def _render_document_markdown(state: AppState, document_block: Block | None = None) -> None:
    if state.document_markdown_view is None:
        return

    include_metadata = bool(state.include_metadata_checkbox.value) if state.include_metadata_checkbox else False
    options = RenderOptions(include_metadata=include_metadata)

    if document_block is None:
        document_id = state.selected_document_id
        if not document_id:
            state.document_markdown_view.set_content("_(select a document)_")
            return
        document_block = state.documents_by_id.get(document_id) or state.block_cache.get(document_id)
        if document_block is None:
            try:
                document_block = state.store.get_root_tree(UUID(document_id), depth=None)
            except Exception:
                document_block = None
    if document_block is None:
        state.document_markdown_view.set_content("_(document unavailable)_")
        return

    rendered = state.renderer.render(document_block, options=options)
    state.document_markdown_view.set_content(rendered or "_(empty document)_")


def _format_block_details(block: Block) -> str:
    lines = [
        f"### {_block_label(block)}",
        "",
        f"- **Type**: `{block.type.value}`",
        f"- **ID**: `{block.id}`",
        f"- **Parent**: `{block.parent_id}`",
        f"- **Root**: `{block.root_id}`",
        f"- **Version**: `{block.version}`",
        f"- **Created**: `{block.created_time.isoformat()}`",
        f"- **Last Edited**: `{block.last_edited_time.isoformat()}`",
    ]
    if block.metadata:
        lines.append(f"- **Metadata keys**: {', '.join(sorted(block.metadata.keys()))}")
    return "\n".join(lines)


def _select_block(state: AppState, block_id: str) -> None:
    block = _resolve_block(state, block_id)
    if block is None:
        return

    state.selected_block_id = block_id

    if state.details_markdown:
        state.details_markdown.set_content(_format_block_details(block))
    if state.properties_area:
        state.properties_area.value = json.dumps(block.properties.model_dump(), indent=2)
    if state.metadata_area:
        state.metadata_area.value = json.dumps(block.metadata, indent=2)
    if state.data_area:
        content_payload = block.content.model_dump() if block.content else {}
        state.data_area.value = json.dumps(content_payload, indent=2)

    _render_block(state, block)


def _handle_tree_select(state: AppState, event: events.ValueChangeEventArguments) -> None:
    selected = getattr(event, "value", None)
    block_id: str | None = None

    if isinstance(selected, dict):
        block_id = selected.get("key") or selected.get("id")
    elif isinstance(selected, list) and selected:
        first = selected[0]
        if isinstance(first, dict):
            block_id = first.get("key") or first.get("id")
        elif first is not None:
            block_id = str(first)
    elif selected is not None:
        block_id = str(selected)

    if not block_id:
        return

    block_id = block_id.strip()
    try:
        UUID(block_id)
    except ValueError:
        return

    _select_block(state, block_id)


def _load_document(state: AppState, document_id: str | None) -> None:
    doc_value = (document_id or "").strip() if isinstance(document_id, str) else None
    if doc_value:
        try:
            UUID(doc_value)
        except ValueError:
            ui.notify("Could not parse document identifier.", color="negative")
            doc_value = None

    state.selected_document_id = doc_value
    state.selected_block_id = None
    state.block_cache = {}

    if not doc_value or state.tree_component is None:
        _set_tree_nodes(state.tree_component, [])
        if state.details_markdown:
            state.details_markdown.set_content("Select a block to inspect.")
        _render_document_markdown(state, None)
        state.filter_results = []
        state.filter_summary = ""
        if state.filter_results_container:
            state.filter_results_container.clear()
        return

    root_uuid = UUID(doc_value)
    root_block = state.store.get_root_tree(root_uuid, depth=None, include_trashed=state.show_trashed)
    state.block_cache[str(root_block.id)] = root_block
    state.documents_by_id[str(root_block.id)] = root_block
    tree_payload = [_build_tree(state.block_cache, root_block)]
    _set_tree_nodes(state.tree_component, tree_payload)
    _render_document_markdown(state, root_block)

    if state.details_markdown:
        state.details_markdown.set_content("Select a block to inspect.")
    if state.markdown_view:
        state.markdown_view.set_content("_(select a block)_")
    if state.data_area:
        state.data_area.value = "{}"
    state.filter_results = []
    state.filter_summary = ""
    if state.filter_results_container:
        state.filter_results_container.clear()


def _refresh_documents(state: AppState, selected: str | None = None) -> None:
    documents = state.store.list_documents()
    dataset_roots = [
        block
        for block in state.store.query_blocks(where=WhereClause(type=BlockType.DATASET))
        if block.parent_id is None
    ]
    state.documents = documents + dataset_roots
    state.documents_by_id = {str(doc.id): doc for doc in state.documents}
    state.document_label_to_id = {
        _document_label(doc): str(doc.id) for doc in state.documents
    }

    labels = list(state.document_label_to_id.keys())
    if state.document_select:
        state.document_select.options = labels
        state.document_select.update()

    target_id = selected or state.selected_document_id
    if target_id not in state.documents_by_id:
        target_id = None
    if target_id is None and state.document_label_to_id:
        target_id = next(iter(state.document_label_to_id.values()))

    if state.document_select and target_id:
        target_label = next(
            (label for label, doc_id in state.document_label_to_id.items() if doc_id == target_id),
            None,
        )
        if target_label and state.document_select.value != target_label:
            state.document_select.value = target_label
            state.document_select.update()

    _load_document(state, target_id)


# ---------------------------------------------------------------------------
# Filtering


def _render_filter_results(state: AppState) -> None:
    container = state.filter_results_container
    if container is None:
        return
    container.clear()
    with container:
        summary = state.filter_summary.strip()
        count = len(state.filter_results)
        if summary:
            noun = "result" if count == 1 else "results"
            ui.label(f"{summary} — {count} {noun}").classes("text-xs text-slate-500")
        if not state.filter_results:
            ui.label("No blocks matched.").classes("text-sm text-slate-500")
            return
        for block in state.filter_results:
            ui.button(
                f"{block.type.value} — {_block_label(block)}",
                on_click=lambda _, b=block: _focus_filtered_block(state, b),
            ).props("flat dense")


def _focus_filtered_block(state: AppState, block: Block) -> None:
    root_id = str(block.root_id)
    state.selected_block_id = str(block.id)
    _load_document(state, root_id)
    _select_block(state, str(block.id))


def _apply_filter(
    state: AppState,
    block_type_value: str,
    path_value: str,
    operator_value: str,
    filter_value: str,
    parent_type_value: str,
    parent_path_value: str,
    parent_operator_value: str,
    parent_filter_value: str,
    root_type_value: str,
    root_path_value: str,
    root_operator_value: str,
    root_filter_value: str,
) -> None:
    where_kwargs: dict[str, Any] = {}
    if state.selected_document_id:
        where_kwargs["root_id"] = state.selected_document_id
    if block_type_value and block_type_value != "all":
        where_kwargs["type"] = BlockType(block_type_value)
    where_clause = WhereClause(**where_kwargs) if where_kwargs else None

    try:
        property_filter = _build_property_filter_from_inputs(path_value, operator_value, filter_value)
    except ValueError as exc:
        ui.notify(str(exc), color="negative")
        return

    try:
        parent_property_filter = _build_property_filter_from_inputs(
            parent_path_value,
            parent_operator_value,
            parent_filter_value,
        )
    except ValueError as exc:
        ui.notify(str(exc), color="negative")
        return

    try:
        root_property_filter = _build_property_filter_from_inputs(
            root_path_value,
            root_operator_value,
            root_filter_value,
        )
    except ValueError as exc:
        ui.notify(str(exc), color="negative")
        return

    parent_where_kwargs: dict[str, Any] = {}
    if parent_type_value and parent_type_value != "all":
        parent_where_kwargs["type"] = BlockType(parent_type_value)
    parent_filter = None
    if parent_where_kwargs or parent_property_filter is not None:
        parent_filter = ParentFilter(
            where=WhereClause(**parent_where_kwargs) if parent_where_kwargs else None,
            property_filter=parent_property_filter,
        )

    root_where_kwargs: dict[str, Any] = {}
    if root_type_value and root_type_value != "all":
        root_where_kwargs["type"] = BlockType(root_type_value)
    root_filter = None
    if root_where_kwargs or root_property_filter is not None:
        root_filter = RootFilter(
            where=WhereClause(**root_where_kwargs) if root_where_kwargs else None,
            property_filter=root_property_filter,
        )

    results = state.store.query_blocks(
        where=where_clause,
        property_filter=property_filter,
        parent=parent_filter,
        root=root_filter,
        limit=50,
    )

    summary_bits: list[str] = []
    if block_type_value and block_type_value != "all":
        summary_bits.append(f"type = {block_type_value}")
    if property_filter is not None:
        summary_bits.append(f"{property_filter.path} {operator_value} {filter_value}")
    if state.selected_document_id and (not where_clause or where_clause.root_id):
        summary_bits.append(f"root {_short_id(state.selected_document_id)}")
    if parent_filter is not None:
        parent_bits: list[str] = []
        if parent_filter.where and parent_filter.where.type:
            parent_type = (
                parent_filter.where.type.value
                if isinstance(parent_filter.where.type, BlockType)
                else str(parent_filter.where.type)
            )
            parent_bits.append(f"type = {parent_type}")
        if parent_property_filter is not None:
            parent_bits.append(
                f"{parent_property_filter.path} {parent_operator_value} {parent_filter_value}"
            )
        if parent_bits:
            summary_bits.append(f"parent({'; '.join(parent_bits)})")
    if root_filter is not None:
        root_bits: list[str] = []
        if root_filter.where and root_filter.where.type:
            root_type = (
                root_filter.where.type.value
                if isinstance(root_filter.where.type, BlockType)
                else str(root_filter.where.type)
            )
            root_bits.append(f"type = {root_type}")
        if root_property_filter is not None:
            root_bits.append(
                f"{root_property_filter.path} {root_operator_value} {root_filter_value}"
            )
        if root_bits:
            summary_bits.append(f"root({'; '.join(root_bits)})")

    summary_text = "; ".join(summary_bits) if summary_bits else "Repository filter"
    _set_filter_results(state, results, summary_text)


# ---------------------------------------------------------------------------
# Block editing


def _save_block_changes(state: AppState) -> None:
    if not state.selected_block_id:
        ui.notify("Select a block before saving.", color="warning")
        return

    block = _resolve_block(state, state.selected_block_id)
    if block is None:
        ui.notify("Selected block could not be resolved.", color="negative")
        return

    try:
        properties_payload = json.loads(state.properties_area.value or "{}") if state.properties_area else {}
        metadata_payload = json.loads(state.metadata_area.value or "{}") if state.metadata_area else {}
        content_payload = json.loads(state.data_area.value or "{}") if state.data_area else {}
    except json.JSONDecodeError as exc:
        ui.notify(f"Invalid JSON payload: {exc}", color="negative")
        return

    if not isinstance(metadata_payload, dict):
        ui.notify("Metadata payload must be a JSON object.", color="negative")
        return
    if not isinstance(content_payload, dict):
        ui.notify("Content payload must be a JSON object.", color="negative")
        return

    try:
        new_properties = block.properties.__class__(**properties_payload)
    except Exception as exc:
        ui.notify(f"Invalid properties payload: {exc}", color="negative")
        return

    existing_content = block.content or Content()
    updated_content = existing_content.model_copy(update=content_payload)

    updated_block = block.model_copy(
        update={
            "properties": new_properties,
            "metadata": metadata_payload,
            "version": block.version + 1,
            "last_edited_time": datetime.now(timezone.utc),
            "content": updated_content,
        }
    )

    state.store.save_blocks([updated_block])

    block_id_str = str(updated_block.id)
    root_id_str = str(updated_block.root_id)

    _refresh_documents(state, selected=root_id_str)
    _select_block(state, block_id_str)
    ui.notify("Block saved", color="positive")


def _set_trash_state(state: AppState, *, in_trash: bool) -> None:
    block_id = state.selected_block_id
    if not block_id:
        ui.notify("Select a block first", color="warning")
        return
    block = _resolve_block(state, block_id)
    if block is None:
        ui.notify("Selected block could not be resolved.", color="negative")
        return
    if block.parent_id is None:
        ui.notify("Cannot change trash state of the root block.", color="warning")
        return
    try:
        state.store.set_in_trash([block.id], in_trash=in_trash, cascade=True)
    except Exception as exc:
        ui.notify(str(exc), color="negative")
        return

    state.block_cache = {}
    _load_document(state, state.selected_document_id)
    if not in_trash:
        _select_block(state, block_id)
    ui.notify("Block restored" if not in_trash else "Block moved to trash", color="positive")


def _toggle_show_trashed(state: AppState, value: bool) -> None:
    state.show_trashed = value
    state.block_cache = {}
    _load_document(state, state.selected_document_id)


def _rerender_on_toggle(state: AppState) -> Callable[[events.ValueChangeEventArguments], None]:
    def handler(_event: events.ValueChangeEventArguments) -> None:
        if state.selected_block_id:
            block = _resolve_block(state, state.selected_block_id)
            if block:
                _render_block(state, block)
        _render_document_markdown(state)

    return handler


# ---------------------------------------------------------------------------
# UI composition


def _build_sidebar(state: AppState) -> None:
    with ui.column().style("width: 320px; min-width: 280px;").classes("gap-4 p-4 bg-slate-50 h-full"):
        ui.markdown(SIDEBAR_HELP_MD).classes("text-sm text-slate-600")

        def handle_doc_change(event: events.ValueChangeEventArguments) -> None:
            label = event.value if isinstance(event.value, str) else None
            if not label:
                _load_document(state, None)
                return
            block_id = state.document_label_to_id.get(label)
            if block_id is None:
                ui.notify("Unknown document label", color="negative")
                return
            _load_document(state, block_id)

        state.document_select = ui.select(
            options=[],
            label="Documents",
            on_change=handle_doc_change,
        ).props("outlined dense").classes("w-full")

        state.tree_component = ui.tree(
            [],
            node_key="id",
            label_key="label",
            on_select=lambda e: _handle_tree_select(state, e),
        ).props("bordered")
        state.tree_component.classes("w-full rounded-lg border p-2 bg-white overflow-auto")
        state.tree_component.style("height: calc(100vh - 220px);")


def _build_upload_section(state: AppState) -> None:
    with ui.expansion("0. Upload Documents & Datasets", value=False).classes("shadow-sm w-full").props("header-class=font-bold"):
        ui.markdown(
            "Upload sample content to see it immediately in the canonical tree."
        ).classes("text-sm text-slate-600 pb-2 w-full")

        async def handle_markdown(event: events.UploadEventArguments) -> None:
            try:
                content = await event.file.text()
            except Exception as exc:
                ui.notify(f"Upload failed: {exc}", color="negative")
                return
            blocks = markdown_to_blocks(content)
            blocks = _attach_source_metadata(blocks, event.file.name)
            state.store.save_blocks(blocks)
            ui.notify("Stored Markdown document", color="positive")
            _refresh_documents(state, selected=str(blocks[0].id))

        async def handle_pdf(event: events.UploadEventArguments) -> None:
            try:
                data = await event.file.read()
                blocks = azure_di_to_blocks(io.BytesIO(data))
            except Exception as exc:
                ui.notify(f"Azure DI parse failed: {exc}", color="negative")
                return
            blocks = _attach_source_metadata(blocks, event.file.name)
            state.store.save_blocks(blocks)
            ui.notify("Stored Azure DI document", color="positive")
            _refresh_documents(state, selected=str(blocks[0].id))

        async def handle_dataset(event: events.UploadEventArguments) -> None:
            try:
                data = await event.file.read()
                blocks = dataset_to_blocks(io.BytesIO(data))
            except Exception as exc:
                ui.notify(f"Dataset parse failed: {exc}", color="negative")
                return
            blocks = _attach_source_metadata(blocks, event.file.name)
            state.store.save_blocks(blocks)
            ui.notify("Stored dataset", color="positive")
            _refresh_documents(state, selected=str(blocks[0].id))

        with ui.row().classes("gap-3 flex-wrap"):
            ui.upload(label="Markdown (.md)", on_upload=handle_markdown).props("accept=.md,text/markdown")
            ui.upload(label="PDF (Azure DI)", on_upload=handle_pdf).props("accept=application/pdf")
            ui.upload(label="CSV dataset", on_upload=handle_dataset).props("accept=.csv,text/csv")


def _build_overview_section(state: AppState) -> None:
    with ui.expansion("1. Overview", value=True).classes("shadow-sm w-full").props("header-class=font-bold"):
        ui.markdown(OVERVIEW_TEXT).classes("text-sm text-slate-600 w-full")
        ui.code(OVERVIEW_CODE, language="python").classes(
            "w-full text-xs bg-slate-100 text-slate-900 border border-slate-200 rounded"
        )


def _build_document_snapshot_section(state: AppState) -> None:
    with ui.expansion("2. Document Snapshot", value=True).classes("shadow-sm w-full").props("header-class=font-bold"):
        ui.markdown(DOCUMENT_PREVIEW_TEXT).classes("text-sm text-slate-600 w-full")
        ui.code(DOCUMENT_PREVIEW_CODE, language="python").classes(
            "w-full text-xs bg-slate-100 text-slate-900 border border-slate-200 rounded mb-2"
        )
        state.document_markdown_view = ui.markdown("_(select a document)_").classes(
            "w-full rounded-lg border border-slate-200 p-4 bg-slate-50"
        )


def _build_filters_section(state: AppState) -> None:
    with ui.expansion("3. Repository Filters", value=True).classes("shadow-sm w-full").props("header-class=font-bold"):
        ui.markdown(FILTERS_TEXT).classes("text-sm text-slate-600 pb-2 w-full")
        ui.code(FILTERS_CODE, language="python").classes(
            "w-full text-xs bg-slate-100 text-slate-900 border border-slate-200 rounded mb-2"
        )

        with ui.grid(columns=2).classes("gap-2 w-full"):
            block_type_select = ui.select(
                options=["all"] + [bt.value for bt in BlockType],
                label="Block type",
                value="all",
            ).props("outlined dense").classes("w-full")
            block_operator_select = ui.select(
                options=["contains", "equals"],
                label="Operator",
                value="contains",
            ).props("outlined dense").classes("w-full")
            block_path_input = ui.input(
                label="JSON path",
                placeholder="content.data.category",
            ).props("outlined dense").classes("w-full")
            block_value_input = ui.input(
                label="Value",
                placeholder="e.g. Preventive",
            ).props("outlined dense").classes("w-full")

        ui.separator().classes("my-2")
        ui.label("Parent constraints (optional)").classes("text-xs font-semibold text-slate-500")
        with ui.grid(columns=2).classes("gap-2 w-full"):
            parent_type_select = ui.select(
                options=["all"] + [bt.value for bt in BlockType],
                label="Parent type",
                value="all",
            ).props("outlined dense").classes("w-full")
            parent_operator_select = ui.select(
                options=["contains", "equals"],
                label="Parent operator",
                value="contains",
            ).props("outlined dense").classes("w-full")
            parent_path_input = ui.input(
                label="Parent JSON path",
                placeholder="properties.title",
            ).props("outlined dense").classes("w-full")
            parent_value_input = ui.input(
                label="Parent value",
                placeholder="e.g. Overview",
            ).props("outlined dense").classes("w-full")

        ui.separator().classes("my-2")
        ui.label("Root constraints (optional)").classes("text-xs font-semibold text-slate-500")
        with ui.grid(columns=2).classes("gap-2 w-full"):
            root_type_select = ui.select(
                options=["all"] + [bt.value for bt in BlockType],
                label="Root type",
                value="all",
            ).props("outlined dense").classes("w-full")
            root_operator_select = ui.select(
                options=["contains", "equals"],
                label="Root operator",
                value="contains",
            ).props("outlined dense").classes("w-full")
            root_path_input = ui.input(
                label="Root JSON path",
                placeholder="properties.title",
            ).props("outlined dense").classes("w-full")
            root_value_input = ui.input(
                label="Root value",
                placeholder="e.g. Controls Handbook",
            ).props("outlined dense").classes("w-full")

        ui.button(
            "Apply repository filter",
            on_click=lambda: _apply_filter(
                state,
                block_type_select.value,
                block_path_input.value,
                block_operator_select.value,
                block_value_input.value,
                parent_type_select.value,
                parent_path_input.value,
                parent_operator_select.value,
                parent_value_input.value,
                root_type_select.value,
                root_path_input.value,
                root_operator_select.value,
                root_value_input.value,
            ),
        ).classes("mt-2 w-full sm:w-auto")

        state.filter_results_container = ui.column().classes("mt-2 gap-1 w-full")


def _build_inspector_section(state: AppState) -> None:
    with ui.expansion("4. Block Inspector", value=True).classes("shadow-sm w-full").props("header-class=font-bold"):
        ui.markdown(INSPECTOR_TEXT).classes("text-sm text-slate-600 pb-2 w-full")
        ui.code(INSPECTOR_CODE, language="python").classes(
            "w-full text-xs bg-slate-100 text-slate-900 border border-slate-200 rounded mb-2"
        )

        state.details_markdown = ui.markdown("Select a block to inspect.").classes(
            "w-full rounded-lg border border-slate-200 p-4 bg-white"
        )

        with ui.row().classes("w-full gap-4 flex-wrap items-stretch"):
            state.properties_area = ui.textarea(
                value="{}",
                label="Properties (JSON)",
            ).props("outlined").classes("flex-1").style("min-width: 260px; height: 160px;")
            state.metadata_area = ui.textarea(
                value="{}",
                label="Metadata (JSON)",
            ).props("outlined").classes("flex-1").style("min-width: 260px; height: 160px;")
            state.data_area = ui.textarea(
                value="{}",
                label="Content data (JSON)",
            ).props("outlined").classes("flex-1").style("min-width: 260px; height: 160px;")

        ui.button("Save block changes", on_click=lambda: _save_block_changes(state)).classes("mt-2 w-full sm:w-auto")

        with ui.row().classes("gap-2 flex-wrap mt-2"):
            ui.button(
                "Move to trash",
                on_click=lambda: _set_trash_state(state, in_trash=True),
            ).props("outline")
            ui.button(
                "Restore from trash",
                on_click=lambda: _set_trash_state(state, in_trash=False),
            )
            ui.checkbox(
                "Show trashed blocks",
                value=state.show_trashed,
                on_change=lambda e: _toggle_show_trashed(state, bool(e.value)),
            )


def _build_preview_section(state: AppState) -> None:
    with ui.expansion("5. Renderer Preview", value=True).classes("shadow-sm w-full").props("header-class=font-bold"):
        ui.markdown(PREVIEW_TEXT).classes("text-sm text-slate-600 pb-2 w-full")
        ui.code(PREVIEW_CODE, language="python").classes(
            "w-full text-xs bg-slate-100 text-slate-900 border border-slate-200 rounded mb-2"
        )

        with ui.row().classes("w-full gap-4 flex-wrap items-center"):
            state.include_metadata_checkbox = ui.checkbox(
                "Include metadata",
                value=False,
                on_change=_rerender_on_toggle(state),
            )
            state.include_children_checkbox = ui.checkbox(
                "Recursive block preview",
                value=True,
                on_change=lambda e: _toggle_recursive_preview(state, bool(e.value)),
            )

        state.markdown_view = ui.markdown("_(select a block)_").classes(
            "w-full rounded-lg border border-slate-200 p-4 bg-white"
        )
        state.markdown_view.style("min-height: 160px;")


def _toggle_recursive_preview(state: AppState, include_children: bool) -> None:
    state.render_block_children = include_children
    if state.selected_block_id:
        block = _resolve_block(state, state.selected_block_id)
        if block:
            _render_block(state, block)
    _render_document_markdown(state)


def build_ui(state: AppState) -> None:
    with ui.header().classes("justify-between items-center"):
        ui.label("Block Data Store — POC Showcase").classes("text-lg font-semibold")

    with ui.row().classes("w-full h-full gap-4"):
        _build_sidebar(state)

        with ui.column().classes("flex-1 gap-4"):
            _build_upload_section(state)
            _build_overview_section(state)
            _build_document_snapshot_section(state)
            _build_filters_section(state)
            _build_inspector_section(state)
            _build_preview_section(state)

    _refresh_documents(state)


state = _bootstrap_state()


if __name__ in {"__main__", "__mp_main__"}:
    build_ui(state)
    ui.run(title="Block Data Store POC Showcase")
