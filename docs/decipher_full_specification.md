# Decipher AI – Core Data Model and Architecture Specification

## 1. Purpose and Vision

This document defines the canonical data model and architecture underpinning Decipher AI. It establishes the foundation for a flexible, block-based system capable of supporting multi-format content, AI workflows, compliance analytics, and knowledge graph functionality, while maintaining strong guarantees for structure, extensibility, and performance.

The goal is to create a unified representation of all content, metadata, and relationships while enabling multiple independent views and AI-native processing.

---

## 2. Core Design Principles

- **Everything is a block:** Documents, sections, paragraphs, datasets, records, pages, and AI chunks are all blocks.
- **Single canonical hierarchy:** Each block has exactly one canonical parent, defining structure, ordering, permissions, and provenance.
- **Secondary non-canonical views:** Additional trees (e.g., page groups, AI chunk groups) are materialised via grouping blocks plus `groups` metadata on canonical content—no duplicated synced nodes.
- **Parent-owned ordering:** Ordering is stored and controlled by the parent via `children_ids`.
- **Payload isolation:** Structural relationships and content payload are separated for clarity and performance.
- **Typed properties, free-form metadata:** Each block subclass defines a **typed ****\`\`**** model**; `metadata` remains open (`dict[str, Any]`) for ad-hoc/AI annotations.
- **Structured, multi-part content:** Blocks carry a \*\*typed \*\*\`\` as a list of content parts (e.g., `text`, `data`, `object`, `blob/url`), enabling multiple payloads per block while persisting as JSON.
- **Renderer layer abstraction:** Blocks are pure data. Rendering (Markdown, HTML, AI context) is handled by pluggable renderer strategies.
- **AI-native by design:** Standardised representations (controlled recursively, by metadata flags) allow AI tools to consume any block.

---

## 3. Block Schema

This schema represents the persisted fields in the database. While the logical model is stable, certain implementation details (such as content encoding and indexing strategy) may evolve as the system matures.

| Field              | Type        | Description                                                                            |   |       |                                                                                                 |
| ------------------ | ----------- | -------------------------------------------------------------------------------------- | - | ----- | ----------------------------------------------------------------------------------------------- |
| `id`               | UUID        | Unique identifier                                                                      |   |       |                                                                                                 |
| `type`             | TEXT        | Block type (document, section, paragraph, dataset, record, page\_group)        |   |       |                                                                                                 |
| `parent_id`        | UUID        | Canonical parent (null for root)                                                       |   |       |                                                                                                 |
| `root_id`          | UUID        | Identifier of the canonical root block (top-level document)                            |   |       |                                                                                                 |
| `workspace_id`     | UUID        | Tenant/workspace scope                                                                 |   |       |                                                                                                 |
| `children_ids`     | UUID[]      | Ordered list of canonical children                                           |   |       |                                                                                                 |
| `version`          | BIGINT      | Monotonic version for conflict control                                                 |   |       |                                                                                                 |
| `created_time`     | TIMESTAMPTZ | Creation timestamp                                                                     |   |       |                                                                                                 |
| `last_edited_time` | TIMESTAMPTZ | Modification timestamp                                                                 |   |       |                                                                                                 |
| `created_by`       | UUID        | Creator id                                                                             |   |       |                                                                                                 |
| `last_edited_by`   | UUID        | Editor id                                                                              |   |       |                                                                                                 |
| `properties`       | JSONB       | Persisted JSON of a typed per-subclass properties model (validated in Model layer)     |   |       |                                                                                                 |
| `metadata`         | JSONB       | Free-form annotations for AI or system use                                             |   |       |                                                                                                 |
| `content`          | JSONB       | Persisted JSON representing a list of content parts, supporting multiple payload types |   | JSONB | **Persisted JSON** of a **typed multi-part content model** (supports text/data/object/blob/url) |



---

## 4. Hierarchical Structure

### Canonical Tree (Primary)

```
[document]
  ├─ [section]
  │    └─ [paragraph]
  └─ [section]
       └─ [paragraph]
