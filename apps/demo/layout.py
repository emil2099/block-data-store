"""Reusable layout helpers for the NiceGUI demo."""

from __future__ import annotations

from contextlib import contextmanager

from nicegui import ui

_NAV_LINKS = [
    ("Home", "/"),
    ("Documents", "/documents"),
    ("PDF Pages", "/pdf"),
    ("Canonical Tree", "/tree"),
    ("Datasets", "/datasets"),
]


def _nav_bar(current: str) -> None:
    with ui.header().classes("bg-slate-900 text-white shadow-sm"):
        with ui.row().classes("w-full items-center justify-between px-6 py-3"):
            ui.link(text="Block Data Store Demo", target="/").classes(
                "text-lg font-semibold no-underline text-white"
            )
            with ui.row().classes("gap-4"):
                for label, href in _NAV_LINKS:
                    is_current = href == current
                    classes = "text-white no-underline"
                    if not is_current:
                        classes = "text-white/70 hover:text-white no-underline"
                    ui.link(text=label, target=href).classes(
                        classes + (" font-semibold" if is_current else "")
                    )


@contextmanager
def page_frame(
    *,
    current: str,
    title: str,
    subtitle: str | None = None,
) -> None:
    """Render shared navigation and yield a central content column."""

    _nav_bar(current)
    with ui.column().classes("max-w-6xl mx-auto w-full gap-4 py-8 px-4"):
        ui.label(title).classes("text-3xl font-semibold text-slate-900")
        if subtitle:
            ui.label(subtitle).classes("text-slate-500")
        yield


def stat_card(label: str, value: str, *, href: str | None = None) -> None:
    with ui.card().classes("p-4 min-w-[180px] bg-white shadow-sm"):
        ui.label(value).classes("text-3xl font-semibold text-slate-900")
        if href:
            ui.link(text=label, target=href).classes("text-slate-500 no-underline hover:underline")
        else:
            ui.label(label).classes("text-slate-500")


__all__ = ["page_frame", "stat_card"]
