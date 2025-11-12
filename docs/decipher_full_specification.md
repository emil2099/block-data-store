# Decipher AI – Core Data Model and Architecture Specification

## Purpose & Vision
This document captures the foundational intent behind Decipher’s block-based content platform—to unify every piece of structured information into a single, AI-native fabric—while preserving clarity about why the system exists and how the major layers collaborate. Individual concerns (block schema, renderers, storage, grouping) have their own focused documents so they can evolve independently, but this spec should help readers understand the story before diving into the details.

## Who This Is For
- Product and architecture stakeholders who need the “why” and the big picture.
- Engineers who want guardrails, invariants, and a reliable mental model before reading implementation details.
- Contributors creating parsers, renderers, or storage adapters that must align with the canonical model.

## How To Read This
- Skim Purpose, Principles, and the End-to-End Example to build intuition.
- Use Block Model Summary, Hierarchy & Grouping, and Filtering sections as your day‑to‑day reference for invariants and data flow.
- Jump to companion docs when you need specifics:
  - Canonical schema and block types → `docs/decipher_block_specification.md`
  - Grouping model (pages/chunks) → `docs/decipher_block_grouping_model.md`
  - Renderer architecture → `docs/decipher_renderer_architecture.md`
  - Storage responsibilities → `docs/decipher_storage_layers_summary.md`

## Non‑Goals (What This Document Does Not Do)
- Define every field of every block type (that lives in Block Specification).
- Prescribe a single renderer or UI framework.
- Lock us to a specific database engine, indexing strategy, or deployment topology.

## Vision & Motivation
- **Unify every representation of content** (documents, datasets, annotations, derived views) into one typed block hierarchy so AI and analytical workflows can reason over it uniformly.
- **Stabilize the core model**: the canonical tree, typed blocks, and decoupled renderers make it safe to extend ingestion paths, groupings, and tooling without bending the schema.
- **Orient readers quickly**: describe the “why” and the high-level interactions so newcomers can find the right companion doc (`docs/decipher_block_specification.md`, `docs/decipher_renderer_architecture.md`, etc.) for implementation details.

## Core Design Principles
- **Everything is a block:** documents, sections, paragraphs, records, groups, and derived artifacts all share the same envelope.
- **Single canonical hierarchy:** each block has exactly one parent; ordering is owned by that parent via `children_ids`, ensuring deterministic structure, permissions, and provenance.
- **Secondary views via tagging:** page/chunk/group blocks live alongside the canonical tree; canonical blocks simply tag their `properties.groups` to participate in alternate traversals.
- **Payload isolation:** relationships, schemaful `properties`, free-form metadata, and multi-part `content` are each stored separately so renderers, indexers, and analytics can pick what they need.
- **Renderer layer abstraction:** blocks stay pure data while separate renderer strategies (Markdown, HTML, AI contexts, etc.) consume hydrated trees.

## End‑to‑End Example (From PDF Page To AI Chunk)
- Parser ingests a PDF and emits a canonical tree (document → sections → paragraphs/lists) plus `page_group` blocks ordered under a `page_group_index`.
- Canonical content blocks set `properties.groups = [page-uuid,...]` for each page they appear on (split paragraphs can reference multiple pages).
- Document Store persists the graph through the Domain Service, which enforces single-parent and parent-owned ordering invariants.
- A chunking job creates `chunk_group` blocks and tags participating canonical blocks via `properties.groups`. No nodes are duplicated.
- Renderer asks for “Chunk 12” → repository fetches blocks tagged with that group → result is sorted by canonical order → renderer walks the hydrated tree to produce Markdown/HTML/AI context.

## Block Model Summary
Every entity uses the same persistence envelope: `id`, `type`, workspace/root/parent identifiers, `children_ids`, concurrency/versioning timestamps, typed `properties`, flexible `metadata`, and multi-part `content`. Some highlights:
- `properties`: schemaful attributes (including `groups` membership) defined by each block subclass in `docs/decipher_block_specification.md`.
- `metadata`: open annotations, embeddings, AI outputs, or audit flags.
- `content`: typed payload pieces (text, structured object, tabular data, blobs) so multiple consumers can choose the best format.

The canonical schema and the current base block types (documents, sections, paragraphs, datasets, groups, etc.) are documented in `docs/decipher_block_specification.md`.

## Hierarchy & Grouping
- **Canonical tree:** the single source of truth for structure, order, navigation, and access control. Every operation that changes parent/children relationships runs through the Domain Service so invariants are preserved.
- **Secondary trees:** page groups, chunk groups, and other derived views are built by tagging canonical blocks with group IDs rather than duplicating nodes. Queries gather the canonical blocks for a group and then reorder them by the canonical hierarchy when rendering. See `docs/decipher_block_grouping_model.md` for the current strategy.