```

### Secondary Trees (Non-canonical)

- Defined using `page_group` or `chunk_group` blocks.
- Secondary views attach through `properties.groups`; renderers/query layers collect blocks by group ID to form alternate presentations (pages, chunks, derived collections) without duplicating nodes.
- Enables alternative views without altering canonical source of truth.

---

## 5. Rendering Model

Rendering is handled via a **renderer layer**, not embedded in model logic.

**Render Strategy Interface:**

- Input: Block (or tree), with options: recursive, include\_metadata.
- Output: String or structured representation.
- Examples:
  - `MarkdownRenderer` – generates AI-ready markdown.
  - `HtmlRenderer` – UI display.
  - Future: JSON-LD for graph export.

This approach mirrors Notion’s architecture: blocks represent structure, clients handle presentation.

---

## 6. Filtering and Query Model

Filtering supports analytical use cases across structure and metadata.

### Structural Filtering (`where`)

Filters on block-level attributes:

```json
{"where": {"type": "record", "root_id": "..."}}
```

### Semantic Filtering (`filter`)

Filters on JSON properties:

```json
{"filter": {"property": "category", "select": {"equals": "Preventive"}}}
```

### Combined

```json
{  "where": {"type": "record"},  "filter": {"category": "Preventive"} }
```

Filters may be nested to support JSONB and complex metadata structures.

---

## 7. Architecture Layers

### 1. Model Layer (Pydantic)

- Immutable blocks with ID references only.
- Private resolvers injected at runtime for navigation.
- Subclasses defined via discriminated unions.

### 2. Repository Layer (SQLAlchemy)

- Handles persistence.
- Single source of truth for read/write logic.
- Supports PostgreSQL and SQLite via unified interface.
- Implements `get_block`, `set_children`, `query_blocks` with depth control and version safety.

### 3. Document Store Layer

- Orchestrates operations such as moving blocks, filtering trees, and wiring grouping metadata.
- Contains business rules and validation.

### 4. Renderer Layer

- Separately implemented rendering strategies.
- Enables distinct outputs for AI, UI, export.

---

## 8. Future Extensions

- Relationships as first-class objects (cross-document mapping).
- Version history and time travel.
- Vector embeddings.
- Real-time collaboration and conflict resolution.

---

## 9. Key Benefits

- Scalable, flexible representation for AI workflows.
- Separation of core data model from presentation.
- Enables granular editing, retrieval, and filtering.
- Supports complex analytical use cases across documents.

---

## 10. Next Steps

- Finalise block subclasses.
- Implement core layers.
- Build initial ingestion and rendering pipeline.
- Execute POC to validate all assumptions.

---

# Appendix A: Block Subclass Definitions

## A.1 Overview

Blocks are immutable Pydantic models. Each specific block type declares \*\*typed \*\*` and **typed \*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\***`, while `metadata` remains free-form. Persistence stores `properties`/`content` as JSON; validation happens in the Model layer. Subclasses are discriminated by the `type` field.

## A.2 Typed Content Model (multi-part)

Blocks may contain multiple content payloads simultaneously (e.g., text + data). We model this as a list of discriminated content parts.

```python
class TextPart(BaseModel):
    kind: Literal['text']
    text: str

class DataPart(BaseModel):
    kind: Literal['data']
    data: dict[str, Any]

class ObjectPart(BaseModel):
    kind: Literal['object']
    object: dict[str, Any]

class BlobPart(BaseModel):
    kind: Literal['blob', 'url']
    url: AnyUrl | None = None
    media_type: str | None = None  # e.g., 'image/png', 'application/pdf'

ContentPart = Annotated[Union[TextPart, DataPart, ObjectPart, BlobPart], Field(discriminator='kind')]
```

Each block’s `content` is `list[ContentPart] = []` (empty for structural-only blocks).

## A.3 Typed Properties per Subclass

Properties are schemaful per block subtype. Versions can be tracked with an optional `properties_version: int`.

```python
class DocumentProps(BaseModel):
    title: str
    status: Literal['draft','final'] | None = None

class SectionProps(BaseModel):
    title: str
    anchor: str | None = None  # for stable links

class ParagraphProps(BaseModel):
    role: Literal['body','note','quote'] | None = None
