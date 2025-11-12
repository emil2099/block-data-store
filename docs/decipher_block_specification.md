# Decipher Block Specification

## 1. Objective

The purpose of this document is to define the minimal and definitive set of Block types required to deliver all of Decipher's use cases, from document ingestion and analysis to AI-driven workflows and knowledge extraction.

This specification serves as the canonical source of truth for the block data model. It builds upon the foundational concepts in the "Core Data Model and Architecture Specification" and provides the concrete details needed for implementation. As our thinking evolves, this document will be updated to reflect the most current design decisions.

## 2. Core Principles

The design of our block model is guided by a few core principles that ensure flexibility, scalability, and clarity.

- **Everything is a Block:** All content and structure—documents, sections, paragraphs, data records, and even secondary groupings—are represented as a unified block type.
- **Single canonical hierarchy:** Every block has exactly one primary parent, creating a clear and reliable structure for ordering, permissions, and data provenance. Secondary views and groupings are built on top of this stable foundation.
- **Separation of concerns:** The model cleanly separates:
    - **Typed properties:** Schema-based, validated attributes specific to each block type.
    - **Free-form metadata:** Flexible, unvalidated annotations for AI, system and user-generated attributes.
    - **Multi-representation content:** The actual data payload of the block.
- **Renderer abstraction:** Blocks are pure data structures. Their presentation (as Markdown, HTML, or an AI prompt) is handled by a separate, pluggable renderer layer, not by the model itself. Blocks must remain render-agnostic.
- **Order and indent are controlled by parent:** The hierarchy defines both the level of each block (and therefore indent) and the order of elements (as controlled by children_id array).

## 3. Base Block Schema

All specific block types inherit from this single, consistent base schema. This table defines the fields that are persisted to the database for every block, regardless of its type.

| **Attribute** | **Data Type** | **Description** |
| --- | --- | --- |
| id | UUID | A globally unique identifier for the block. |
| type | TEXT | The string literal identifying the block's type (e.g., 'paragraph', 'record'). |
| workspace_id | UUID | The identifier for the tenant or workspace the block belongs to. |
| root_id | UUID | The identifier of the canonical root block (e.g., the top-level document). |
| parent_id | UUID | The ID of the block's single canonical parent. Null for root blocks. |
| children_ids | UUID[] | An ordered list of the block's canonical children IDs. Ordering is owned by the parent. |
| in_trash | BOOLEAN | A flag indicating if the block has been soft-deleted. Defaults to FALSE. |
| version | BIGINT | A monotonic version number used for optimistic concurrency control. |
| created_time | TIMESTAMPTZ | The timestamp when the block was created. |
| last_edited_time | TIMESTAMPTZ | The timestamp of the last modification. |
| created_by | UUID | The ID of the user or process that created the block. |
| last_edited_by | UUID | The ID of the user or process that last edited the block. |
| properties | JSONB | A JSON object containing typed, schemaful properties specific to the block's type. |
| metadata | JSONB | A flexible JSON object for storing free-form annotations, AI outputs, or system flags. |
| content | JSONB | A JSON object containing multiple representations of the block's core data payload. |

---

### 3.1. Content Field Specification

Rather than a fully open JSON object, the content field adheres to a pre-defined, typed structure. It is designed to explicitly store multiple, simultaneous representations of a block's payload within a single object. This ensures that different consumers (UIs, AI models, renderers) can access the format they need without requiring real-time conversion.

All keys within the content object are **optional**. A block may contain one or more of these keys depending on its type and purpose. For example, a structural container block may have an empty content object, while a paragraph may only populate plain_text.

**Content Schema:**

| **Key** | **Data Type** | **Description** |
| --- | --- | --- |
| plain_text | string | The "safest" and most basic representation of the content. Ideal for search indexing, simple AI prompting, and universal compatibility. |
| object | JSON object | A structured object for complex, nested data. Can be used to represent richly formatted text, custom components, or other non-tabular structured data. |
| data | JSON object | A structured object specifically representing a data record, such as a row from a table or dataset. Typically a flat key-value map where keys are column names. |

