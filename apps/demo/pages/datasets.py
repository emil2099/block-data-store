"""Dataset explorer page."""

from __future__ import annotations

import io
import json
from uuid import UUID

from nicegui import events, ui

from block_data_store.models.block import BlockType
from block_data_store.parser.dataset_parser import dataset_to_blocks
from block_data_store.repositories.filters import WhereClause

from ..layout import page_frame
from ..state import get_context


@ui.page("/datasets")
def datasets_page() -> None:  # pragma: no cover - UI wiring
    ctx = get_context()

    with page_frame(
        current="/datasets",
        title="Dataset Explorer",
        subtitle="Upload CSV sources and preview dataset blocks rendered as tables.",
    ):
        dataset_select = ui.select(label="Dataset", options={}, on_change=None).classes("w-full")
        table_preview = ui.markdown("Upload a dataset to render its table.").classes("bg-white shadow-sm p-4 w-full")
        record_preview = ui.code("{}", language="json").classes("w-full")

        def refresh_datasets() -> None:
            roots = [
                block
                for block in ctx.store.query_blocks(where=WhereClause(type=BlockType.DATASET))
                if block.parent_id is None
            ]
            options = { _dataset_label(block): str(block.id) for block in roots }
            dataset_select.options = options
            dataset_select.update()
            if options:
                dataset_select.value = next(iter(options.values()))
                dataset_select.update()
                load_dataset(dataset_select.value)
            else:
                table_preview.set_content("Upload a dataset to see it rendered.")
                record_preview.set_content("{}")

        def load_dataset(dataset_id: str | None) -> None:
            if not dataset_id:
                return
            block = ctx.store.get_block(UUID(dataset_id), depth=None)
            if block is None:
                ui.notify("Dataset not found", color="negative")
                return
            table_preview.set_content(ctx.renderer.render(block))
            records = [child for child in block.children() if child.type is BlockType.RECORD]
            first = records[0].content.data if records and records[0].content else {}
            record_preview.set_content(json.dumps(first or {}, indent=2))

        dataset_select.on_change(lambda e: load_dataset(e.value))

        with ui.row().classes("gap-3 flex-wrap mt-4"):
            ui.upload(
                label="Upload CSV Dataset",
                on_upload=lambda e: _after_dataset_upload(e, ctx.store, refresh_datasets),
            ).props("accept=.csv,text/csv")

        ui.separator()
        ui.label("Rendered dataset table").classes("text-sm font-semibold text-slate-600")
        table_preview
        ui.label("First record preview").classes("text-sm font-semibold text-slate-600")
        record_preview

        refresh_datasets()


def _after_dataset_upload(event: events.UploadEvent, store, refresher) -> None:
    data = event.content.read()
    try:
        blocks = dataset_to_blocks(io.BytesIO(data))
    except Exception as exc:  # pragma: no cover - pandas optional
        ui.notify(f"Dataset parse failed: {exc}", color="negative")
        return
    store.save_blocks(blocks)
    ui.notify("Dataset stored", color="positive")
    refresher()


def _dataset_label(block) -> str:
    title = getattr(block.properties, "title", None)
    return title or f"Dataset {str(block.id)[:8]}"


__all__ = ["datasets_page"]