### Invariants Checklist (must hold at all times)
- Exactly one canonical parent per block (roots excluded).
- Parent owns ordering via `children_ids`; no child stores its own index.
- `root_id` identifies the canonical root document for every descendant.
- Group membership is expressed only via `properties.groups` (UUIDs of group blocks); no synced duplicate nodes.
- Writes that change structure must pass optimistic concurrency checks (version).

## Rendering Model
Rendering happens entirely outside the model. Renderer engines dispatch on block type, accept configuration (recursive rendering, metadata inclusion, theming), and walk hydrated trees via injected dispatcher references. This keeps the core model stable while allowing Markdown, HTML, UI, AI-prompt, or future graph outputs to coexist. The renderer contract and examples live in `docs/decipher_renderer_architecture.md`.

## Filtering & Query Model
Filtering supports both structural constraints (`where` clauses on block attributes such as `type`, `root_id`, `parent_id`) and semantic filtering across JSON properties (`filter` clauses, nested paths, logical `and`/`or` compositions). The repository layer bridges SQLite/Postgres differences (JSON1 vs JSONB) and exposes unified APIs for analytical queries and derived views while respecting the canonical tree.

### Example Queries
- Structural: `{"where": {"type": "paragraph", "root_id": "..."}}`
- Semantic: `{"filter": {"property": "category", "equals": "Preventive"}}`
- Combined: `{ "where": {"type": "record"}, "filter": {"property": "status", "equals": "Active"} }`

## Architecture Layers
1. **Document Store:** orchestrates ingestion (Markdown, datasets, PDFs, etc.), enforces grouping metadata, and coordinates derived processing (AI chunking, dataset extraction). It wires parsers into block graphs and delegates rendering/export requests.
2. **Domain Service:** public-facing API that enforces invariants (single parent, parent-owned ordering, valid groups, version control), sequences multi-block writes, triggers side effects (caches, vector indexes), and returns hydrated domain models.
3. **Repository:** internal persistence adapter that executes SQLAlchemy queries, hydrates hierarchies (depth-controlled), batches writes, and maintains optimistic concurrency. It never includes business logic or side effects.
4. **Renderer & Consumers:** separate strategies that accept hydrated trees and produce AI prompts, UIs, exports, or derived analytics. They rely on the canonical model’s typed blocks but stay agnostic to persistence.

For more about storage responsibilities and the Domain Service/Repository contract, see `docs/decipher_storage_layers_summary.md`.

## Design Trade‑offs (Why This Shape)
- **Tags over synced secondary trees:** avoids duplication, reduces drift, and uses canonical order to render any view; trades for sorting work at query/render time.
- **Pluggable renderer vs embedded formatting:** keeps model stable and AI‑friendly; trades for explicit orchestration when rendering.
- **Typed properties with free‑form metadata:** balances schema validation with space for AI annotations; trades for careful versioning of property schemas.

## Glossary
- **Canonical tree:** the authoritative hierarchy of content blocks (single parent, parent‑owned order).
- **Group block:** an anchor block (e.g., `page_group`, `chunk_group`) that represents a secondary view; canonical blocks reference it via `properties.groups`.
- **Hydration:** loading a block and some or all of its descendants/ancestors into memory so traversals are local and deterministic.
- **Renderer engine:** dispatcher that maps block types to components and recurses to produce output.

## Future Extensions & Benefits
- Supports relationships as first-class entities, version histories, vector embeddings, and real-time collaboration because the canonical model remains stable.
- Separation of concerns (model vs renderer vs persistence) simplifies adoption, testing, and evolution.
- Typed blocks with multi-part content make AI prompting and analytical queries predictable without brittle conversions.

## Supporting References
1. **Canonical block schema and type system:** `docs/decipher_block_specification.md`
2. **Grouping model for pages, chunks, and domains:** `docs/decipher_block_grouping_model.md`
 3. **Renderer architecture and dispatcher pattern:** `docs/decipher_renderer_architecture.md`
4. **Layered storage responsibilities:** `docs/decipher_storage_layers_summary.md`

## Version Control Table
| Date | Version | Summary | Reference |
| --- | --- | --- | --- |
| 2025-11-12 | 2.3 | Restored motivation, principles, and layer descriptions while keeping the details in companion specs. | `docs/decipher_block_specification.md`, `docs/decipher_block_grouping_model.md`, `docs/decipher_renderer_architecture.md`, `docs/decipher_storage_layers_summary.md` |
| 2025-11-12 | 2.4 | Added audience/reading guide, non‑goals, end‑to‑end example, invariants checklist, trade‑offs, glossary, and query examples. | Same as above |
