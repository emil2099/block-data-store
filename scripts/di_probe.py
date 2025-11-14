"""Quick helper to inspect Azure DI AnalyzeResult payloads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from block_data_store.parser import AzureDiConfig, analyze_with_cache


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to the document to inspect")
    parser.add_argument("--model-id", default="prebuilt-layout", help="Azure DI model id")
    parser.add_argument(
        "--content-format",
        default="markdown",
        choices=["markdown", "text"],
        help="Content format to request from Azure DI",
    )
    parser.add_argument(
        "--save-json",
        type=Path,
        help="Optional path to store the minimal AnalyzeResult payload",
    )
    parser.add_argument(
        "--page-preview",
        type=int,
        default=2,
        help="How many page excerpts to print",
    )
    args = parser.parse_args()

    config = AzureDiConfig(model_id=args.model_id, content_format=args.content_format)
    payload = analyze_with_cache(args.path, config=config)

    _print_summary(payload, max_pages=args.page_preview)

    if args.save_json:
        args.save_json.parent.mkdir(parents=True, exist_ok=True)
        args.save_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Saved payload to {args.save_json}")


def _print_summary(payload: dict, *, max_pages: int) -> None:
    content = payload.get("content", "") or ""
    pages = payload.get("pages", []) or []
    print(f"Model: {payload.get('model_id') or 'unknown'}")
    print(f"Pages reported: {len(pages)}")
    for index, page in enumerate(pages[: max_pages], start=1):
        spans = page.get("spans") or []
        if not spans:
            print(f"- Page {index}: no spans")
            continue
        span = spans[0]
        offset = int(span.get("offset", 0))
        length = int(span.get("length", 0))
        excerpt = content[offset : offset + min(length, 200)]
        excerpt = excerpt.replace("\n", " ").strip()
        print(f"- Page {index}: offset={offset} length={length} excerpt={excerpt[:120]!r}")


if __name__ == "__main__":  # pragma: no cover - CLI helper
    main()

