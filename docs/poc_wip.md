# Block Data Store POC — Plan and Progress
# (Feel free to prune completed items or obsolete notes to keep this file lean.)

This document tracks implementation progress against the Decipher AI specifications and highlights remaining scope.

References
- Full spec: `docs/decipher_full_specification.md`
- POC spec: `docs/decipher_poc_specification.md`

## Current State (2025-11-05)

- **Model layer:** `block_data_store/models/blocks/*.py` now houses per-type block/props classes plus the shared base (`Block`, `BlockType`, `Content`), keeping the implementation modular while aligning with Appendix A’s typed properties/content guidance.
- **Parser & ingestion:** The Mistune-backed pipeline in `block_data_store/parser/markdown_parser.py` converts Markdown headings, paragraphs, bullet lists, and ````dataset:*```` fences into block hierarchies, including derived dataset/record children. Sample source assets under `data/` and the `scripts/demo_ingest.py` helper exercise this flow end-to-end.
- **Persistence & repository:** `block_data_store/db/schema.py` + `db/engine.py` expose SQLAlchemy models, session/engine helpers, and optional persistent SQLite URLs. `block_data_store/repositories/block_repository.py` implements depth-aware `get_block`, structural mutations (`set_children`, `reorder_children`, `move_block`), and quorum validation (duplicate/loop/root guards).
- **Filtering:** `block_data_store/repositories/filters.py` plus repository helpers provide structural `WhereClause`, parent scoping, nested JSON property filters, boolean composition, and operator coverage (`equals`, `not_equals`, `in`, `contains`) aligned with the spec’s filtering section.
- **Tooling, fixtures, and tests:** `tests/` cover repository flows, parser output, engine configuration, renderer output, and DocumentStore-based round trips (`tests/test_round_trip.py`). Postgres runs are supported when `POSTGRES_TEST_URL` or `DATABASE_URL` is set (see `tests/conftest.py`); otherwise tests default to SQLite. Sample data + script (`data/secondary_tree_example.json`, `scripts/load_secondary_tree_example.py`) provide a realistic scenario that can be seeded into SQLite for manual verification alongside notebooks (`notebooks/poc_walkthrough.ipynb`).
- **Document Store seam:** `block_data_store/store/document_store.py` now exposes document fetch helpers plus secondary-tree support via `get_page_group`, resolving `synced` children into canonical blocks while preserving structural metadata.
- **Document Store seam:** `block_data_store/store/document_store.py` now exposes `get_root_tree` (main document) plus slice support via `get_slice`, resolving `synced` children into reusable views while preserving structural metadata; ingestion and one-off block lookups are routed through the store.
- **UI / renderer layers:** Markdown renderer is live and the NiceGUI showcase now walks through navigation, repository-grade filtering (block/parent/root), block inspection, and renderer previews with inline documentation; HTML renderer remains open.
- **Sample content:** `data/poc_long_showcase.md` adds a synthetic, long-form handbook covering headings, nested lists, and multiple datasets to exercise performance and UI behaviour with larger documents.

## Scope Adjustments (POC focus)

- HTML renderer: deferred beyond current POC.
- Extended parser coverage (tables, callouts, page-level constructs): deferred.
- `properties_version` semantics: deferred.
- Secondary-tree authoring/mutations: deferred (read path validated and retained).
- Extra repository invariants hardening: nice-to-have; not required for POC.

## Remaining Scope vs Spec

| Area | Spec reference | Status | Notes / Next Steps |
| --- | --- | --- | --- |
| Model layer / Data Model | Full spec §2 & Appendix A (`docs/decipher_full_specification.md:18-309`) | 🟢 Substantial | Typed property/content models and discriminated block subclasses implemented (incl. repo/parser/test updates); next steps: optional `properties_version` semantics and expanding block coverage as new types emerge. |
| Parser & ingestion | POC spec §2–3 (`docs/decipher_poc_specification.md:13-46`) | ✅ Baseline | Extended coverage (tables/callouts/page-level constructs) deferred; current baseline is acceptable for POC. |
| Repository & DB layer | Full spec Appendix B (`docs/decipher_full_specification.md:318-360`) | ✅ Core | Tests already support Postgres via env var; default remains SQLite. CI job for Postgres is optional and can be added later if needed. |
| Document Store orchestration | Full spec §7 (`docs/decipher_full_specification.md:125-140`) | 🟢 Validated | Façade handles canonical fetches plus page-group/synced resolution; mutations remain out of scope. |
| Secondary trees & synced/page_group blocks | Full spec Appendix A.5 (`docs/decipher_full_specification.md:253-289`) + POC spec objective 2 | 🟢 Validated | Read-side modelling/resolution (page groups + synced refs) is implemented; authoring/mutation flows deferred. |
| Renderer (Markdown) | Full spec §§5 & Appendix D (`docs/decipher_full_specification.md:72-113, 459-517`) + POC deliverables (`docs/decipher_poc_specification.md:69-80`) | 🟢 Ready | Markdown renderer shipped (synced-aware, metadata toggles); HTML renderer deferred. |
| NiceGUI app | POC spec §3 Demonstrations (`docs/decipher_poc_specification.md:37-46`) | 🟡 Prototype | Fresh showcase app seeds documents, presents sidebar navigation + expansion-based walkthrough (overview, filters, inspector, renderer) with inline docs; next: polish copy and add short call-stack examples. |
| Notebook + performance instrumentation | POC spec §§2–3 & Success Criteria (`docs/decipher_poc_specification.md:13-46, 84-92`) | 🟡 Needs follow-through | Capture timings/query counts and validate Postgres parity in notebook + pytest markers. |
| Test suite & performance coverage | POC spec §3 Quality (`docs/decipher_poc_specification.md:48-55`) | 🟡 Partial | Add performance-focused tests/markers; broaden backend coverage via env-configured Postgres runs. |