```

## A.4 Base Block Model

```python
class Block(BaseModel):
    id: UUID
    type: str
    parent_id: UUID | None
    root_id: UUID
    workspace_id: UUID
    children_ids: tuple[UUID, ...] = ()
    version: int
    created_time: datetime
    last_edited_time: datetime
    created_by: UUID
    last_edited_by: UUID
    properties: Any  # typed in subclasses
    metadata: dict[str, Any] = {}
    content: list[ContentPart] = []
    properties_version: int | None = None

    _resolve_one: Callable[[UUID | None], 'Block | None'] = PrivateAttr(default=lambda _id: None)
    _resolve_many: Callable[[Iterable[UUID]], list['Block']] = PrivateAttr(default=lambda ids: [])

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    def parent(self) -> 'Block | None':
        return self._resolve_one(self.parent_id) if self.parent_id else None

    def children(self) -> list['Block']:
        return self._resolve_many(self.children_ids)
```

## A.5 Subclasses

```python
class DocumentBlock(Block):
    type: Literal['document']
    properties: DocumentProps

class SectionBlock(Block):
    type: Literal['section']
    properties: SectionProps

class ParagraphBlock(Block):
    type: Literal['paragraph']
    properties: ParagraphProps

class PageGroupProps(BaseModel):
    title: str | None = None

class PageGroupBlock(Block):
    type: Literal['page_group']
    properties: PageGroupProps
```

**Note:** Secondary views are now constructed via grouping blocks (`group_index`, `page_group`, `chunk_group`) combined with the `groups` property on content blocks—no separate synced blocks are required.

## A.6 Discriminated Union

Expose a single union for parsing and type hints:

```python
AnyBlock = Annotated[
    Union[DocumentBlock, SectionBlock, ParagraphBlock, PageGroupBlock],
    Field(discriminator='type')
]
```

## A.7 Invariants

- Exactly one canonical parent (root excluded).
- Parent-owned ordering via `children_ids`.
- `root_id` is the canonical owner document.
- `properties` and `content` are **typed** in code; persisted as JSON.

## A.8 Extensibility

- New block types introduced by adding new `*Props` and optional content parts.
- No DB schema changes required.
- Renderer Layer consumes typed models and may ignore unknown content parts.

---

# Appendix B: Repository and Hydration Strategy

## B.1 Purpose and Scope

The repository layer abstracts persistence logic. It provides a consistent API for interacting with SQLite and Postgres without exposing ORM models to higher layers. This is **not final** and is expected to evolve as performance and complexity considerations increase.

## B.2 Responsibilities

- Persist and retrieve blocks.
- Perform depth-controlled hydration (0, 1, or full tree).
- Inject resolver functions for navigation in Pydantic models.
- Enforce optimistic concurrency via version checks.
- Support structural writes via `set_children`.
- Support structured filtering APIs.

## B.3 Depth-Controlled Hydration

- **depth=0:** return the block only; children resolved on-demand (lazy).
- **depth=1:** pre-load children; grandchildren loaded lazily.
- **depth=None / 'all':** pre-load full tree.

Each call maintains an in-memory cache (`dict[UUID → Block]`) for resolving children and parents efficiently.

## B.4 Example Interface

```python
def get_block(id: UUID, *, depth: int | None = 0) -> AnyBlock:
    """Retrieve a block with optional subtree hydration."""


def set_children(parent_id: UUID, children_ids: Sequence[UUID], *, expected_version: int) -> None:
    """Update parent-owned ordering and increment version."""


def query_blocks(where: dict, filter: dict | None = None) -> list[AnyBlock]:
    """Return blocks filtered by structure and properties."""