## 4. Open Questions - Update these during document production

This section serves as a living list of architectural questions and trade-offs that need to be explicitly addressed and decided upon as this specification evolves.

- How is deletion handled? Do we use the in_trash flag, and what is the process for permanent deletion? 
**Status:** **Resolved** - see discussion in section 12.1.
- How are AI-generated outputs (e.g., extractions, summaries) treated? Do we add a source flag within metadata?
**Status:** **Resolved** - see discussion in section 12.2.
- How are external source document references treated (e.g., a reference to "Section 1.3.5" in a regulation)?
**Status:** **Resolved** - see discussion in section 12.3.
- Notion's architecture highlights that blocks can be converted from one type to another without losing history. How can we support this?
**Status:** **Resolved** - see discussion in section 12.4.
- How should rich text or inline elements (like mentions or links) be handled within the content model? Should this be part of plain_text using a format like Markdown, or within the object representation? Should we consider a hybrid using in-line Markdown blocks without clashing with block-level structures?
**Status:** **Deferred** - initial implementation to have no inline complexity (assume plain_text as default), review at a later stage.
- How Schema is defined and interacts with DataRecord
**Status:** **Deferred** - to be addressed as part of implementation details, but assume some sort of dictionary based approach with keys representing columns and values a dictionary of parameters like datatype, etc

## 5. Block Types Summary

This section provides a high-level overview of every block type defined in this specification, their architectural category, key properties, and their roles as potential containers.

### Block Type Overview

| **Block Type (type)** | **Category** | **Key Properties** | **Can Have Children?** | **Primary Content** |
| --- | --- | --- | --- | --- |
| **workspace** | Container | title | Yes | Structural |
| **collection** | Container | title | Yes | Structural |
| **document** | Container | title, category | Yes | Structural |
| **dataset** | Container | title, schema, category | Yes (only record type) | Structural |
| derived_content_container | Container | category | Yes | Structural |
| **paragraph** | Document Content | (none) | No | plain_text |
| **bulleted_list_item** | Document Content | (none) | Yes (for nesting) | plain_text |
| **numbered_list_item** | Document Content | (none) | Yes (for nesting) | plain_text |
| **heading** | Document Content | level | No | plain_text |
| **quote** | Document Content | (none) | Yes | Structural (via children) |
| **code** | Document Content | language | No | plain_text |
| **table** | Document Content | (none) | No | object |
| **html** | Document Content | (none) | No | plain_text |
| object | Document Content | category | Yes | object, plain_text |
| **record** | Dataset Content | (none) | No | data, plain_text |
| **group_index** | Grouping | group_index_type | Yes (only group types) | Structural |
| **page_group** | Grouping | page_number | No | Structural |
| **chunk_group** | Grouping | (none) | No | Structural |

## 6. Container Blocks

Container Blocks are high-level blocks that provide the primary structure for organising content. They act as the roots of content trees (like documents and datasets) or as organisational folders (collections), or to hold derived content (like AI-generated entities).

---

### WorkspaceBlock

- **Type:** workspace
- **Purpose:** The single, ultimate parent for all content blocks within a workspace. It is the only block that can have a null parent.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| title | string | Yes | The user-facing name of the workspace. |

**Content Usage**

This is a structural block and does not contain any content.

**Renderer Behavior**

- This block is not rendered as content. It serves as the top-level entry point for navigating a workspace's content in a user interface.

---

### CollectionBlock

- **Type:** collection
- **Purpose:** A folder-like container used to organize documents, datasets, and other collections.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| title | string | Yes | The user-facing name of the collection. |

**Content Usage**

This is a structural block and does not contain any content.

**Renderer Behavior**

- This block is not rendered as content. In a UI, it would be represented as a navigable folder.

### DocumentBlock

