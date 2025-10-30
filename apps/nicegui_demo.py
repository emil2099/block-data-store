"""NiceGUI demonstration app for the Block Data Store POC."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
import ast
from pathlib import Path
import sys
from typing import Any, Callable
from uuid import UUID

from nicegui import events, ui

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Add project root to module search path when running as a script.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from block_data_store.db.engine import create_engine, create_session_factory
from block_data_store.db.schema import create_all
from block_data_store.models.block import Block, BlockType, Content
from block_data_store.parser import load_markdown_path
from block_data_store.renderers.base import RenderOptions
from block_data_store.renderers.markdown import MarkdownRenderer
from block_data_store.repositories.filters import FilterOperator, PropertyFilter, WhereClause
from block_data_store.store import DocumentStore, create_document_store

DB_PATH = Path(__file__).resolve().parent / "nicegui_demo.db"
SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class AppState:
    store: DocumentStore
    renderer: MarkdownRenderer
    documents: list[Block] = field(default_factory=list)
    documents_by_id: dict[str, Block] = field(default_factory=dict)
    document_label_to_id: dict[str, str] = field(default_factory=dict)
    selected_document_id: str | None = None
    selected_block_id: str | None = None
    pending_block_id: str | None = None
    block_cache: dict[str, Block] = field(default_factory=dict)
    filter_results: list[Block] = field(default_factory=list)
    document_select: Any | None = None
    tree_component: Any | None = None
    filter_results_container: Any | None = None
    details_markdown: Any | None = None
    document_markdown_view: Any | None = None
    properties_area: Any | None = None
    metadata_area: Any | None = None
    data_area: Any | None = None
    markdown_view: Any | None = None
    include_metadata_checkbox: Any | None = None
    resolve_synced_checkbox: Any | None = None
    include_children_checkbox: Any | None = None
    render_block_children: bool = True


def _document_label(block: Block) -> str:
    title = getattr(block.properties, "title", None)
    return title or f"Document {block.id}"


def _block_label(block: Block) -> str:
    if block.type is BlockType.DOCUMENT:
        title = getattr(block.properties, "title", None)
        if title:
            return f"{block.type.value}: {title}"

    if block.content:
        if block.content.text:
            summary = block.content.text.strip().splitlines()[0][:40]
            if summary:
                return f"{block.type.value}: {summary}"
        data = block.content.data
        if isinstance(data, dict) and data:
            key, value = next(iter(data.items()))
            return f"{block.type.value}: {key}={value}"
    return f"{block.type.value}: {block.id}"


def _bootstrap_state() -> AppState:
    engine = create_engine(sqlite_path=DB_PATH)
    create_all(engine)
    session_factory = create_session_factory(engine)
    store = create_document_store(session_factory)
    renderer = MarkdownRenderer(resolve_reference=lambda ref: store.get_block(ref, depth=1) if ref else None)
    state = AppState(store=store, renderer=renderer)
    _seed_documents(state)
    return state


def _seed_documents(state: AppState) -> None:
    if state.store.list_documents():
        return
    for path in sorted(SAMPLE_DATA_DIR.glob("*.md")):
        blocks = load_markdown_path(path)
        state.store.save_blocks(blocks)


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


def _format_block_details(block: Block) -> str:
    lines = [
        f"### {_block_label(block)}",
        "",
        f"- **ID**: `{block.id}`",
        f"- **Type**: `{block.type.value}`",
        f"- **Parent ID**: `{block.parent_id}`",
        f"- **Root ID**: `{block.root_id}`",
        f"- **Version**: `{block.version}`",
        f"- **Created**: `{block.created_time.isoformat()}`",
        f"- **Last Edited**: `{block.last_edited_time.isoformat()}`",
    ]
    if block.metadata:
        lines.append(f"- **Metadata keys**: {', '.join(sorted(block.metadata.keys()))}")
    return "\n".join(lines)


def _render_block(state: AppState, block: Block) -> None:
    if state.markdown_view is None:
        return
    include_metadata = bool(state.include_metadata_checkbox.value) if state.include_metadata_checkbox else False
    resolve_synced = bool(state.resolve_synced_checkbox.value) if state.resolve_synced_checkbox else True
    recursive = state.render_block_children
    options = RenderOptions(
        include_metadata=include_metadata,
        resolve_synced=resolve_synced,
        recursive=recursive,
    )
    rendered = state.renderer.render(block, options=options)
    state.markdown_view.set_content(rendered or "_(empty)_")


def _render_document_markdown(state: AppState, document_block: Block | None = None) -> None:
    view = state.document_markdown_view
    if view is None:
        return

    include_metadata = bool(state.include_metadata_checkbox.value) if state.include_metadata_checkbox else False
    resolve_synced = bool(state.resolve_synced_checkbox.value) if state.resolve_synced_checkbox else True
    options = RenderOptions(include_metadata=include_metadata, resolve_synced=resolve_synced)

    if document_block is None:
        document_id = state.selected_document_id
        if not document_id:
            view.set_content("_(no document selected)_")
            return
        document_block = state.documents_by_id.get(document_id) or state.block_cache.get(document_id)
        if document_block is None:
            try:
                document_block = state.store.get_root_tree(UUID(document_id), depth=None)
            except Exception:
                document_block = None
    if document_block is None:
        view.set_content("_(document unavailable)_")
        return

    rendered = state.renderer.render(document_block, options=options)
    view.set_content(rendered or "_(empty document)_")


def _update_block_preview_mode(state: AppState, *, include_children: bool) -> None:
    state.render_block_children = include_children
    if state.selected_block_id:
        block = state.block_cache.get(state.selected_block_id)
        if block:
            _render_block(state, block)
    else:
        if state.markdown_view:
            state.markdown_view.set_content("_(select a block)_")
    _render_document_markdown(state)


def _select_block(state: AppState, block_id: str) -> None:
    block = state.block_cache.get(block_id)
    if block is None:
        block = state.store.get_block(UUID(block_id), depth=1)
        if block is None:
            return
        state.block_cache[block_id] = block

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
    elif isinstance(selected, list):
        if not selected:
            return
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
    UUID(block_id)

    _select_block(state, block_id)


def _load_document(state: AppState, document_id: str | None) -> None:
    doc_value = (document_id or "").strip() if isinstance(document_id, str) else None
    if doc_value:
        try:
            UUID(doc_value)
        except ValueError:
            raise ValueError(f"Could not resolve document identifier: {document_id}") from None
            doc_value = None

    state.selected_document_id = doc_value
    state.selected_block_id = None
    state.block_cache = {}

    if not doc_value or state.tree_component is None:
        _set_tree_nodes(state.tree_component, [])
        if state.details_markdown:
            state.details_markdown.set_content("Select a block to inspect.")
        if state.data_area:
            state.data_area.value = "{}"
        _render_document_markdown(state, None)
        return

    root_uuid = UUID(doc_value)
    root_block = state.store.get_root_tree(root_uuid, depth=None)
    state.block_cache[str(root_block.id)] = root_block
    state.documents_by_id[str(root_block.id)] = root_block
    tree_payload = [_build_tree(state.block_cache, root_block)]
    _set_tree_nodes(state.tree_component, tree_payload)
    _render_document_markdown(state, root_block)

    if state.pending_block_id and state.pending_block_id in state.block_cache:
        pending = state.pending_block_id
        state.pending_block_id = None
        _select_block(state, pending)
    else:
        if state.details_markdown:
            state.details_markdown.set_content("Select a block to inspect.")
        if state.markdown_view:
            state.markdown_view.set_content("")
        if state.data_area:
            state.data_area.value = "{}"

    if state.filter_results_container:
        state.filter_results_container.clear()


def _refresh_documents(state: AppState, selected: str | None = None) -> None:
    state.documents = state.store.list_documents()
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


def _render_filter_results(state: AppState) -> None:
    container = state.filter_results_container
    if container is None:
        return
    container.clear()
    with container:
        if not state.filter_results:
            ui.label("No blocks matched.").classes("text-sm text-slate-500")
            return
        for block in state.filter_results:
            label = f"{block.type.value} — {_block_label(block)}"
            ui.button(
                label,
                on_click=lambda _, b=block: _focus_block(state, b),
            ).props("dense flat color=primary")


def _focus_block(state: AppState, block: Block) -> None:
    block_id = str(block.id)
    root_id = str(block.root_id)
    state.pending_block_id = block_id
    if state.selected_document_id != root_id:
        if state.document_select:
            state.document_select.value = root_id
            state.document_select.update()
        _load_document(state, root_id)
    else:
        _select_block(state, block_id)


def _apply_filter(
    state: AppState,
    block_type_value: str,
    path_value: str,
    operator_value: str,
    filter_value: str,
) -> None:
    where_kwargs: dict[str, Any] = {}
    if state.selected_document_id:
        where_kwargs["root_id"] = state.selected_document_id
    if block_type_value and block_type_value != "all":
        where_kwargs["type"] = BlockType(block_type_value)

    where_clause = WhereClause(**where_kwargs) if where_kwargs else None

    property_filter = None
    path = (path_value or "").strip()
    value = (filter_value or "").strip()
    if path and value:
        operator = FilterOperator.CONTAINS if operator_value == "contains" else FilterOperator.EQUALS
        coerced_value: Any = value
        try:
            coerced_value = ast.literal_eval(value)
        except Exception:
            lowered = value.lower()
            if lowered == "true":
                coerced_value = True
            elif lowered == "false":
                coerced_value = False

        try:
            property_filter = PropertyFilter(path=path, value=coerced_value, operator=operator)
        except Exception as exc:
            raise ValueError(f"Invalid filter definition: {exc}") from exc

    state.filter_results = state.store.query_blocks(
        where=where_clause,
        property_filter=property_filter,
        limit=50,
    )
    _render_filter_results(state)


def _save_block_changes(state: AppState) -> None:
    if not state.selected_block_id:
        raise RuntimeError("Select a block before saving.")

    block = state.block_cache.get(state.selected_block_id)
    if block is None:
        block = state.store.get_block(UUID(state.selected_block_id), depth=1)
        if block is None:
            raise RuntimeError("Selected block no longer exists.")

    try:
        properties_payload = json.loads(state.properties_area.value or "{}") if state.properties_area else {}
        metadata_payload = json.loads(state.metadata_area.value or "{}") if state.metadata_area else {}
        content_payload = json.loads(state.data_area.value or "{}") if state.data_area else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON payload: {exc}") from exc

    if not isinstance(metadata_payload, dict):
        raise ValueError("Metadata JSON payload must be an object.")
    if not isinstance(content_payload, dict):
        raise ValueError("Content JSON payload must be an object.")

    try:
        new_properties = block.properties.__class__(**properties_payload)
    except Exception as exc:
        raise ValueError(f"Invalid properties payload: {exc}") from exc

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
    target_doc = str(updated_block.root_id)
    state.pending_block_id = str(updated_block.id)
    _refresh_documents(state, selected=target_doc)
    print(f"Block {updated_block.id} saved successfully.")


def _rerender_on_toggle(state: AppState) -> Callable[[events.ValueChangeEventArguments], None]:
    def handler(_event: events.ValueChangeEventArguments) -> None:
        if state.selected_block_id:
            block = state.block_cache.get(state.selected_block_id)
            if block:
                _render_block(state, block)
        _render_document_markdown(state)

    return handler


def build_ui(state: AppState) -> None:
    with ui.header().classes("items-center justify-between"):
        ui.label("Block Data Store — NiceGUI Demo").classes("text-lg font-semibold")
        ui.label("Markdown → Repository → DocumentStore → Renderer → UI").classes("text-sm text-slate-500")

    ui.markdown(
        """
        **What this demo shows**

        - **Ingestion**: Markdown samples under `data/` are parsed into typed blocks and persisted through the SQL-backed DocumentStore factory.
        - **Navigation**: The left pane lists canonical documents and expands their hierarchies so you can inspect the composed block tree.
        - **Mutation**: Selecting a block wires its properties, metadata, and data payload into the editors on the right; saving issues an upsert through the store.
        - **Rendering**: Live Markdown previews illustrate how the renderer layer materialises both an individual block and the entire document snapshot.

        Update a block and save to watch the previews refresh—every change flows through the same pipeline the POC uses end to end.
        """
    ).classes("px-4 pb-4 text-sm text-slate-600")

    splitter = ui.splitter().style("height: calc(100vh - 60px);").classes('w-full')

    with splitter.before:
        with ui.column().classes("w-full h-full gap-4 p-4"):
            def handle_doc_change(e: events.ValueChangeEventArguments) -> None:
                label = e.value if isinstance(e.value, str) else None
                if not label:
                    _load_document(state, None)
                    return
                block_id = state.document_label_to_id.get(label)
                if block_id is None:
                    raise ValueError(f"Unknown document label selected: {label}")
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
            ).props("bordered").classes("w-full rounded-lg border p-2 overflow-auto").style("height: 50vh;")

            with ui.card().classes("w-full"):
                ui.label("Filter Blocks").classes("text-sm font-semibold")
                type_select = ui.select(
                    options=["all"] + [bt.value for bt in BlockType],
                    label="Block type",
                    value="all",
                ).props("outlined dense").classes("w-full")
                path_input = ui.input(
                    label="JSON path (e.g. content.data.category)",
                    placeholder="content.data.category",
                ).props("outlined dense").classes("w-full")
                operator_select = ui.select(
                    options=["contains", "equals"],
                    label="Operator",
                    value="contains",
                ).props("outlined dense").classes("w-full")
                value_input = ui.input(
                    label="Value",
                    placeholder="Search value",
                ).props("outlined dense").classes("w-full")

                ui.button(
                    "Apply filter",
                    on_click=lambda: _apply_filter(
                        state,
                        type_select.value,
                        path_input.value,
                        operator_select.value,
                        value_input.value,
                    ),
                ).classes("w-full")

                state.filter_results_container = ui.column().classes("w-full gap-1 mt-2")

    with splitter.after:
        with ui.column().classes("w-full h-full gap-4 p-4"):
            state.details_markdown = ui.markdown("Select a block to inspect.").classes(
                "w-full rounded-lg border border-slate-200 p-4 bg-white"
            )
            with ui.row().classes("w-full gap-4 flex-wrap items-center"):
                state.include_metadata_checkbox = ui.checkbox(
                    "Include metadata",
                    value=False,
                    on_change=_rerender_on_toggle(state),
                )
                state.resolve_synced_checkbox = ui.checkbox(
                    "Resolve synced content",
                    value=True,
                    on_change=_rerender_on_toggle(state),
                )
                state.include_children_checkbox = ui.checkbox(
                    "Include children in block preview",
                    value=True,
                    on_change=lambda e: _update_block_preview_mode(
                        state, include_children=bool(e.value)
                    ),
                )
                state.render_block_children = True

            state.properties_area = ui.textarea(
                value="{}",
                label="Properties (JSON)",
            ).props("outlined").style("height: 160px;").classes("w-full")
            state.metadata_area = ui.textarea(
                value="{}",
                label="Metadata (JSON)",
            ).props("outlined").style("height: 160px;").classes("w-full")
            state.data_area = ui.textarea(
                value="{}",
                label="Content data (JSON)",
            ).props("outlined").style("height: 160px;").classes("w-full")

            ui.button(
                "Save changes",
                on_click=lambda: _save_block_changes(state),
            ).classes("self-start w-full sm:w-auto")

            ui.separator()
            ui.label("Focused block preview").classes("text-sm font-semibold text-slate-600")
            state.markdown_view = ui.markdown("_(select a block)_").classes(
                "w-full rounded-lg border border-slate-200 p-4 bg-white overflow-auto"
            ).style("min-height: 180px; max-height: 35vh;")

            ui.label("Document preview").classes("text-sm font-semibold text-slate-600")
            state.document_markdown_view = ui.markdown("_(no document selected)_").classes(
                "w-full rounded-lg border border-slate-200 p-4 bg-slate-50"
            )

    _refresh_documents(state)


state = _bootstrap_state()


if __name__ in {"__main__", "__mp_main__"}:
    build_ui(state)
    ui.run(title="Block Data Store NiceGUI Demo")
