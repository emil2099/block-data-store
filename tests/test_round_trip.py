from __future__ import annotations

from uuid import UUID

from block_data_store.models.block import BlockType
from block_data_store.parser import markdown_to_blocks
from block_data_store.renderers import MarkdownRenderer
from block_data_store.store import DocumentStore


def test_markdown_round_trip_document(document_store: DocumentStore):
    source = "\n".join(
        [
            "# Team Handbook",
            "",
            "## Purpose",
            "",
            "Our mission is to build simple data tools.",
            "",
            "- Values",
            "    - Customer Obsessed",
            "    - Iterate fast",
            "- Transparency",
            "",
            "1. Onboard",
            "2. Deliver",
            "    1. Kickoff",
            "    2. Feedback",
            "3. Improve",
        ]
    )
    blocks = markdown_to_blocks(source)
    document_store.save_blocks(blocks)
    document = document_store.get_root_tree(blocks[0].id, depth=None)

    renderer = MarkdownRenderer()
    output = renderer.render(document)

    assert output == source

    _assert_block_shapes(document_store, document.id)


def _assert_block_shapes(store: DocumentStore, document_id: UUID) -> None:
    document = store.get_root_tree(document_id, depth=None)
    assert document is not None
    assert document.type is BlockType.DOCUMENT

    headings = document.children()
    assert len(headings) == 1
    heading = headings[0]
    assert heading.type is BlockType.HEADING
    assert getattr(heading.properties, "level") == 2
    assert heading.content and heading.content.plain_text == "Purpose"

    paragraphs = [child for child in heading.children() if child.type is BlockType.PARAGRAPH]
    assert len(paragraphs) == 1
    assert paragraphs[0].content.plain_text.startswith("Our mission")

    bullets = [child for child in heading.children() if child.type is BlockType.BULLETED_LIST_ITEM]
    assert len(bullets) == 2
    assert bullets[0].content.plain_text == "Values"
    assert len(bullets[0].children()) == 2
    assert bullets[0].children()[0].content.plain_text == "Customer Obsessed"
    assert bullets[0].children()[1].content.plain_text == "Iterate fast"

    numbers = [child for child in heading.children() if child.type is BlockType.NUMBERED_LIST_ITEM]
    assert len(numbers) == 3
    assert numbers[0].content.plain_text == "Onboard"
    assert numbers[1].content.plain_text == "Deliver"
    nested_numbers = numbers[1].children()
    assert [child.content.plain_text for child in nested_numbers] == ["Kickoff", "Feedback"]
