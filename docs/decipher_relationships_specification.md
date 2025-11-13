# Relationships Specification

# **Architectural Overview: The Decipher Relationship Model**

**Version:** 1.0

**Status:** Adopted

## 1. Objective and Use Cases

The Decipher Block Model provides a robust canonical hierarchy for content. However, to build a true knowledge graph and support advanced analytical workflows, the system must be able to represent explicit, queryable links that cut *across* these hierarchies.

The purpose of this document is to define a simple, robust, and elegant model for creating first-class relationships between any two blocks in the system. This model will serve as the foundation for linking content, tracking provenance, and enabling complex, graph-based queries.

### Key Use Cases:

- **Linking AI Extractions to Source Content:** An ObjectBlock representing an extracted "Obligation" is derived from a semantic chunk of a source document. The relationship model can link this ObjectBlock directly to the chunk_group block that represents the source text, providing clear provenance for AI-generated data. For even greater precision, it could link to the specific ParagraphBlock within that chunk.
- **Connecting Compliance and Policy Documents:** A DocumentBlock representing an internal "Data Protection Policy" needs to be linked to the external "GDPR Regulation" DocumentBlock that it supports.
- **Building Knowledge Graphs:** A RecordBlock for a "Risk" in a dataset can be linked to multiple RecordBlocks representing "Controls" that mitigate it.
- **Cross-Document Referencing:** A specific ParagraphBlock in one contract can reference a specific HeadingBlock in a master services agreement, creating a durable link that is independent of the parent-child structure.

## 2. Core Principles

The design of the relationship model is guided by the same principles of clarity, scalability, and integrity that underpin the Block Model.

- **Relationships are First-Class Citizens:** A relationship is its own distinct entity, not merely an attribute of a block. This allows relationships to have their own identity, metadata, and lifecycle.
- **Directed in Logic, Canonical in Storage:** All relationships are treated as semantically directional (a source connects to a target with a type or "verb"). The persistence layer, however, may store these in a canonical, non-directional format for efficiency and uniqueness.
- **Integrity and Consistency Above All:** The model guarantees that relationships cannot point to non-existent or inaccessible blocks. It fully respects the hierarchical soft-delete and permissions models of the block system.
- **Simplicity by Default:** The initial implementation prioritizes simplicity and flexibility, deferring complex features like typed properties or soft deletes for relationships until a clear need arises.

## 3. The Solution: A First-Class Relationship Model

The solution is to create a dedicated relationships table in the database. Each row in this table represents a single, durable link (an "edge") between two blocks (the "nodes"). This approach cleanly separates the concern of *content* (Blocks) from the concern of *connection* (Relationships), providing a scalable and performant foundation for all relational queries.

## 4. Base Relationship Schema

This schema defines the fields that are persisted to the database for every relationship.

| **Attribute** | **Data Type** | **Description** |
| --- | --- | --- |
| id | UUID | A globally unique identifier for the relationship itself. |
| workspace_id | UUID | The identifier for the tenant/workspace. Ensures data scoping. **FK to workspaces**. |
| block_id_a | UUID | The ID of the first block in the relationship's canonical pair. **FK to blocks.id**. |
| block_id_b | UUID | The ID of the second block in the relationship's canonical pair. **FK to blocks.id**. |
| rel_type | TEXT | A string literal defining the semantic type (the "verb") of the relationship (e.g., 'derived_from', 'supports', 'references'). |
| metadata | JSONB | A flexible JSON object for storing free-form annotations or application-specific data about the relationship. |
| version | BIGINT | A monotonic version number for optimistic concurrency control. |
| created_time | TIMESTAMPTZ | The timestamp when the relationship was created. |
| last_edited_time | TIMESTAMPTZ | The timestamp of the last modification. |
| created_by | UUID | The ID of the user or process that created the relationship. |
| last_edited_by | UUID | The ID of the user or process that last edited the relationship. |

## 5. Key Architectural Mechanics and Behaviors

### 5.1. Directionality and Canonical Storage

While relationships are logically directional, they are stored canonically to prevent duplicates and simplify querying.

