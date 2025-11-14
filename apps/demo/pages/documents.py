"""Document upload/listing page."""

from __future__ import annotations

import io
from datetime import datetime

from nicegui import events, ui

from block_data_store.models.block import Block
from block_data_store.parser import markdown_to_blocks
from block_data_store.parser.azure_di_parser import azure_di_to_blocks
from block_data_store.parser.dataset_parser import dataset_to_blocks

from ..layout import page_frame
from ..state import get_context


@ui.page("/documents")
def documents_page() -> None:  # pragma: no cover - UI wiring
    ctx = get_context()

    with page_frame(
        current="/documents",
        title="Documents & Uploads",
        subtitle="Add Markdown, PDF, or CSV sources and inspect their stored metadata.",
    ):
        documents_container = ui.column().classes("gap-2 w-full")

        def refresh_documents() -> None:
            documents_container.clear()
            docs = ctx.store.list_documents()
            if not docs:
                with documents_container:
                    ui.label("No documents yet. Upload a Markdown or PDF file.")
                return
            with documents_container:
                for block in docs:
                    _document_card(block)

        ui.markdown(
            "Uploaders below save directly into the sample SQLite database."
        ).classes("text-slate-500")

        with ui.row().classes("gap-3 flex-wrap"):
            ui.upload(
                label="Upload Markdown",
                on_upload=lambda e: _after(_handle_markdown_upload(e, ctx.store), refresh_documents),
            ).props("accept=.md,text/markdown")

            ui.upload(
                label="Upload PDF (Azure DI)",
                on_upload=lambda e: _after(_handle_pdf_upload(e, ctx.store), refresh_documents),
            ).props("accept=application/pdf")

            ui.upload(
                label="Upload CSV Dataset",
                on_upload=lambda e: _after(_handle_dataset_upload(e, ctx.store), refresh_documents),
            ).props("accept=.csv,text/csv")

        ui.separator()

        refresh_documents()


def _document_card(block: Block) -> None:
    title = getattr(block.properties, "title", None) or f"Document {block.id}"

    timestamp = block.created_time.strftime("%Y-%m-%d %H:%M") if isinstance(block.created_time, datetime) else ""
    source = (block.metadata or {}).get("source")
    with ui.card().classes("w-full shadow-sm p-4"):
        ui.label(title).classes("text-lg font-semibold")
        with ui.row().classes("text-xs text-slate-500 gap-4"):
            ui.label(f"Type: {block.type.value}")
            if timestamp:
                ui.label(f"Created: {timestamp}")
            ui.label(f"Block ID: {str(block.id)[:8]}")
            if source:
                ui.label(f"Source: {source}")
        with ui.row().classes("gap-2 mt-2"):
            ui.button("Open in Tree", on_click=lambda _, doc_id=str(block.id): ui.open(f"/tree?doc={doc_id}"))
            if (block.metadata or {}).get("source") == "azure_di":
                ui.button("View pages", on_click=lambda _, doc_id=str(block.id): ui.open(f"/pdf?doc={doc_id}"),).props("outline")


def _handle_markdown_upload(event: events.UploadEvent, store) -> None:
    try:
        content = event.content.read().decode("utf-8")
    except Exception as exc:  # pragma: no cover - user I/O
        ui.notify(f"Upload failed: {exc}", color="negative")
        return
    blocks = markdown_to_blocks(content)
    store.save_blocks(blocks)
    ui.notify(f"Stored Markdown document ({len(blocks)} blocks)", color="positive")


def _handle_pdf_upload(event: events.UploadEvent, store) -> None:
    data = event.content.read()
    try:
        blocks = azure_di_to_blocks(io.BytesIO(data))
    except Exception as exc:  # pragma: no cover - optional dependency/runtime failures
        ui.notify(f"Azure DI parse failed: {exc}", color="negative")
        return
    store.save_blocks(blocks)
    ui.notify("Stored Azure DI document", color="positive")


def _handle_dataset_upload(event: events.UploadEvent, store) -> None:
    data = event.content.read()
    try:
        blocks = dataset_to_blocks(io.BytesIO(data))
    except Exception as exc:  # pragma: no cover - optional dependency/runtime failures
        ui.notify(f"Dataset parse failed: {exc}", color="negative")
        return
    store.save_blocks(blocks)
    ui.notify("Stored dataset", color="positive")


def _after(result, refresher) -> None:
    """Run a refresh callback after an upload handler."""

    refresher()
    return result


__all__ = ["documents_page"]
