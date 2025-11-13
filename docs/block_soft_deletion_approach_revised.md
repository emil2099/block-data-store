# Deletes logic

# Adoption of Cascading Soft-Delete Model

**Date:** 2025-11-13 **Status:** Accepted

## 1. Context

The system was initially designed with a non-cascading soft-delete model, as documented in `decipher_block_specification.md` (section 12.1). This model flags only the target block with `in_trash = TRUE`, relying on read-time queries to recursively check the `in_trash` status of a block's entire parental hierarchy.

This decision was made to optimize for write-speed, making delete and restore operations instantaneous (a single-row update).

However, this has created a significant architectural problem:

1. **Application Profile Mismatch:** Our application is **read-heavy** and **delete-rare**. The current model optimizes our rarest operation (deletes) at the expense of our most frequent operation (reads).
2. **Pervasive Read Complexity:** Every query that fetches blocks, relationships, or search results must perform a complex and computationally expensive recursive query (e.g., a Recursive Common Table Expression) to check for "implicit" deletion.
3. **Compounding Complexity:** This read-time complexity "leaks" into all other systems. As noted in `decipher_relationships_specification.md`, this creates a major performance risk for relationship queries. This same complexity will slow down filtering, search, and vector index queries.

## 2. Decision

We will **replace** the non-cascading model with a **cascading soft-delete model**, similar to that used by Notion.

This new model is defined as follows:

1. **On Delete:** When a parent block is deleted, its `in_trash` flag will be set to `TRUE`. This operation will **cascade** to all descendant blocks, which will also have their `in_trash` flags explicitly set to `TRUE`.
2. **On Restore:** When a block is restored from the trash, its `in_trash` flag will be set to `FALSE`. This operation will also **cascade** to all descendant blocks, setting their flags to `FALSE`.
3. **Implementation:** The orchestration of this cascade (i.e., finding all descendants and commanding the update) will be the responsibility of the **Domain Service**, in line with its role of enforcing business logic as defined in `decipher_storage_layers_summary.md`.

## 3. Consequences

This decision moves the system's complexity from read-time to write-time, which aligns with our application's operational profile.

### Positive Consequences

- **Massively Simplified Read Logic:** All hierarchy-aware recursive CTEs for deletion checking are eliminated. A block's visibility is determined by a simple, non-recursive `WHERE in_trash = false`.
- **Improved Read Performance:** Read operations (for blocks, relationships, search, filters) will become significantly faster and less resource-intensive.
- **Reduced System-wide Complexity:** The performance risk identified in `decipher_relationships_specification.md` is fully mitigated. Future features (vector search, etc.) will not need to implement complex, hierarchy-aware logic.
- **Correct Alignment of Concerns:** The complexity of the delete operation is moved into the **Domain Service**, which is designed to handle such business logic. The **Repository** layer becomes simpler and faster, aligning with its defined purpose.

### Negative Consequences

- **Slower Write Operations:** Deleting or restoring a block with a large number of descendants (e.g., 10,000) will no longer be an instantaneous, single-row update. It will now be a multi-row update, which will take longer.
- **Justification:** This is an acceptable and intentional trade-off. The performance cost is paid once by a rare operation, which in turn benefits all frequent read operations.

## 4. Action Items

1. **Modify Domain Service:** Update the `delete_block` and `restore_block` (or equivalent) methods in the Domain Service to find all descendants of a target block and orchestrate a batch update of their `in_trash` status.
2. **Audit Repository Layer:** Audit all `Repository` read methods (e.g., `get_block_children`, `get_relationships_for_block`) to remove all recursive CTEs related to `in_trash` checks.
3. **Update Repository Layer:** Replace the complex logic with a simple `WHERE blocks.in_trash = false` filter.
4. **Update Documentation:** Section 12.1 of `decipher_block_specification.md` must be rewritten to reflect this new decision. The "Risks" section of `decipher_relationships_specification.md` must be updated to remove the mitigated performance risk.