- **Logical Model (Domain Service):** The application API always operates in terms of a source block, a target block, and a type. Example: create_relationship(source: BlockX, target: BlockY, type: 'supports').
- **Storage Model (Repository):** Before persisting, the two block IDs are ordered into a canonical pair (e.g., sorted lexicographically). The result is stored as block_id_a and block_id_b. This ensures that a (Y, X, 'supports') relationship cannot be created if a (X, Y, 'supports') relationship already exists.

### 5.2. Integrity with Block Soft Deletes

The relationship model fully respects the cascading soft-delete contract defined in the Block Specification.

> A relationship is only considered "visible" or "active" if both of its endpoint blocks have `in_trash = FALSE`.
> 

Because the Domain Service now cascades delete/restore operations to every descendant block, visibility checks no longer require recursive ancestry lookups. Repository queries simply join relationships to the two endpoint blocks and apply `WHERE blocks.in_trash = FALSE` on each side before returning results. Administrative views that need to reason about trashed data can opt into `include_trashed` semantics explicitly.

### 5.3. Relationship Lifecycle (Deletion)

For the initial implementation (V1), relationships will be **hard-deleted**.

- When a relationship is deleted, its row is permanently removed from the relationships table via a DELETE statement.
- **Automatic Deletion:** To prevent dangling references, the block_id_a and block_id_b columns must have a Foreign Key constraint on the blocks table with an ON DELETE CASCADE rule. If a block is permanently deleted from the database, all relationships connected to it will be automatically and instantly removed.

### 5.4. Uniqueness

To prevent redundant data, a relationship is considered unique based on the two blocks it connects and its semantic type. This will be enforced by a UNIQUE constraint in the database on the composite key: (block_id_a, block_id_b, rel_type).

### 5.5. Permissions and Visibility

A user's ability to see a relationship is governed by their permissions on the blocks it connects.

> A relationship is only visible to a user if that user has read permissions for both of the blocks it connects.
> 

This rule is a critical security constraint and must be enforced within the Domain Service layer before returning relationship data to any user or client.

## 6. API Layer Abstraction (The Domain Service)

The Domain Service will be the single entry point for all relationship operations, ensuring all business rules, validation, and integrity checks are consistently applied.

**Key Methods:**

- create_relationship(source_block_id, target_block_id, type, metadata)
- get_relationships(block_id, direction='all')
- delete_relationship(source_block_id, target_block_id, type)

## 7. Risks and Mitigations

### 7.1. Risk: Cascading Write Cost

- **Risk:** Deleting or restoring a block with thousands of descendants requires a multi-row update, which can introduce momentary write latency compared to the previous single-row toggle.
- **Mitigation:** Deletes remain a rare operation. The Domain Service batches the affected IDs and performs a single transactional update, ensuring consistency while containing the runtime cost. Monitoring will be added around long-running cascades so we can revisit chunking or background execution if workloads demand it.

### 7.2. Risk: Semantic Ambiguity of rel_type

- **Risk:** The use of a free-form TEXT field for rel_type could lead to inconsistency (e.g., derived_from, derivedFrom, source_of). This can make reliable querying difficult.
- **Mitigation:** This will be managed at the application level. The Domain Service should use a predefined set of enumerated constants or a simple schema registry for rel_type values to ensure consistency across the platform.

## 8. Future Considerations (Deferred for V1)

To ensure a lean and robust initial implementation, the following features have been explicitly deferred:

| **Feature** | **Description** | **Rationale for Deferral** |
| --- | --- | --- |
| **Soft Deletes for Relationships** | Adding an in_trash flag to the relationships table to make deletions reversible. | The primary need for soft-delete is to protect content (blocks). The cost of recreating a link is low, so the added complexity is not justified for V1. |
| **Typed Properties for Relationships** | A formal, schema-based properties field, similar to the one on blocks. | A flexible metadata field is sufficient for initial use cases. This avoids creating a parallel, complex type system for relationships. |
| **Database-Enforced Cardinality** | Rules at the database level to enforce one-to-one or one-to-many relationships. | Cardinality is a business rule, not a data-integrity rule. Enforcing it in the Domain Service provides greater flexibility without requiring schema changes. |
