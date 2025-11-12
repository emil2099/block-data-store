from __future__ import annotations

from uuid import UUID, uuid4

from block_data_store.models.block import BlockType, Content
from block_data_store.renderers import MarkdownRenderer, RenderOptions


def _wire(blocks):
    mapping = {block.id: block for block in blocks}

    def resolve_one(block_id: UUID | None):
        return mapping.get(block_id) if block_id else None

    def resolve_many(block_ids):
        return [mapping[b_id] for b_id in block_ids if b_id in mapping]

    for block_id, block in list(mapping.items()):
        mapping[block_id] = block.with_resolvers(resolve_one=resolve_one, resolve_many=resolve_many)
    return mapping


def test_markdown_renderer_renders_document_tree(block_factory):
    document_id = uuid4()
    heading_id = uuid4()
    paragraph_id = uuid4()

    document = block_factory(
        block_id=document_id,
        block_type=BlockType.DOCUMENT,
        parent_id=None,
        root_id=document_id,
        children_ids=(heading_id,),
        properties={"title": "Sample Doc"},
    )
    heading = block_factory(
        block_id=heading_id,
        block_type=BlockType.HEADING,
        parent_id=document_id,
        root_id=document_id,
        children_ids=(paragraph_id,),
        properties={"level": 2},
        content=Content(plain_text="Intro"),
    )
    paragraph = block_factory(
        block_id=paragraph_id,
        block_type=BlockType.PARAGRAPH,
        parent_id=heading_id,
        root_id=document_id,
        content=Content(plain_text="Hello world."),
    )

    blocks = _wire([document, heading, paragraph])
    renderer = MarkdownRenderer()

    output = renderer.render(blocks[document_id])

    assert "# Sample Doc" in output
    assert "## Intro" in output
    assert "Hello world." in output


def test_markdown_renderer_includes_metadata(block_factory):
    paragraph = block_factory(
        block_type=BlockType.PARAGRAPH,
        parent_id=None,
        root_id=uuid4(),
        content=Content(plain_text="Body"),
        metadata={"role": "summary", "language": "en"},
    )

    renderer = MarkdownRenderer()
    output = renderer.render(paragraph, options=RenderOptions(include_metadata=True, recursive=False))

    assert "Body" in output
    assert "> language: en" in output
    assert "> role: summary" in output


def test_dataset_renderer_includes_child_records(block_factory):
    dataset_id = uuid4()
    record_id = uuid4()

    dataset = block_factory(
        block_id=dataset_id,
        block_type=BlockType.DATASET,
        parent_id=None,
        root_id=dataset_id,
        children_ids=(record_id,),
        properties={"category": "inventory"},
        content=None,
    )
    record = block_factory(
        block_id=record_id,
        block_type=BlockType.RECORD,
        parent_id=dataset_id,
        root_id=dataset_id,
        content=Content(data={"title": "Item A", "status": "active"}),
    )

    blocks = _wire([dataset, record])
    renderer = MarkdownRenderer()

    output = renderer.render(blocks[dataset_id])

    assert "```dataset:inventory" in output
    assert "#### Item A" in output
    assert "- **status**: active" in output


