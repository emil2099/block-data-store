"""Page-by-page viewer for Azure DI documents."""

from __future__ import annotations

from uuid import UUID

from nicegui import ui
from starlette.requests import Request

from block_data_store.models.block import Block, BlockType
from block_data_store.renderers.base import RenderOptions

from ..layout import page_frame
from ..state import get_context


@ui.page("/pdf")
def pdf_pages(request: Request) -> None:  # pragma: no cover - UI wiring
    ctx = get_context()
    state: dict[str, Block] = {"root": None}

    with page_frame(
        current="/pdf",
        title="Azure DI Page Viewer",
        subtitle="Render Azure Document Intelligence parses one page at a time.",
    ):
        documents = _azure_documents(ctx.store)
        if not documents:
            ui.label("Upload a PDF via the Documents page to enable this view.").classes("text-slate-500")
            return

        doc_options = {str(doc.id): _doc_label(doc) for doc in documents}
        query_doc = request.query_params.get("doc") if request else None
        available_values = list(doc_options.keys())
        default_doc = query_doc if query_doc in available_values else (available_values[0] if available_values else None)
        page_area = ui.markdown("Select a page to render.").classes("w-full bg-white shadow-sm p-4 min-h-[240px]")
        pages_container = ui.row().classes("gap-2 flex-wrap")

        def render_page(doc_id: str, page_id: str) -> None:
            root = state.get("root")
            if not root or str(root.id) != doc_id:
                root = ctx.store.get_root_tree(UUID(doc_id), depth=None)
                state["root"] = root
            markdown = _render_page_markdown(root, UUID(page_id), ctx.renderer)
            if markdown.strip():
                page_area.set_content(markdown)
            else:
                page_area.set_content("_(No content tagged for this page.)_")

        def load_document(doc_id: str | None) -> None:
            pages_container.clear()
            page_area.set_content("Select a page to render.")
            if not doc_id:
                return
            root = ctx.store.get_root_tree(UUID(doc_id), depth=None)
            state["root"] = root
            pages = _page_blocks(root)
            if not pages:
                with pages_container:
                    ui.label("Document has no page groups.")
                return
            with pages_container:
                for page_block in pages:
                    ui.button(
                        f"Page {page_block.properties.page_number}",
                        on_click=lambda _, d=doc_id, pid=str(page_block.id): render_page(d, pid),
                    )

        ui.select(
            label="Select document",
            options=doc_options,
            value=default_doc,
            on_change=lambda e: load_document(e.value),
        ).classes("w-full")

        ui.separator()
        with ui.column().classes("gap-2 w-full"):
            ui.label("Pages").classes("text-sm font-semibold text-slate-600")
            pages_container
            ui.label("Page preview").classes("text-sm font-semibold text-slate-600 mt-4")
            page_area

        if default_doc:
            load_document(default_doc)


def _azure_documents(store) -> list[Block]:
    docs = store.list_documents()
    return [doc for doc in docs if (doc.metadata or {}).get("source") == "azure_di"]


def _doc_label(block: Block) -> str:
    title = getattr(block.properties, "title", None)
    return title or f"Document {str(block.id)[:8]}"


def _page_blocks(root: Block) -> list[Block]:
    for child in root.children():
        if child.type is BlockType.GROUP_INDEX and getattr(child.properties, "group_index_type", None) == "page":
            return sorted(child.children(), key=lambda b: b.properties.page_number)
    return []


def _render_page_markdown(root: Block, page_id: UUID, renderer) -> str:
    ordered_blocks: list[Block] = []

    def walk(block: Block) -> None:
        ordered_blocks.append(block)
        for child in block.children():
            walk(child)

    walk(root)
    options = RenderOptions(include_metadata=False, recursive=True)
    sections: list[str] = []
    for block in ordered_blocks:
        groups = getattr(block.properties, "groups", None)
        if not groups or page_id not in groups:
            continue
        if block.type in {BlockType.DOCUMENT, BlockType.GROUP_INDEX, BlockType.PAGE_GROUP}:
            continue
        rendered = renderer.render(block, options=options)
        if rendered.strip():
            sections.append(rendered)
    return "\n\n".join(sections)


__all__ = ["pdf_pages"]