- **Type:** document
- **Purpose:** The root block for a document. It acts as the primary container for a narrative or semantic tree of heterogeneous content blocks (paragraphs, headings, tables, etc.).

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| title | string | No | The title of the document. |
| category | string | No | A business-specific type for the document (e.g., 'policy', 'contract', 'procedure', or 'generic'). |

**Content Usage**

The DocumentBlock itself does not have content; it serves as the parent for the blocks that do.

**Renderer Behavior**

- A renderer would typically display the title property, followed by the recursive rendering of its child blocks.

---

### DatasetBlock

- **Type:** dataset
- **Purpose:** The root block for a set of structured data. It acts as the primary container for a homogeneous collection of RecordBlocks and defines their schema.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| title | string | No | The title of the dataset. |
| schema | JSON object | Yes | A structured object that defines the columns (e.g., name, data type) for all child RecordBlocks. |
| category | string | No | A business-specific type for the dataset (e.g., 'control_library', 'risk_register', or 'generic'). |

**Content Usage**

The DatasetBlock itself does not have content; it defines the structure for its child RecordBlocks.

**Renderer Behavior**

- A renderer would typically display the title property and render its child RecordBlocks as a table, using the schema property to create the table headers.

---

### DerivedContentContainerBlock

- **Type:** derived_content_container
- **Purpose:** A specialized, system-managed container whose purpose is to hold a collection of derived content (like ObjectBlocks) of a single, specific category. It is a direct child of a DocumentBlock and serves to keep machine-generated data cleanly separated from the primary narrative.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| category | string | Yes | A string that defines the single, specific type of derived data this container holds (e.g., 'obligations', 'controls', 'definitions'). |

**Content Usage**

This is a structural block and does not contain any content.

**Renderer Behavior**

- This block is not typically rendered as part of the primary document view. The UI can use the category property to display its contents in specific, context-aware ways (e.g., showing a list of obligations in a dedicated side panel).

---

## 7. Document Content Blocks

Document Content Blocks are used to represent the primary content from unstructured sources like documents, articles, and web pages. They form the narrative and informational backbone of a document.

---

### ParagraphBlock

- **Type:** paragraph
- **Purpose:** The fundamental block for representing a paragraph of text. It is the default and most common content block.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| groups | list[UUID] | No | A list of Group Block UUIDs this block belongs to. Defaults to []. |

**Content Usage**

| **Key** | **Usage** |
| --- | --- |
| plain_text | **Required.** Contains the raw text content of the paragraph. |
| object | *Optional.* For complex, structured data representations of the content. |
| data | *Not used.* |

**Renderer Behavior**

- **Markdown:** Renders the plain_text content, followed by two newlines.

---

### BulletedListItemBlock

- **Type:** bulleted_list_item
- **Purpose:** Represents a single item in a bulleted (unordered) list. This block can also act as a container for other blocks to create nested lists.

**A Note on How Lists Are Structured**

A list is formed by placing multiple BulletedListItemBlock or NumberedListItemBlocks sequentially as siblings. A **nested list** is created by making one list item block the **canonical parent** of another. The depth of nesting in the block hierarchy directly defines the visual indentation level.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| groups | list[UUID] | No | A list of Group Block UUIDs this block belongs to. Defaults to []. |

**Content Usage**

| **Key** | **Usage** |
| --- | --- |
| plain_text | **Required.** Contains the text content of the list item itself. |
| object | *Optional.* For complex, structured data representations of the content. |
| data | *Not used.* |

**Renderer Behavior**

- **Markdown:** Renders a bullet point (*) followed by the plain_text content. The renderer is responsible for calculating the required indentation based on the block's depth in the hierarchy.

---

### NumberedListItemBlock

- **Type:** numbered_list_item
- **Purpose:** Represents a single item in a numbered (ordered) list. This block can also act as a container for other blocks.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| groups | list[UUID] | No | A list of Group Block UUIDs this block belongs to. Defaults to []. |

**Content Usage**

| **Key** | **Usage** |
| --- | --- |
| plain_text | **Required.** Contains the text content of the list item itself. |
| object | *Optional.* For complex, structured data representations of the content. |
| data | *Not used.* |