## Plan (Prioritised Next Work)

1. Performance & metrics: add pytest performance markers and capture timings/query counts for ingestion, fetch depths, filtering, and rendering; summarise in notebook.
2. NiceGUI documentation: inline help for major actions (load, select, edit/save, renderer toggles) and error/empty states.

## Postgres Test Execution

- Tests run against Postgres when either `POSTGRES_TEST_URL` or `DATABASE_URL` is set (see `tests/conftest.py`).
- Without these variables, tests default to in-memory SQLite.
- Example:
  - `export POSTGRES_TEST_URL=postgresql+psycopg://user:pass@localhost:5432/blocks`
  - `pytest -q`

## Not In Scope (POC)

- Vector store integration beyond ensuring no blockers in canonical design.
- Production-grade migrations, full permissions model, and complex caching/indexing.

## Risks and Open Questions

- Performance baselines may fluctuate across backends; pin simple thresholds and review deltas in notebook/CI output.
- Cross-database JSON function parity is only manually verified; continue running the suite with a Postgres URL locally until CI is added (optional).
- UI scope creep remains a concern—NiceGUI should stay minimal and purely for validation while adding just the requested docs/filters.

## Work Log

- 2025-11-05: Added repository-level `RootFilter` support with tests and rebuilt the NiceGUI demo as a guided POC showcase (sidebar tree + documentation-backed expansions for filters, inspector, preview); refreshed the plan to focus on documentation and performance metrics.
- 2025-11-05: Authored `data/poc_long_showcase.md`, a synthetic multi-section handbook that stresses nested lists and datasets to validate parser throughput and UI responsiveness against larger documents.
- 2025-10-25: Completed the typed block/content retrofit, extended DocumentStore for page-group & synced reads, added the secondary-tree sample + loader, delivered the Markdown renderer with unit tests, and added a DocumentStore-driven Markdown round-trip test.
- 2025-10-23: Laid the groundwork with persistence/filtering upgrades (JSON filters, boolean logic, Postgres fixtures) and refreshed the plan to align with the spec.
- 2025-10-29: Reviewed the revised storage-layer summary; flagged that callers still construct/use the repository directly (DocumentStore factories, renderer callbacks, `scripts/load_secondary_tree_example.py`), which conflicts with the “domain service as single entry point” guidance.
- 2025-10-29: Added `create_document_store` factory, routed scripts/tests/renderers (and the walkthrough notebook) through the store API, and refreshed scripts to use `get_root_tree`/`get_slice`, bringing the façade in line with the single-entry storage guidance.
- 2025-10-29: Refactored the Markdown renderer to use component classes with per-block child orchestration and ensured dataset blocks render child records inline, keeping the design aligned with the renderer architecture guidelines.
- 2025-10-29: Reworked the markdown round-trip test to cover multi-level headers and list structures; current renderer/parser output drops list formatting, so additional work is needed to preserve bullets and numbering.
- 2025-10-29: Added bulleted/numbered list item block types, parser translators, and renderer components so Markdown round trips now maintain nested list structure.
- 2025-10-29: Rebuilt the Markdown parser around a simple AST walk that produces Block drafts before materialising typed models, eliminating the translator registry and state machine while keeping dataset/list behaviours intact.
- 2025-10-29: Introduced `apps/nicegui_demo.py`, a NiceGUI prototype that seeds sample Markdown into SQLite, lists documents, visualises the block tree, filters/query results, renders Markdown, and lets users edit block metadata/properties via the DocumentStore.
- 2025-10-29: Expanded the NiceGUI demo with a full-document Markdown preview and on-page walkthrough copy so the UI now showcases renderer output alongside block-level inspection.
- 2025-10-29: Polished the NiceGUI experience by auto-expanding the document tree, adding a content-data editor, reorganising the layout so block/document previews sit together at the bottom, expanding the intro guidance, and exposing a recursive preview toggle.
- 2025-10-29: Retired the Section block in favour of a Heading block with typed levels, removed list-order metadata, normalised textual payloads into `content`, and simplified dataset/record modelling (records now keep key/value pairs in `content.data`), updating the Markdown renderer, NiceGUI demo, and tests accordingly.
