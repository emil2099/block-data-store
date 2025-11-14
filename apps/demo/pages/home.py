"""Landing page for the modular NiceGUI demo."""

from __future__ import annotations

from nicegui import ui

from block_data_store.models.block import BlockType
from block_data_store.repositories.filters import WhereClause

from ..layout import page_frame, stat_card
from ..state import get_context


@ui.page("/")
def home_page() -> None:  # pragma: no cover - UI wiring
    ctx = get_context()
    documents = ctx.store.list_documents()
    dataset_roots = [
        block
        for block in ctx.store.query_blocks(where=WhereClause(type=BlockType.DATASET))
        if block.parent_id is None
    ]
    pdf_docs = [doc for doc in documents if (doc.metadata or {}).get("source") == "azure_di"]

    with page_frame(
        current="/",
        title="Block Data Store Demo",
        subtitle="Explore how documents, pages, and datasets flow through the canonical block model.",
    ):
        with ui.row().classes("gap-4 flex-wrap"):
            stat_card("Documents", str(len(documents)), href="/documents")
            stat_card("PDFs with pages", str(len(pdf_docs)), href="/pdf")
            stat_card("Datasets", str(len(dataset_roots)), href="/datasets")

        ui.separator()

        ui.markdown(
            """
## What you can do

- **Upload & inspect** Markdown, Azure DI PDFs, and CSV datasets.
- **Render page-by-page** output for Azure-formatted PDFs using the page grouping model.
- **Traverse the canonical tree** with rich metadata and renderer previews.
- **Preview datasets** parsed into `DatasetBlock` + `RecordBlock` graphs.
"""
        ).classes("text-slate-600 w-full")

        with ui.row().classes("gap-3 flex-wrap"):
            ui.button("Manage documents", on_click=lambda: ui.navigate.to("/documents"))
            ui.button("View PDF pages", on_click=lambda: ui.navigate.to("/pdf"))
            ui.button("Canonical tree explorer", on_click=lambda: ui.navigate.to("/tree"))
            ui.button("Dataset explorer", on_click=lambda: ui.navigate.to("/datasets"))


__all__ = ["home_page"]