**Renderer Behavior**

- **Markdown:** Renders a number (1.) followed by the plain_text content. The renderer is responsible for calculating indentation based on the block's depth and determining the correct list number based on preceding sibling blocks.

---

### HeadingBlock

- **Type:** heading
- **Purpose:** Represents a document heading, such as a title or section header.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| level | integer | Yes | The heading level, from 1 (most important) to 6 (least important). |
| groups | list[UUID] | No | A list of Group Block UUIDs this block belongs to. Defaults to []. |

**Content Usage**

| **Key** | **Usage** |
| --- | --- |
| plain_text | **Required.** Contains the text of the heading. |
| object | *Not used.* |
| data | *Not used.* |

**Renderer Behavior**

- **Markdown:** Renders a number of # characters corresponding to the level property, followed by the plain_text content.

---

### QuoteBlock

- **Type:** quote
- **Purpose:** Represents a block of quoted text. It can contain other content blocks (like paragraphs or lists) to represent complex quotations.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| groups | list[UUID] | No | A list of Group Block UUIDs this block belongs to. Defaults to []. |

**Content Usage**

The QuoteBlock itself typically has no direct content; its value comes from the child blocks it contains.

| **Key** | **Usage** |
| --- | --- |
| plain_text | *Not used.* |
| object | *Not used.* |
| data | *Not used.* |

**Renderer Behavior**

- **Markdown:** The renderer prepends a > character to each line of the content rendered from its child blocks.

---

### CodeBlock

- **Type:** code
- **Purpose:** Represents a block of pre-formatted text, typically for displaying code snippets.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| language | string | No | A string from a pre-defined set of supported languages for syntax highlighting. Examples: 'python', 'javascript', 'sql', 'typescript', 'bash', 'json'. |
| groups | list[UUID] | No | A list of Group Block UUIDs this block belongs to. Defaults to []. |

**Content Usage**

| **Key** | **Usage** |
| --- | --- |
| plain_text | **Required.** Contains the raw, unformatted code string. |
| object | *Not used.* |
| data | *Not used.* |

**Renderer Behavior**

- **Markdown:** Renders the plain_text content inside a fenced code block (```). The language property is used for the info string (e.g., ```python).

---

### TableBlock

- **Type:** table
- **Purpose:** Represents a semantic table with structured, machine-readable data.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| groups | list[UUID] | No | A list of Group Block UUIDs this block belongs to. Defaults to []. |

**Content Usage**

This block uses the object field to store a canonical JSON representation of the table.

| **Key** | **Usage** |
| --- | --- |
| plain_text | *Optional.* A plain text summary or title for the table. |
| object | **Required.** A structured JSON object representing the table's headers, rows, and cells. The schema should be able to represent complex structures like merged cells. |
| data | *Not used.* |

**Renderer Behavior**

- **Markdown:** Requires a transformation from the structured object content into Markdown table syntax.

---

### HtmlBlock

- **Type:** html
- **Purpose:** An "escape hatch" to store a block of raw HTML. This is used when content cannot be cleanly mapped to a semantic block type, preserving its original formatting.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| groups | list[UUID] | No | A list of Group Block UUIDs this block belongs to. Defaults to []. |

**Content Usage**

| **Key** | **Usage** |
| --- | --- |
| plain_text | **Required.** Contains the raw HTML string for the block. |
| object | *Not used.* |
| data | *Not used.* |

**Renderer Behavior**

- **Markdown:** The renderer should pass the raw HTML string from the plain_text field through untouched, as Markdown parsers typically support inline HTML.

---

### ObjectBlock

- **Type:** object
- **Purpose:** Represents a block whose primary content is a structured JSON object. It serves a dual role: as a generic content type for embedding custom structured data (e.g., charts, complex tables) within a document's narrative flow, and as a container for system-generated data like AI extractions.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| category | string | No | An optional string that defines the "schema" or kind of data being stored. When present (e.g., 'obligation'), it allows systems to interpret and handle the object's content in a specific way. |
| groups | list[UUID] | No | A list of Group Block UUIDs this block belongs to. Defaults to []. |

