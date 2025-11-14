"""Canonical tree explorer page."""

from __future__ import annotations

import json
from uuid import UUID

from nicegui import ui
from starlette.requests import Request

from block_data_store.models.block import Block, BlockType
from block_data_store.renderers.base import RenderOptions

from ..layout import page_frame
from ..state import get_context


@ui.page("/tree")
def tree_page(request: Request) -> None:  # pragma: no cover - UI wiring
    ctx = get_context()
    documents = ctx.store.list_documents()
    if not documents:
        with page_frame(
            current="/tree",
            title="Canonical Tree Explorer",
            subtitle="Upload a document first to explore its canonical hierarchy.",
        ):
            ui.label("No documents available.")
        return

    doc_options = {_doc_label(doc): str(doc.id) for doc in documents}
    query_doc = request.query_params.get("doc") if request else None
    default_value = query_doc if query_doc in doc_options.values() else next(iter(doc_options.values()))
    block_lookup: dict[str, Block] = {}

    with page_frame(
        current="/tree",
        title="Canonical Tree Explorer",
        subtitle="Inspect blocks, metadata, and renderer output interactively.",
    ):
        controls = ui.row().classes("gap-4 flex-wrap w-full")
        with controls:
            doc_select = ui.select(
                label="Document",
                options=doc_options,
                value=default_value,
            ).classes("min-w-[220px]")
            include_metadata = ui.checkbox("Include metadata").classes("mt-4")
            recursive_preview = ui.checkbox("Recursive preview", value=True).classes("mt-4")

        content_row = ui.row().classes("w-full gap-6 flex-wrap")
        with content_row:
            tree_component = ui.tree(
                nodes=[],
                on_select=lambda e: _select_block(
                    e.value,
                    block_lookup,
                    details_panel,
                    preview_panel,
                    include_metadata,
                    recursive_preview,
                    ctx.renderer,
                ),
            ).classes("min-w-[320px] flex-1 bg-white shadow-sm p-3 rounded")
            tree_component.props("node-key=id tick-strategy=leaf dense")
            with ui.column().classes("flex-1 gap-3"):
                details_panel = ui.markdown("Select a block to inspect.").classes(
                    "bg-white shadow-sm p-4"
                )
                preview_panel = ui.markdown("Renderer preview will appear here.").classes(
                    "bg-white shadow-sm p-4 min-h-[200px]"
                )

        def load_document(doc_id: str | None) -> None:
            if not doc_id:
                return
            root = ctx.store.get_root_tree(UUID(doc_id), depth=None)
            block_lookup.clear()
            nodes = [_build_tree_nodes(root, block_lookup)]
            tree_component._props["nodes"] = nodes
            tree_component.update()
            details_panel.set_content("Select a block to inspect.")
            preview_panel.set_content("Renderer preview will appear here.")

        doc_select.on_change(lambda e: load_document(e.value))
        load_document(doc_select.value)


def _doc_label(block: Block) -> str:
    title = getattr(block.properties, "title", None)
    return title or f"Document {str(block.id)[:8]}"


def _build_tree_nodes(block: Block, cache: dict[str, Block]) -> dict:
    block_id = str(block.id)
    cache[block_id] = block
    return {
        "id": block_id,
        "label": _block_label(block),
        "children": [_build_tree_nodes(child, cache) for child in block.children()],
    }


def _block_label(block: Block) -> str:
    title = getattr(block.properties, "title", None)
    if title and block.type is BlockType.HEADING:
        return f"Heading: {title}"
    if block.content and block.content.plain_text:
        summary = block.content.plain_text.strip().splitlines()[0][:40]
        if summary:
            return f"{block.type.value}: {summary}"
    return f"{block.type.value}: {str(block.id)[:8]}"


def _select_block(
    value,
    cache: dict[str, Block],
    details_panel,
    preview_panel,
    include_metadata_checkbox,
    recursive_checkbox,
    renderer,
) -> None:
    block_id = None
    if isinstance(value, dict):
        block_id = value.get("id")
    elif isinstance(value, str):
        block_id = value
    if not block_id or block_id not in cache:
        return
    block = cache[block_id]
    metadata_lines = [f"**Type:** {block.type.value}", f"**ID:** {block_id}"]
    if block.parent_id:
        metadata_lines.append(f"**Parent:** {str(block.parent_id)[:8]}")
    payload = {
        "properties": block.properties.model_dump(mode="json"),
        "metadata": block.metadata,
        "content": block.content.model_dump(mode="json") if block.content else None,
    }
    details_panel.set_content(
        "\n".join(metadata_lines)
        + "\n\n```json\n"
        + json.dumps(payload, indent=2)
        + "\n```"
    )

    options = RenderOptions(
        include_metadata=bool(include_metadata_checkbox.value),
        recursive=bool(recursive_checkbox.value),
    )
    preview = renderer.render(block, options=options)
    preview_panel.set_content(preview or "_(empty selection)_")


__all__ = ["tree_page"]
