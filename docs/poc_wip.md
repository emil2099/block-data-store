# Block Data Store POC — Plan and Progress
# (Feel free to prune completed items or obsolete notes to keep this file lean.)

This document tracks implementation progress against the Decipher AI specifications and highlights remaining scope.

References
- Full spec: `docs/decipher_full_specification.md`
- POC spec: `docs/decipher_poc_specification.md`

## Current State (2025-10-25)

- **Model layer:** `block_data_store/models/blocks/*.py` now houses per-type block/props classes plus the shared base (`Block`, `BlockType`, `Content`), keeping the implementation modular while aligning with Appendix A’s typed properties/content guidance.
- **Parser & ingestion:** The Mistune-backed pipeline in `block_data_store/parser/markdown_parser.py` converts Markdown headings, paragraphs, bullet lists, and ````dataset:*```` fences into block hierarchies, including derived dataset/record children. Sample source assets under `data/` and the `scripts/demo_ingest.py` helper exercise this flow end-to-end.
- **Persistence & repository:** `block_data_store/db/schema.py` + `db/engine.py` expose SQLAlchemy models, session/engine helpers, and optional persistent SQLite URLs. `block_data_store/repositories/block_repository.py` implements depth-aware `get_block`, structural mutations (`set_children`, `reorder_children`, `move_block`), and quorum validation (duplicate/loop/root guards).
- **Filtering:** `block_data_store/repositories/filters.py` plus repository helpers provide structural `WhereClause`, parent scoping, nested JSON property filters, boolean composition, and operator coverage (`equals`, `not_equals`, `in`, `contains`) aligned with the spec’s filtering section.
- **Tooling, fixtures, and tests:** `tests/` now cover repository flows, parser output, engine configuration, renderer output, and DocumentStore-based round trips (`tests/test_round_trip.py`). `tests/conftest.py` optionally points at Postgres, though we still trigger SQLite by default. Sample data + script (`data/secondary_tree_example.json`, `scripts/load_secondary_tree_example.py`) provide a realistic scenario that can be seeded into SQLite for manual verification alongside notebooks (`notebooks/poc_walkthrough.ipynb`).
- **Document Store seam:** `block_data_store/store/document_store.py` now exposes document fetch helpers plus secondary-tree support via `get_page_group`, resolving `synced` children into canonical blocks while preserving structural metadata.
- **Document Store seam:** `block_data_store/store/document_store.py` now exposes `get_root_tree` (main document) plus slice support via `get_slice`, resolving `synced` children into reusable views while preserving structural metadata; ingestion and one-off block lookups are routed through the store.
- **UI / renderer layers:** Renderer strategies, secondary-tree handling, and the NiceGUI UI are still missing; the nascent document-store façade only covers canonical trees, so most higher-level orchestration remains unimplemented.

## Design Deviation Alerts (spec drift watchlist)

- **Typed block subclasses & multi-part content** (full spec §2 + Appendix A): Core support exists, but we still need to enforce `properties_version` semantics and stay disciplined as new block types arrive.
- **Secondary trees & synced/page_group blocks** (full spec Appendix A.5; POC spec §2): Read-side resolution is live (DocumentStore + renderer coverage); authoring/mutation flows are deferred beyond the POC scope.
- **Renderer + NiceGUI deliverables** (POC spec §§2–3 & Deliverables table): Markdown renderer is done and the NiceGUI prototype now exercises the document store end to end; HTML output still needs implementation to complete the renderer stack.

## Remaining Scope vs Spec

| Area | Spec reference | Status | Notes / Next Steps |
| --- | --- | --- | --- |
| Model layer / Data Model | Full spec §2 & Appendix A (`docs/decipher_full_specification.md:18-309`) | 🟢 Substantial | Typed property/content models and discriminated block subclasses implemented (incl. repo/parser/test updates); next steps: optional `properties_version` semantics and expanding block coverage as new types emerge. |
| Parser & ingestion | POC spec §2–3 (`docs/decipher_poc_specification.md:13-46`) | ✅ Baseline | Extend coverage for tables/callouts/page-level constructs and emit placeholders for secondary trees so downstream layers can validate them. |
| Repository & DB layer | Full spec Appendix B (`docs/decipher_full_specification.md:318-360`) | ✅ Core | Keep strengthening invariants, add Postgres CI runs, and prepare to offload orchestration into a Document Store façade. |
| Document Store orchestration | Full spec §7 (`docs/decipher_full_specification.md:125-140`) | 🟢 Validated | Façade handles canonical fetches plus page-group/synced resolution; future mutation tooling can wait until post-POC feature work. |
| Secondary trees & synced/page_group blocks | Full spec Appendix A.5 (`docs/decipher_full_specification.md:253-289`) + POC spec objective 2 | 🟢 Validated | Read-side modelling/resolution (page groups + synced refs) is implemented via DocumentStore; no further mutation flows are required for the POC. Focus shifts to renderer/UI consumers. |
| Renderer (Markdown + HTML) | Full spec §§5 & Appendix D (`docs/decipher_full_specification.md:72-113, 459-517`) + POC deliverables (`docs/decipher_poc_specification.md:69-80`) | 🟡 Markdown ready | Markdown renderer shipped (synced-aware, metadata toggles); HTML renderer + UI wiring still pending. |
| NiceGUI app | POC spec §3 Demonstrations (`docs/decipher_poc_specification.md:37-46`) | 🟡 Prototype | `apps/nicegui_demo.py` seeds sample Markdown, lists documents, shows the block tree, filters, renders Markdown, and edits metadata/properties; next steps: wire in HTML renderer once available and add smoke tests. |
| Notebook + performance instrumentation | POC spec §§2–3 & Success Criteria (`docs/decipher_poc_specification.md:13-46, 84-92`) | 🟡 Needs follow-through | Upgrade `notebooks/poc_walkthrough.ipynb` to run the full lifecycle, capture timings/query counts, and validate Postgres parity. |
| Test suite & performance coverage | POC spec §3 Quality (`docs/decipher_poc_specification.md:48-55`) | 🟡 Partial | Add tests for secondary trees, renderer output, document-store orchestration, and concurrency/performance baselines (including Postgres runs). |

## Plan (Prioritised Next Work)

1. **HTML renderer + formatting polish:** Mirror the Markdown renderer’s coverage for HTML output, ensuring parity for synced refs/metadata toggles.
2. **NiceGUI polish + HTML wiring:** Hook the UI into the upcoming HTML renderer, add minimal smoke tests, and document how to launch the demo.
3. **Notebook + performance instrumentation:** Finalise the Jupyter walkthrough, capture timings/query counts, and run side-by-side SQLite/Postgres exercises.
4. **Testing & observability expansion:** Extend pytest coverage for renderers/UI adapters and automate Postgres runs to ensure portability.

## Not In Scope (POC)

- Vector store integration beyond ensuring no blockers in canonical design.
- Production-grade migrations, full permissions model, and complex caching/indexing.

## Risks and Open Questions

- Secondary-tree + renderer scope is still ahead; without it we cannot meet the “Markdown → Renderer → UI” success criteria.
- Cross-database JSON function parity is only manually verified; automated Postgres coverage is required before we can trust portability claims.
- UI scope creep remains a concern—NiceGUI should stay minimal and purely for validation.

## Work Log

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