**Content Usage**

| **Key** | **Usage** |
| --- | --- |
| plain_text | *Optional.* A simple string summary or title for the object. |
| object | **Required.** A JSON object containing the structured key-value pairs of the block's content. |
| data | *Not used.* |

**Renderer Behavior**

- **Markdown:** The rendering of this block is context-dependent. A generic renderer might display the plain_text title or a simple representation of the JSON content. Specific applications or UI components would be required to render a meaningful visualisation based on the object content, often keyed by the category property.

## 8. Dataset Content Blocks

Dataset Content Blocks are used to represent the structured data records that reside within a DatasetBlock. There is only one block type in this category.

---

### RecordBlock

- **Type:** record
- **Purpose:** Represents a single, structured record (or row) within a DatasetBlock.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| groups | list[UUID] | No | A list of Group Block UUIDs this block belongs to. Defaults to []. |

**Content Usage**

This block uses both the data and plain_text fields to provide structured and unstructured representations of its content.

| **Key** | **Usage** |
| --- | --- |
| plain_text | *Optional.* A simple string concatenation of the record's values. Useful for search and simple AI contexts (e.g., "CTRL-001, Active, High Risk"). |
| object | *Not used.* |
| data | **Required.** A JSON object containing the key-value pairs for the record. The keys must align with the column definitions in the parent DatasetBlock's schema. |

**Renderer Behavior**

- **Markdown:** A RecordBlock is not typically rendered in isolation. It renders a single table row (| cell 1 | cell 2 |) as part of a larger table rendering operation initiated by its DatasetBlock parent.

## 9. Grouping Blocks

Grouping Blocks do not represent visible content themselves. Instead, they serve as structural "anchors" that enable the creation of secondary views across the canonical content, such as physical pages or AI-ready chunks. Content blocks associate with these groups by storing the group block's UUID in their properties.groups array.

---

### GroupIndexBlock

- **Type:** group_index
- **Purpose:** Acts as the single, canonical parent for a collection of related group blocks. Its children_ids array defines the explicit order of the groups (e.g., page 1, page 2, page 3...).

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| group_index_type | Literal['page', 'chunk'] | Yes | A string that defines the kind of groups this index contains. |

**Content Usage**

This is a structural block and does not contain any content.

**Renderer Behavior**

- This block is not rendered directly. It provides a structural root for querying and ordering a specific set of groups.

---

### PageGroupBlock

- **Type:** page_group
- **Purpose:** An anchor block representing a single physical page from a source document. Its id is referenced by content blocks.

**Typed Properties (properties)**

| **Property** | **Data Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| page_number | integer | Yes | The sequential number of the page this group represents. |

**Content Usage**

This is a structural block and does not contain any content.

**Renderer Behavior**

- This block is not rendered directly. Its existence allows a renderer to query for all content blocks belonging to this page and render them in their correct canonical order.

---

### ChunkGroupBlock

- **Type:** chunk_group
- **Purpose:** An anchor block representing a single, AI-generated chunk of content, typically for use in RAG systems.

**Typed Properties (properties)**

The properties object for this block is empty. Its identity is its id and its order is defined by its position within its parent GroupIndexBlock.

**Content Usage**

This is a structural block and does not contain any content.

**Renderer Behavior**

- This block is not rendered directly. It is used to query and assemble the content blocks that form a specific chunk for an AI model.

## 10. System Blocks

### UnsupportedBlock

- **Type:** unsupported
- **Purpose:** A minimal block type used by ingestion systems to store raw content that is malformed, unrecognised, or cannot be mapped to any other semantic block type.

**Typed Properties (properties)**

This block has no specific typed properties. It simply inherits from Base Block.

**Content Usage**

