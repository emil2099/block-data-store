# Getting Started with Block Data Store

Block Data Store is a unified block-based content model with persistence, parsing, and rendering layers. It allows you to store documents, sections, paragraphs, and datasets as typed blocks, enabling structured content management, filtering, and rendering.

## Installation

Install the package directly from GitHub:

```bash
pip install git+https://github.com/emil2099/block_data_store.git
```

For a specific version:

```bash
pip install "git+https://github.com/emil2099/block_data_store.git@v0.1.0"
```

## Quick Start

Here is a minimal example to get you up and running:

```python
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from block_data_store.db.engine import create_engine, create_session_factory
from block_data_store.db.schema import create_all
from block_data_store.models.block import DocumentBlock, ParagraphBlock, Content
from block_data_store.startup import ensure_workspace
from block_data_store.store import create_document_store

# 1. Initialize the store (SQLite example)
engine = create_engine(sqlite_path=Path("block_store.db"))
create_all(engine)
session_factory = create_session_factory(engine)
store = create_document_store(session_factory)

# 2. Ensure there is a workspace to attach documents to
workspace = ensure_workspace(store, title="My Workspace")

# 3. Create a document tree
doc_id = uuid4()
doc = DocumentBlock(
    id=doc_id,
    parent_id=None,
    root_id=doc_id,
    created_time=datetime.now(timezone.utc),
    last_edited_time=datetime.now(timezone.utc),
    properties={"title": "My First Document"},
)

para = ParagraphBlock(
    id=uuid4(),
    parent_id=doc_id,
    root_id=doc_id,
    created_time=datetime.now(timezone.utc),
    last_edited_time=datetime.now(timezone.utc),
    properties={},
    content=Content(plain_text="Hello, Block Data Store!"),
)

# 4. Persist blocks and attach the document under the workspace sidebar
store.upsert_blocks([doc, para], parent_id=workspace.id, top_level_only=True)

# 5. Retrieve and verify
saved_doc = store.get_block(doc_id)
print(f"Retrieved: {saved_doc.properties['title']}")
```

## Parsing Content

Block Data Store provides powerful parsers to ingest content from various sources into structured blocks.

### Markdown

The Markdown parser converts standard Markdown into a hierarchy of blocks (Document, Heading, Paragraph, List, Code, etc.).

```python
from block_data_store.parser import load_markdown_path, markdown_to_blocks

# Option 1: Load directly from a file
blocks = load_markdown_path("path/to/document.md")
store.upsert_blocks(blocks)

# Option 2: Parse a string
markdown_content = "# Hello\n\nThis is a paragraph."
blocks = markdown_to_blocks(markdown_content)
store.upsert_blocks(blocks)
```

### Azure Document Intelligence (PDFs)

The Azure DI parser extracts layout and content from PDFs using Azure's Document Intelligence service. It requires the `azure-ai-documentintelligence` package.

**Configuration:**
Set `AZURE_DI_ENDPOINT` and `AZURE_DI_KEY` environment variables, or pass them via `AzureDiConfig`.

```python
from pathlib import Path
from block_data_store.parser.azure_di_parser import azure_di_to_blocks, AzureDiConfig

# Configure the parser
config = AzureDiConfig(
    endpoint="https://<your-resource>.cognitiveservices.azure.com/",
    key="<your-key>",
    model_id="prebuilt-layout"  # Default model
)

# Parse a PDF file
pdf_path = Path("path/to/document.pdf")
with pdf_path.open("rb") as f:
    blocks = azure_di_to_blocks(
        f,
        config=config,
        grouping="canonical"  # Options: "canonical" (flow) or "page" (grouped by page)
    )

store.upsert_blocks(blocks)
```

### Datasets (CSV & Excel)

The Dataset parser converts tabular data into a `Dataset` block containing `Record` blocks for each row. It requires `pandas`.

```python
from block_data_store.parser.dataset_parser import dataset_to_blocks, DatasetParserConfig

# Configure dataset parsing
config = DatasetParserConfig(
    title="Sales Data 2024",
    category="Financials",
    select_columns=["Date", "Product", "Revenue"],  # Optional: filter columns
    reader="csv"  # Options: "auto", "csv", "excel"
)

# Parse a CSV file
blocks = dataset_to_blocks("path/to/sales.csv", config=config)

# The first block is the Dataset root, followed by Record blocks
dataset_root = blocks[0]
records = blocks[1:]

store.upsert_blocks(blocks)
```

## Core Concepts

- **Blocks**: The fundamental unit of content. Everything is a block (Document, Heading, Paragraph, Dataset, etc.).
- **DocumentStore**: The main entry point for interacting with the data (`upsert`, `get`, `query`).
- **Repository**: The underlying persistence layer (SQLAlchemy based).
- **Renderers**: Convert blocks back into formats like Markdown.
- **Parsers**: Ingest content from Markdown, PDF (via Azure DI), or CSVs into blocks.

## Working with Blocks

### Upserting Blocks

Use `upsert_blocks` to create or update blocks. Optionally supply `parent_id` to attach the top-level blocks you pass to a parent in one call. The method will:
- upsert all provided blocks,
- then update the parent’s `children_ids` (append or insert after a sibling) with optimistic concurrency checks.

```python
# Attach a document (and its subtree) under a workspace or collection
store.upsert_blocks(blocks, parent_id=workspace.id, top_level_only=True)

# Insert a new paragraph after an existing one
store.upsert_blocks(
    [new_paragraph],
    parent_id=doc.id,
    insert_after=existing_para_id,
)
```

`top_level_only=True` (default) means only the blocks in your list that are *not* children of another block in the same payload are attached to the parent; nested children keep their existing parents.

### Querying and Filtering

The store supports rich filtering capabilities using `WhereClause`, `ParentFilter`, and `RootFilter`.

```python
from block_data_store.repositories.filters import WhereClause, PropertyFilter, BlockType

# Find all paragraphs where the 'text' property contains "important"
blocks = store.query_blocks(
    where=WhereClause(
        type=BlockType.PARAGRAPH,
        property_filter=PropertyFilter(path="content.plain_text", value="important", operator="contains")
    )
)

# Filter by multiple types (OR logic) and workspace
# This returns all blocks that are either Documents OR Datasets within the specified workspace
mixed_blocks = store.query_blocks(
    where=WhereClause(
        type=[BlockType.DOCUMENT, BlockType.DATASET],
        workspace_id=workspace.id
    )
)
```

### Retrieving Trees

To get a full document tree (recursively):

```python
root_block = store.get_root_tree(document_id, depth=None)
# root_block.children() will yield child blocks recursively if depth=None or sufficient depth is provided
```

## Relationships

You can link blocks together using `Relationship` objects.

```python
from block_data_store.models.relationship import Relationship

# Create a relationship
rel = Relationship(
    workspace_id=workspace_id,
    source_block_id=source_block.id,
    target_block_id=target_block.id,
    rel_type="references",
    metadata={"note": "See also"}
)
store.upsert_relationships([rel])

# Query relationships
outgoing = store.get_relationships(source_block.id, direction="outgoing")
```

## Rendering to Markdown

```python
from block_data_store.renderers.markdown import MarkdownRenderer, RenderOptions

renderer = MarkdownRenderer()
markdown_output = renderer.render(root_block, options=RenderOptions(recursive=True))
print(markdown_output)
```
