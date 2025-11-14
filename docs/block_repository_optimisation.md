# Block Repository Optimisation Decisions

## Context

The current `BlockRepository` (`block_data_store/repositories/block_repository.py`) powers the entire persistence layer. Recent spec updates (soft delete filtering, canonical children preservation) increased its complexity: it now handles ORM mapping, filtering DSL, hierarchy validation, graph hydration, resolver wiring, and transaction boundaries in a single class. This all-in-one approach is still workable, but every change requires reasoning about cross-cutting concerns and increases the risk of bugs (e.g., forgetting a visibility join, duplicating hierarchy checks, or triggering N+1 queries when resolving children).

This document summarises optimisation opportunities, orders them by impact, and provides high-level guidance so we can iterate without losing sight of the simplification goals from `AGENTS.md`.

## Prioritised Opportunities

### Update — November 2025

We implemented two of the high-impact items above while chasing Cosmos Postgres performance regressions:

1. **Bulk Postgres upsert** — `BlockRepository.upsert_blocks` now batches every payload in a single `INSERT ... ON CONFLICT DO UPDATE` when the active dialect reports `postgresql`. SQLite still uses `session.merge` for compatibility. This eliminates the per-block round trip that previously made markdown ingestion scale linearly with latency.
2. **Full-root hydration** — `get_block(..., depth=None)` no longer walks the tree recursively issuing child queries. Instead, it loads all rows sharing the same `root_id` in one query and wires them in-memory. This mirrors the recursive CTE idea from opportunity #3 with minimal ORM surgery.

**Trade-offs / risks:**

- The Postgres-specific upsert bypasses SQLAlchemy's identity map, so hooks (`before_update`, `after_insert`) won't fire. If we add such hooks later, we must revisit `_bulk_upsert_postgres` or gate it behind a feature flag.
- Bulk fetching an entire root loads every block into memory; extremely large documents could consume significant RAM. We should consider a streaming/iterative hydrator or depth-aware batching if documents exceed a few thousand blocks.
- Non-Postgres dialects still use `session.merge`, so cross-database performance remains uneven until we introduce SQLite or generic bulk paths.

Keep these caveats in mind when extending the repository or moving more logic into the bulk paths.

### 1. **Shared Filtering & Visibility Helpers (High Impact / Low Effort)**
- **Problem:** `get_block` and `query_blocks` repeat the same structural filter plumbing (`root`, `parent`, `where`, `property_filter`) and visibility joins.
- **Opportunity:** Centralise the CTE/visibility logic and DSL application (e.g., `_visible_cte`, `_apply_filters`, `_apply_related_filters`).
- **Benefit:** Shrinks the public methods, ensures visibility rules are always applied, and makes it easier to extend the query DSL (relationships, group filters) without copy/paste.
- **Status:** Initial helper extraction done (Feb 2025). Further simplification possible by building a small `QueryBuilder` object if/when new filter types arrive.

### 2. **Hierarchy Validation Service (High Impact / Medium Effort)**
- **Problem:** Cycle/root/version checks are duplicated across `set_children`, `move_block`, and `_move_within_session`. Adding new mutation commands would likely reintroduce bugs.
- **Opportunity:** Introduce a `HierarchyValidator` (or reuse `_validate_children_change`) that can validate a batch of mutations once and return hydrated child rows. Long-term, a command object per mutation (`SetChildren`, `MoveBlock`) could encapsulate validation + persistence.
- **Benefit:** Consistent invariants, smaller public methods, clearer extension points for future features (trash/restore subtrees, cloning, derived containers).

### 3. **Resolver & Hydration Efficiency (High Impact / Medium Effort)**
- **Problem:** `_resolve_one` calls back into `get_block` (new session each time), and `_hydrate_subgraph` issues recursive `SELECT ... WHERE id IN (...)` per level.
- **Opportunity:** Keep resolvers strictly cache-bound (no new sessions) and fetch deeper trees using a recursive CTE or batched query. Alternatively, expose a `hydrated_graph = repository.load_tree(id, depth)` API that returns a ready-to-use view object without resolvers.
- **Benefit:** Dramatically fewer SQL round trips, simpler resolver logic, clearer contract for hydration (blocks become read-only snapshots tied to one transaction).

### 4. **Unit-of-Work / Session Boundary (Medium Impact / Medium Effort)**
- **Problem:** Every repository method opens/commits its own session, but complex flows (e.g., `move_block` followed by a read) can’t share a transaction. `_resolve_one` also re-enters the repo with a fresh session.
- **Opportunity:** Provide a Unit of Work context (`with repository.unit_of_work() as uow:`) that hands out a shared session to advanced callers (DocumentStore, future services). Long-term, expose a session-aware resolver factory.
- **Benefit:** Better transactional safety, easier batching of mutations, and fewer chances of observing stale state mid-operation.

### 5. **Responsibility Decomposition (Medium Impact / Higher Effort)**
- **Problem:** One class handles mapping, filtering DSL, hierarchy checking, hydration, and resolver wiring.
- **Opportunity:** Split into focused collaborators as the codebase grows (e.g., `BlockMapper`, `BlockQueryBuilder`, `HierarchyService`, `GraphHydrator`). Start by extracting pure functions/modules; only introduce classes when responsibilities become heavy enough.
- **Benefit:** Code becomes easier to unit-test in isolation and we can evolve each piece without touching unrelated concerns. This aligns with the simplification principle in `AGENTS.md`.

### 6. **Schema Alignment for Children Ordering (Lower Impact / Higher Effort)**
- **Problem:** `children_ids` is a JSON array of strings; every hydration call converts to tuples of UUIDs.
- **Opportunity:** If/when we move to Postgres in production, we can use `ARRAY(UUID)` or normalise into a `block_children` table. For SQLite dev, keep JSON but add helper functions to avoid repeated conversions.
- **Benefit:** Cleaner ORM models, cheaper conversions, opens the door to enforcing referential integrity at the DB layer.

## Next Steps
1. Finish wiring shared helpers (in progress) and add regression tests specifically for filter/helper behaviour.
2. Extract a hierarchy validation helper and reuse it across mutations.
3. Introduce a cache-bound resolver strategy to eliminate recursive repo calls; evaluate a recursive CTE for depth hydration.
4. Revisit this doc once those three are done to decide whether to pursue unit-of-work support or begin decomposing the repository into multiple modules.

Keeping the repository slim today will make the future features (relationships, vector indexing, derived content orchestration) significantly easier to land.