def test_markdown_renderer_renders_lists(block_factory):
    doc_id = uuid4()
    heading_id = uuid4()
    paragraph_id = uuid4()
    bullet_values_id = uuid4()
    bullet_transparency_id = uuid4()
    bullet_nested_one_id = uuid4()
    bullet_nested_two_id = uuid4()
    number_one_id = uuid4()
    number_two_id = uuid4()
    number_three_id = uuid4()
    number_nested_one_id = uuid4()
    number_nested_two_id = uuid4()

    document = block_factory(
        block_id=doc_id,
        block_type=BlockType.DOCUMENT,
        parent_id=None,
        root_id=doc_id,
        children_ids=(heading_id,),
        properties={"title": "Team Handbook"},
    )
    heading = block_factory(
        block_id=heading_id,
        block_type=BlockType.HEADING,
        parent_id=doc_id,
        root_id=doc_id,
        children_ids=(
            paragraph_id,
            bullet_values_id,
            bullet_transparency_id,
            number_one_id,
            number_two_id,
            number_three_id,
        ),
        properties={"level": 2},
        content=Content(plain_text="Purpose"),
    )
    paragraph = block_factory(
        block_id=paragraph_id,
        block_type=BlockType.PARAGRAPH,
        parent_id=heading_id,
        root_id=doc_id,
        content=Content(plain_text="Our mission is to build simple data tools."),
    )
    bullet_values = block_factory(
        block_id=bullet_values_id,
        block_type=BlockType.BULLETED_LIST_ITEM,
        parent_id=heading_id,
        root_id=doc_id,
        children_ids=(bullet_nested_one_id, bullet_nested_two_id),
        content=Content(plain_text="Values"),
    )
    bullet_nested_one = block_factory(
        block_id=bullet_nested_one_id,
        block_type=BlockType.BULLETED_LIST_ITEM,
        parent_id=bullet_values_id,
        root_id=doc_id,
        content=Content(plain_text="Customer Obsessed"),
    )
    bullet_nested_two = block_factory(
        block_id=bullet_nested_two_id,
        block_type=BlockType.BULLETED_LIST_ITEM,
        parent_id=bullet_values_id,
        root_id=doc_id,
        content=Content(plain_text="Iterate fast"),
    )
    bullet_transparency = block_factory(
        block_id=bullet_transparency_id,
        block_type=BlockType.BULLETED_LIST_ITEM,
        parent_id=heading_id,
        root_id=doc_id,
        content=Content(plain_text="Transparency"),
    )
    number_one = block_factory(
        block_id=number_one_id,
        block_type=BlockType.NUMBERED_LIST_ITEM,
        parent_id=heading_id,
        root_id=doc_id,
        content=Content(plain_text="Onboard"),
    )
    number_two = block_factory(
        block_id=number_two_id,
        block_type=BlockType.NUMBERED_LIST_ITEM,
        parent_id=heading_id,
        root_id=doc_id,
        children_ids=(number_nested_one_id, number_nested_two_id),
        content=Content(plain_text="Deliver"),
    )
    number_nested_one = block_factory(
        block_id=number_nested_one_id,
        block_type=BlockType.NUMBERED_LIST_ITEM,
        parent_id=number_two_id,
        root_id=doc_id,
        content=Content(plain_text="Kickoff"),
    )
    number_nested_two = block_factory(
        block_id=number_nested_two_id,
        block_type=BlockType.NUMBERED_LIST_ITEM,
        parent_id=number_two_id,
        root_id=doc_id,
        content=Content(plain_text="Feedback"),
    )
    number_three = block_factory(
        block_id=number_three_id,
        block_type=BlockType.NUMBERED_LIST_ITEM,
        parent_id=heading_id,
        root_id=doc_id,
        content=Content(plain_text="Improve"),
    )

    blocks = _wire(
        [
            document,
            heading,
            paragraph,
            bullet_values,
            bullet_nested_one,
            bullet_nested_two,
            bullet_transparency,
            number_one,
            number_two,
            number_nested_one,
            number_nested_two,
            number_three,
        ]
    )
    renderer = MarkdownRenderer()

    output = renderer.render(blocks[doc_id])

    expected = (
        "# Team Handbook\n\n"
        "## Purpose\n\n"
        "Our mission is to build simple data tools.\n\n"
        "- Values\n"
        "    - Customer Obsessed\n"
        "    - Iterate fast\n"
        "- Transparency\n\n"
        "1. Onboard\n"
        "2. Deliver\n"
        "    1. Kickoff\n"
        "    2. Feedback\n"
        "3. Improve"
    )

    assert output == expected


def test_markdown_renderer_renders_quote_block(block_factory):
    quote_id = uuid4()
    paragraph_id = uuid4()
    quote = block_factory(
        block_id=quote_id,
        block_type=BlockType.QUOTE,
        parent_id=None,
        root_id=quote_id,
        children_ids=(paragraph_id,),
    )
    paragraph = block_factory(
        block_id=paragraph_id,
        block_type=BlockType.PARAGRAPH,
        parent_id=quote_id,
        root_id=quote_id,
        content=Content(plain_text="Quoted text."),
    )
    blocks = _wire([quote, paragraph])
    renderer = MarkdownRenderer()

    output = renderer.render(blocks[quote_id])

    assert output.startswith("> Quoted text.")


def test_markdown_renderer_renders_code_block(block_factory):
    code = block_factory(
        block_type=BlockType.CODE,
        parent_id=None,
        root_id=uuid4(),
        properties={"language": "python"},
        content=Content(plain_text="print('ok')"),
    )
    renderer = MarkdownRenderer()

    output = renderer.render(code)

    assert "```python" in output
    assert "print('ok')" in output


def test_markdown_renderer_renders_table_block(block_factory):
    table = block_factory(
        block_type=BlockType.TABLE,
        parent_id=None,
        root_id=uuid4(),
        content=Content(
            object={
                "headers": ["Term", "Definition"],
                "rows": [["RTO", "Recovery Time Objective"]],
                "align": ["left", "right"],
            }
        ),
    )
    renderer = MarkdownRenderer()

    output = renderer.render(table)

    assert "| Term | Definition |" in output
    assert "| :--- | ---: |" in output
    assert "| RTO | Recovery Time Objective |" in output


def test_markdown_renderer_renders_html_block(block_factory):
    html = block_factory(
        block_type=BlockType.HTML,
        parent_id=None,
        root_id=uuid4(),
        content=Content(plain_text="<div>Note</div>"),
    )
    renderer = MarkdownRenderer()

    output = renderer.render(html)

    assert output == "<div>Note</div>"
