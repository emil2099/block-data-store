from __future__ import annotations

from block_data_store.models.block import BlockType
from block_data_store.parser import markdown_to_blocks


def test_markdown_parser_emits_core_blocks():
    source = """# Sample Document

Intro paragraph before any sections.

## First Section

Paragraph content lives here.

> Keep it simple.
> Ship quickly.

- Item one
- Item two
    - Nested bullet

```python
print("hi")
```

| Term | Definition |
| ---- | ---------- |
| RPO  | Recovery Point Objective |

<div data-role="note">Raw HTML</div>
"""

    blocks = markdown_to_blocks(source)

    document = blocks[0]
    assert document.type is BlockType.DOCUMENT
    assert document.properties.title == "Sample Document"

    first_heading = next(block for block in blocks if block.type is BlockType.HEADING)
    assert first_heading.parent_id == document.id
    assert getattr(first_heading.properties, "level") == 2

    paragraph = next(block for block in blocks if block.type is BlockType.PARAGRAPH and block.parent_id == first_heading.id)
    assert paragraph.content and paragraph.content.plain_text.startswith("Paragraph content")

    quote = next(block for block in blocks if block.type is BlockType.QUOTE)
    quote_children = [child for child in blocks if child.parent_id == quote.id]
    assert len(quote_children) == 1
    assert quote_children[0].type is BlockType.PARAGRAPH
    assert "Keep it simple." in (quote_children[0].content.plain_text or "")
    assert "Ship quickly." in (quote_children[0].content.plain_text or "")

    code_block = next(block for block in blocks if block.type is BlockType.CODE)
    assert code_block.content and "print" in code_block.content.plain_text
    assert getattr(code_block.properties, "language") == "python"

    table_block = next(block for block in blocks if block.type is BlockType.TABLE)
    assert table_block.content and table_block.content.object
    assert table_block.content.object["headers"] == ["Term", "Definition"]
    assert table_block.content.object["rows"][0][1] == "Recovery Point Objective"

    html_block = next(block for block in blocks if block.type is BlockType.HTML)
    assert html_block.content and html_block.content.plain_text.startswith("<div data-role=\"note\">")