| **Key** | **Usage** |
| --- | --- |
| plain_text | *Optional.* Used to store the raw, unparsed string content of the unsupported element. |
| object | *Optional.* Used to store any partially-parsed or structured data from the unsupported element. |
| data | *Not used.* |

**Renderer Behavior**

- A renderer should display a simple, non-intrusive placeholder (e.g., [unsupported content]) or render nothing. This ensures the block is noted without breaking the flow of the document.

## 11. Future Considerations: Deferred Block Types

To maintain a lean and focused initial implementation, a number of block types have been explicitly deferred. The core architecture is designed to be extensible, and the following blocks represent logical next steps that can be added in the future without requiring fundamental changes to the base model.

| **Block Type**  | **Description** |
| --- | --- |
| ImageBlock | A block for embedding and displaying images. This would require integration with a file storage solution and would manage properties such as the image URL, alternative text, and a user-facing caption. |
| VideoBlock | For embedding playable videos, either by uploading a file or by linking to a third-party service like YouTube or Vimeo. It would manage a source URL and potentially display settings like autoplay or looping. |
| AudioBlock | For embedding playable audio clips. This block would handle uploaded audio files or links to audio streaming services, managing the source URL and playback controls. |
| FileBlock | A block for attaching and linking to downloadable files (e.g., PDFs, spreadsheets, archives). It would integrate with a file storage system and display metadata such as the filename, file type, and size. |
| WebLinkBlock | For displaying a rich, visually appealing preview of an external URL. This would require a backend service to fetch metadata (like the title, description, and preview image) from the linked page and display it in a structured card format. |
| TodoBlock | An interactive block representing a single task or to-do item. It would function like a list item but include a checkbox, requiring a stateful property (e.g., checked: boolean) to track its completion status. |

## 12. Final Design Decisions and Next Steps

### 12.1. Handling Deletion

The system will adopt a hierarchical, non-cascading soft-delete model. This approach is chosen to ensure that user-facing delete and restore operations are instantaneous, while centralizing the complexity of hierarchical state within the data-retrieval layer.

**1. Mechanism: The Implicit Model**

The soft-delete mechanism is defined by the following principles:

- **The in_trash Flag:** Deletion state is managed by the in_trash boolean flag in the Base Block Schema. A TRUE value indicates the block is considered "in the trash".
- **Non-Cascading Writes:** When a parent block is moved to the trash, **only that specific block's in_trash flag is set to TRUE**. All of its descendants remain unchanged in the database but are considered *implicitly* trashed by inheritance.
- **Canonical Structures Stay Intact:** Neither the repository nor the store rewrites children_ids when a child is hidden. The canonical order is always persisted exactly as authored so future writes can reuse the same block instances without losing references.
- **Instantaneous Operations:** This model ensures that both delete and restore operations are single, atomic database updates, making them feel instantaneous to the user regardless of the number of child blocks.

**2. Critical Implementation Requirement: Hierarchy-Aware Queries**

The choice of a non-cascading write model introduces a non-negotiable requirement for all data retrieval logic.

> Every query that fetches blocks for user-facing views MUST be hierarchy-aware.
> 
> 
> To determine if a block is truly visible, a query cannot simply check the block's own in_trash flag. It must traverse up the block's entire parental hierarchy to the root, ensuring that no ancestor is marked as in_trash.
> 
> This must be implemented efficiently in a single database roundtrip, typically using a **Recursive Common Table Expression (CTE)**.
> 

This is the foundational integrity constraint for the entire system. Building this logic into the core data access layer from the beginning is essential to prevent deleted content from appearing in any part of the application.

In practice, the repository filters visibility (via a recursive CTE) but still returns canonical models. Consumers such as renderers or the Document Store simply skip children that fail to resolve, ensuring that read views stay clean without mutating the persisted structure.

**3. Staged Implementation Strategy**

To manage initial complexity while building on a correct technical foundation, the implementation of the deletion feature will be staged.