```

## B.5 Optimistic Concurrency

Writes require passing the current version. If the stored version does not match, the write is rejected.

## B.6 Backend Compatibility

- SQLite uses JSON1 functions; Postgres uses JSONB operators.
- Filtering logic will be abstracted behind the repository.

## B.7 Future Considerations (Non-final)

- Indexing strategies.
- Batch hydration.
- Caching layers.

---

# Appendix C: Filtering Model Extensions

## C.1 Purpose

Filtering is central to analytical use cases. It must support structural querying (tree position) and semantic querying (properties and metadata). This model will evolve with POC learnings and performance constraints.

## C.2 Structural Filter (`where`)

Examples:

```json
{"where": {"type": "record", "root_id": "..."}}
{"where": {"parent_id": "..."}}
```

## C.3 Property Filter (`filter`)

Supports nested property access via dotted paths or JSON operators.

```json
{"filter": {"property": "category", "equals": "Preventive"}}
```

### Nested example:

```json
{"filter": {"property": "attributes.subtype", "equals": "financial"}}
```

## C.4 Combined Query

```json
{
  "where": {"type": "record", "root_id": "abc"},
  "filter": {"property": "category", "equals": "Preventive"}
}
```

## C.5 Logical Operators (AND / OR)

The filtering model supports compound logical expressions using `and` / `or` keys:

### AND example:

```json
{
  "filter": {
    "and": [
      {"property": "category", "equals": "Preventive"},
      {"property": "status", "equals": "Active"}
    ]
  }
}
```

### OR example:

```json
{
  "filter": {
    "or": [
      {"property": "risk_level", "equals": "High"},
      {"property": "risk_level", "equals": "Critical"}
    ]
  }
}
```

Nested logic is also supported:

```json
{
  "filter": {
    "and": [
      {"property": "category", "equals": "Preventive"},
      {"or": [
        {"property": "status", "equals": "Active"},
        {"property": "status", "equals": "Draft"}
      ]}
    ]
  }
}
```

---

# Appendix D: Renderer Architecture

## D.1 Purpose

Rendering is separated from the data model to allow different consumers (AI, UI, export tools) to generate appropriate views of the same blocks.

## D.2 Design Principles

- Blocks are pure data objects.
- Renderer is a pluggable strategy.
- Rendering may include or exclude metadata and recurse the tree.

## D.3 Renderer Interface (Illustrative, not final)

```python
class Renderer(Protocol):
    def render(self, block: AnyBlock, *, recursive: bool = True, include_metadata: bool = False) -> str:
        ...
```

## D.4 Example Renderer Types

- `MarkdownRenderer`: AI and export-friendly
- `HtmlRenderer`: UI-focused
- Future: JSON-LD or GraphQL representation

## D.5 Future Work

- Styling and theming
- Render performance optimisations
- Support for multimodal content (images, tables, charts)

---

*Note: These appendices are intentionally living documents and designed to evolve with implementation insights.*

# Appendix E: Motivation and Comparison to Notion

## E.1 Why a Block-Based Model

- Existing document platforms are page-centric and not optimised for analytical or AI use cases.
- Decipher requires a model that supports deep semantic understanding, structured extraction, and flexible representation.
- Blocks provide atomicity, enabling granular storage, retrieval, and modification without loading entire documents.

## E.2 Inspired by Notion, Extended for AI

| Aspect     | Notion           | Decipher                    |
| ---------- | ---------------- | --------------------------- |
| Core unit  | Block            | Block                       |
| Hierarchy  | Single canonical | Canonical + secondary trees |
| Data model | UX-first         | AI-first & analytics-first  |
| Rendering  | Client-side      | Pluggable Renderer Layer    |
| AI tooling | Limited          | Native integration          |
| Properties | Mostly flat      | Typed + extensible          |
| Content    | Single payload   | Multi-part payload          |

## E.3 Key Differences

- Decipher introduces explicit **typed properties** and **multi-part content**.
- Decipher treats **secondary groupings** as first-class citizens.
- Rendering is abstracted for AI and downstream automation.
- The model is designed to support compliance obligations and knowledge graphs.

## E.4 Strategic Motivation

- Break content free from document silos.
- Enable consistent ingestion, filtering, analysis, and automated reasoning.

---

# Appendix F: Risks and Limitations

## F.1 Known Risks

- **Query Complexity:** JSONB and nested property filters may impact performance.
- **Secondary Trees:** Introducing multiple hierarchies adds cognitive and technical complexity.
- **Typed Properties Evolution:** Requires versioning strategy.
- **Dual Database Support:** SQLite and Postgres parity must be actively maintained.

## F.2 Implementation Risks

- Complexity may exceed delivery capacity.
- Performance tuning may require caching and indexing layers not included in initial versions.

## F.3 Mitigations

- Start with minimal POC and measure performance.
- Incrementally introduce features.
- Separate core logic from display/AI concerns to maintain flexibility.

## F.4 Future Considerations

- Governance of schema evolution.
- Caching and replication layers.
- API stability over time.
