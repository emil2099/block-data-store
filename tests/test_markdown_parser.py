from __future__ import annotations

from block_data_store.models.block import BlockType
from block_data_store.parser import markdown_to_blocks


def test_markdown_to_blocks_builds_expected_hierarchy():
    source = """# Sample Document

## First Section

Paragraph content lives here.

## Second Section

- Item one
- Item two

```dataset:controls
{
  "records": [
    {"title": "Segregation of duties", "category": "Preventive"},
    {"title": "Maker-checker", "category": "Detective"}
  ]
}
```
"""
    blocks = markdown_to_blocks(source)

    assert [block.type for block in blocks[:2]] == [BlockType.DOCUMENT, BlockType.HEADING]

    document = blocks[0]
    first_heading = blocks[1]

    assert document.properties.title == "Sample Document"
    assert first_heading.parent_id == document.id
    assert document.children_ids[0] == first_heading.id
    assert first_heading.content and first_heading.content.plain_text == "First Section"
    assert getattr(first_heading.properties, "level") == 2

    list_item = next(block for block in blocks if block.type == BlockType.BULLETED_LIST_ITEM)
    assert not list_item.metadata
    assert "Item one" in (list_item.content.plain_text or "")

    dataset_block = next(block for block in blocks if block.type == BlockType.DATASET)
    record_children = [
        block for block in blocks if block.parent_id == dataset_block.id and block.type == BlockType.RECORD
    ]
    categories = {
        child.content.data.get("category")
        for child in record_children
        if child.content and child.content.data
    }
    assert categories == {"Preventive", "Detective"}