- **V1 Implementation (Core Mechanism):**
    - The in_trash column must be added to the blocks table from the initial migration.
    - All data access methods for reading block trees (e.g., fetching a document's content, search queries) **must** implement the recursive, hierarchy-aware query logic from Day 1.
- **Future Implementation (User-Facing Features):**
    - The user interface for a "Trash" view, which would list all blocks where in_trash = TRUE.
    - The "Restore" functionality, which sets the in_trash flag back to FALSE.
    - A background job for handling permanent deletion and cleaning up any dangling references that result from it.

### 12.2. Handling AI-Generated Content

The block model is designed to support a range of AI-generated outputs by treating them as first-class citizens within the system. The specific implementation depends on the nature and lifecycle of the output. The three primary scenarios are:

**1. Tier 1: Annotations (e.g., "Tagger")**

- **Scenario:** An AI process analyzes a block and attaches simple, descriptive information to it (e.g., tagging a paragraph with a topic).
- **Decision:** This output is treated as a simple annotation. It is stored directly in the **metadata** field of the source block it describes. This is appropriate for data that has no independent identity and is purely an attribute of its source.

**2. Tier 2: Structured Objects (e.g., "Obligation Extractor")**

- **Scenario:** An AI process analyzes a block and extracts a structured piece of data with its own distinct identity (e.g., an obligation with multiple fields).
- **Decision:** The extracted data must be stored in a new, independent block to be queryable and linkable. The following pattern will be used:
    1. A new **ObjectBlock** is created to hold the structured data in its content.object field. Its properties.category is set to define the data type (e.g., 'obligation').
    2. This ObjectBlock is placed inside a dedicated **DerivedContentContainerBlock**, which is a child of the source DocumentBlock. This provides a predictable location for all such derived assets.
    3. A permanent, queryable link is created in the **relationships** table to connect the new ObjectBlock to its source block, with a type like 'derived_from'.

**3. Tier 3: Full Document Generation (e.g., "AI Reporter")**

- **Scenario:** An AI process generates a full, multi-part document from a prompt or source materials.
- **Decision:** The AI agent will act as a standard author. It will create a new **DocumentBlock** and populate it with a tree of standard content blocks (HeadingBlock, ParagraphBlock, etc.). To ensure traceability, identifying information (e.g., the model version, source prompt) will be stored in the **metadata** field of the root DocumentBlock.

### 12.3. Handling Source Document Numbering and References

To capture source document references (e.g., a paragraph labeled "13.9.6" or a heading titled "Section 1.3.5 Data Encryption"), the system will adopt a two-part strategy that prioritises textual integrity while allowing for optional machine-readable data.

- **Primary Representation in Content:** The reference number or label will be stored as a natural part of the block's content.plain_text. This ensures the canonical text is a faithful representation of the source and is immediately searchable and renderable.
- **Optional Annotation in Metadata:** For advanced use cases, an ingestion process or AI tool can parse this reference and store its structured components (e.g., {"reference": "13.9.6"}) in the block's metadata field. This enables powerful, structured querying without altering the core content.

This approach will still be compatible for constructing a bread-crumb, in the same way as Notion displays a document’s TOCs by traversing the node structure based on headings.

### 12.4. Supporting Block Type Conversion

To allow users to convert blocks from one type to another (e.g., a Heading to a Paragraph) without losing historical property data, the system will adopt a **Unified Properties Model**. This approach prioritizes data fidelity and minimal conversion logic.

- **Mechanism:** When a block's type is changed, the properties field in the database remains untouched. Any properties from the original type that do not have a corresponding field in the new type's schema are preserved in the database but ignored by the application's data model.
- **Implementation:** To enable this, the Pydantic BaseModel that serves as the foundation for all typed properties objects must be configured with extra = 'allow'. This single configuration on the base properties model ensures that all subclasses will correctly ignore unknown fields during parsing without raising validation errors.
- **Benefit:** This strategy makes block conversion a simple, atomic operation (changing only the type field) and guarantees that no data is ever lost. If a block is converted back to a previous type, its original properties will be available and correctly parsed.
