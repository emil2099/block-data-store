"""Entry point for the modular NiceGUI demo."""

from __future__ import annotations

from pathlib import Path
import sys

from nicegui import ui

# Allow running as ``python apps/demo/main.py`` by ensuring the repo root is on sys.path.
if __package__ in {None, ""}:  # pragma: no cover - runtime convenience
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from apps.demo import pages  # noqa: F401
else:  # pragma: no cover - normal package import
    from . import pages  # noqa: F401


def main() -> None:  # pragma: no cover - UI wiring
    ui.run(title="Block Data Store Demo")


if __name__ in {"__main__", "__mp_main__"}:  # pragma: no cover - CLI entry
    main()
