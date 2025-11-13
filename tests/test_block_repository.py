from __future__ import annotations

from uuid import uuid4

import pytest

from block_data_store.models.block import BlockType, Content
from block_data_store.repositories.block_repository import (
    BlockNotFoundError,
    InvalidChildrenError,
    VersionConflictError,
)
from block_data_store.repositories.filters import (
    BooleanFilter,
    FilterOperator,
    LogicalOperator,
    ParentFilter,
    RootFilter,
    PropertyFilter,
    WhereClause,
)


def test_repository_round_trip_with_children_resolution(repository, block_factory):
    document_id = uuid4()
    heading_id = uuid4()
    paragraph_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
                children_ids=(heading_id,),
            ),
            block_factory(
                block_id=heading_id,
                block_type=BlockType.HEADING,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(paragraph_id,),
            ),
            block_factory(
                block_id=paragraph_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=heading_id,
                root_id=document_id,
            ),
        ]
    )

    fetched_document = repository.get_block(document_id)
    assert fetched_document is not None
    fetched_children = fetched_document.children()
    assert len(fetched_children) == 1
    assert fetched_children[0].id == heading_id

    fetched_paragraph = fetched_children[0].children()[0]
    assert fetched_paragraph.id == paragraph_id
    assert fetched_paragraph.parent().id == heading_id


def test_get_block_with_depth_prefetches_children_and_reuses_instances(repository, block_factory):
    document_id = uuid4()
    heading_id = uuid4()
    paragraph_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
                children_ids=(heading_id,),
            ),
            block_factory(
                block_id=heading_id,
                block_type=BlockType.HEADING,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(paragraph_id,),
                properties={"level": 2},
                content=Content(plain_text="Intro"),
            ),
            block_factory(
                block_id=paragraph_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=heading_id,
                root_id=document_id,
                content=Content(plain_text="Paragraph body"),
            ),
        ]
    )

    document = repository.get_block(document_id, depth=1)
    assert document is not None

    first_call_section = document.children()[0]
    second_call_section = document.children()[0]
    assert first_call_section is second_call_section
    assert first_call_section.parent() is document

    paragraph = first_call_section.children()[0]
    assert paragraph.content.plain_text == "Paragraph body"


def test_get_block_depth_none_materialises_full_tree(repository, block_factory):
    document_id = uuid4()
    heading_id = uuid4()
    paragraph_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
                children_ids=(heading_id,),
            ),
            block_factory(
                block_id=heading_id,
                block_type=BlockType.HEADING,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(paragraph_id,),
            ),
            block_factory(
                block_id=paragraph_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=heading_id,
                root_id=document_id,
                content=Content(plain_text="Nested"),
            ),
        ]
    )

    document = repository.get_block(document_id, depth=None)
    assert document is not None

    section = document.children()[0]
    assert section is document.children()[0]

    paragraph = section.children()[0]
    assert paragraph is section.children()[0]
    assert paragraph.parent() is section
    assert paragraph.content.plain_text == "Nested"


def test_set_children_reorders_and_updates_version(repository, block_factory):
    document_id = uuid4()
    heading_id = uuid4()
    para_a_id = uuid4()
    para_b_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
                children_ids=(heading_id,),
            ),
            block_factory(
                block_id=heading_id,
                block_type=BlockType.HEADING,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(para_a_id, para_b_id),
            ),
            block_factory(
                block_id=para_a_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=heading_id,
                root_id=document_id,
            ),
            block_factory(
                block_id=para_b_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=heading_id,
                root_id=document_id,
            ),
        ]
    )

    repository.set_children(heading_id, (para_b_id, para_a_id), expected_version=0)

    section = repository.get_block(heading_id)
    assert section is not None
    assert section.children_ids == (para_b_id, para_a_id)
    assert section.version == 1

    paragraph_b = repository.get_block(para_b_id)
    assert paragraph_b is not None and paragraph_b.version == 0


def test_set_children_rejects_duplicate_child_ids(repository, block_factory):
    parent_id = uuid4()
    child_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=parent_id,
                block_type=BlockType.HEADING,
                parent_id=None,
                root_id=parent_id,
                children_ids=(child_id,),
            ),
            block_factory(
                block_id=child_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=parent_id,
                root_id=parent_id,
            ),
        ]
    )

    with pytest.raises(InvalidChildrenError):
        repository.set_children(parent_id, (child_id, child_id), expected_version=0)


def test_set_children_rejects_missing_parent(repository):
    with pytest.raises(BlockNotFoundError):
        repository.set_children(uuid4(), [], expected_version=0)


def test_set_children_rejects_missing_children(repository, block_factory):
    parent_id = uuid4()
    repository.upsert_blocks(
        [
            block_factory(
                block_id=parent_id,
                block_type=BlockType.HEADING,
                parent_id=None,
                root_id=parent_id,
            )
        ]
    )

    with pytest.raises(InvalidChildrenError):
        repository.set_children(parent_id, (uuid4(),), expected_version=0)


def test_set_children_rejects_cross_root_assignments(repository, block_factory):
    root_a = uuid4()
    root_b = uuid4()
    parent_id = uuid4()
    child_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=parent_id,
                block_type=BlockType.HEADING,
                parent_id=None,
                root_id=root_a,
            ),
            block_factory(
                block_id=child_id,
                block_type=BlockType.HEADING,
                parent_id=None,
                root_id=root_b,
            ),
        ]
    )

    with pytest.raises(InvalidChildrenError):
        repository.set_children(parent_id, (child_id,), expected_version=0)


def test_set_children_rejects_cycles(repository, block_factory):
    root_id = uuid4()
    parent_id = uuid4()
    child_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=parent_id,
                block_type=BlockType.HEADING,
                parent_id=None,
                root_id=root_id,
                children_ids=(child_id,),
            ),
            block_factory(
                block_id=child_id,
                block_type=BlockType.HEADING,
                parent_id=parent_id,
                root_id=root_id,
            ),
        ]
    )

    with pytest.raises(InvalidChildrenError):
        repository.set_children(child_id, (parent_id,), expected_version=0)


def test_reorder_children_requires_current_version(repository, block_factory):
    parent_id = uuid4()
    child_ids = [uuid4(), uuid4(), uuid4()]

    repository.upsert_blocks(
        [
            block_factory(
                block_id=parent_id,
                block_type=BlockType.HEADING,
                parent_id=None,
                root_id=parent_id,
                children_ids=tuple(child_ids),
            ),
        ]
        + [
            block_factory(
                block_id=child_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=parent_id,
                root_id=parent_id,
            )
            for child_id in child_ids
        ]
    )

    with pytest.raises(VersionConflictError):
        repository.reorder_children(parent_id, child_ids, expected_version=1)

    repository.reorder_children(parent_id, child_ids, expected_version=0)


def test_move_block_updates_parent_relationships(repository, block_factory):
    root_id = uuid4()
    section_a_id = uuid4()
    section_b_id = uuid4()
    paragraph_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=root_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=root_id,
                children_ids=(section_a_id,),
            ),
            block_factory(
                block_id=section_a_id,
                block_type=BlockType.HEADING,
                parent_id=root_id,
                root_id=root_id,
                children_ids=(paragraph_id,),
            ),
            block_factory(
                block_id=section_b_id,
                block_type=BlockType.HEADING,
                parent_id=root_id,
                root_id=root_id,
            ),
            block_factory(
                block_id=paragraph_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=section_a_id,
                root_id=root_id,
            ),
        ]
    )

    repository.move_block(
        paragraph_id,
        section_b_id,
        index=0,
        expected_block_version=0,
        expected_new_parent_version=0,
    )

    section_a = repository.get_block(section_a_id)
    section_b = repository.get_block(section_b_id)
    paragraph = repository.get_block(paragraph_id)

    assert section_a is not None and section_b is not None and paragraph is not None
    assert section_a.children_ids == ()
    assert section_b.children_ids == (paragraph_id,)
    assert paragraph.parent_id == section_b_id


def test_move_block_rejects_cross_root_moves(repository, block_factory):
    root_a = uuid4()
    root_b = uuid4()
    root_id = uuid4()
    heading_id = uuid4()
    paragraph_id = uuid4()
    other_root_section = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=paragraph_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=heading_id,
                root_id=root_a,
            ),
            block_factory(
                block_id=heading_id,
                block_type=BlockType.HEADING,
                parent_id=root_id,
                root_id=root_a,
                children_ids=(paragraph_id,),
            ),
            block_factory(
                block_id=root_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=root_a,
            ),
            block_factory(
                block_id=other_root_section,
                block_type=BlockType.HEADING,
                parent_id=root_b,
                root_id=root_b,
            ),
        ]
    )

    with pytest.raises(InvalidChildrenError):
        repository.move_block(
            paragraph_id,
            other_root_section,
            index=0,
            expected_block_version=0,
            expected_new_parent_version=0,
        )


def test_query_blocks_supports_structural_and_parent_filters(repository, block_factory):
    document_id = uuid4()
    dataset_controls_id = uuid4()
    dataset_inventory_id = uuid4()
    record_preventive_id = uuid4()
    record_detective_id = uuid4()
    record_inventory_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
                children_ids=(dataset_controls_id, dataset_inventory_id),
            ),
            block_factory(
                block_id=dataset_controls_id,
                block_type=BlockType.DATASET,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(record_preventive_id, record_detective_id),
                properties={"category": "controls"},
            ),
            block_factory(
                block_id=dataset_inventory_id,
                block_type=BlockType.DATASET,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(record_inventory_id,),
                properties={"category": "inventory"},
            ),
            block_factory(
                block_id=record_preventive_id,
                block_type=BlockType.RECORD,
                parent_id=dataset_controls_id,
                root_id=document_id,
                content=Content(data={"category": "Preventive"}),
            ),
            block_factory(
                block_id=record_detective_id,
                block_type=BlockType.RECORD,
                parent_id=dataset_controls_id,
                root_id=document_id,
                content=Content(data={"category": "Detective"}),
            ),
            block_factory(
                block_id=record_inventory_id,
                block_type=BlockType.RECORD,
                parent_id=dataset_inventory_id,
                root_id=document_id,
                content=Content(data={"category": "Inventory"}),
            ),
        ]
    )

    records = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD, root_id=document_id),
    )
    record_ids = {block.id for block in records}
    assert record_ids == {record_preventive_id, record_detective_id, record_inventory_id}

    preventive_records = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD, root_id=document_id),
        property_filter=PropertyFilter(path="content.data.category", value="Preventive"),
    )
    assert [block.id for block in preventive_records] == [record_preventive_id]

    controls_records = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD),
        parent=ParentFilter(
            where=WhereClause(type=BlockType.DATASET, root_id=document_id),
            property_filter=PropertyFilter(path="category", value="controls"),
        ),
    )
    controls_ids = {block.id for block in controls_records}
    assert controls_ids == {record_preventive_id, record_detective_id}

    limited = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD, root_id=document_id),
        limit=1,
    )
    assert len(limited) == 1


def test_query_blocks_supports_root_filters(repository, block_factory):
    document_controls_id = uuid4()
    document_policies_id = uuid4()
    dataset_controls_id = uuid4()
    dataset_policies_id = uuid4()
    record_controls_id = uuid4()
    record_policies_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_controls_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_controls_id,
                children_ids=(dataset_controls_id,),
                properties={"title": "Controls Handbook"},
            ),
            block_factory(
                block_id=document_policies_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_policies_id,
                children_ids=(dataset_policies_id,),
                properties={"title": "Policies Handbook"},
            ),
            block_factory(
                block_id=dataset_controls_id,
                block_type=BlockType.DATASET,
                parent_id=document_controls_id,
                root_id=document_controls_id,
                children_ids=(record_controls_id,),
                properties={"category": "controls"},
            ),
            block_factory(
                block_id=dataset_policies_id,
                block_type=BlockType.DATASET,
                parent_id=document_policies_id,
                root_id=document_policies_id,
                children_ids=(record_policies_id,),
                properties={"category": "policies"},
            ),
            block_factory(
                block_id=record_controls_id,
                block_type=BlockType.RECORD,
                parent_id=dataset_controls_id,
                root_id=document_controls_id,
                content=Content(data={"category": "Preventive"}),
            ),
            block_factory(
                block_id=record_policies_id,
                block_type=BlockType.RECORD,
                parent_id=dataset_policies_id,
                root_id=document_policies_id,
                content=Content(data={"category": "Detective"}),
            ),
        ]
    )

    controls_records = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD),
        root=RootFilter(
            where=WhereClause(type=BlockType.DOCUMENT),
            property_filter=PropertyFilter(
                path="properties.title",
                value="Controls Handbook",
            ),
        ),
    )

    assert [block.id for block in controls_records] == [record_controls_id]

    policies_datasets = repository.query_blocks(
        where=WhereClause(type=BlockType.DATASET),
        root=RootFilter(
            property_filter=PropertyFilter(
                path="properties.title",
                value="Policies Handbook",
            ),
        ),
    )

    assert [block.id for block in policies_datasets] == [dataset_policies_id]


def test_in_trash_flag_controls_visibility(repository, block_factory):
    document_id = uuid4()
    heading_id = uuid4()
    paragraph_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
                children_ids=(heading_id,),
            ),
            block_factory(
                block_id=heading_id,
                block_type=BlockType.HEADING,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(paragraph_id,),
            ),
            block_factory(
                block_id=paragraph_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=heading_id,
                root_id=document_id,
            ),
        ]
    )

    repository.set_in_trash([heading_id, paragraph_id], in_trash=True)

    assert repository.get_block(heading_id) is None
    assert repository.get_block(paragraph_id) is None
    hidden_heading = repository.get_block(heading_id, include_trashed=True)
    assert hidden_heading is not None
    assert hidden_heading.in_trash is True

    paragraphs = repository.query_blocks(where=WhereClause(type=BlockType.PARAGRAPH))
    assert paragraphs == []
    all_paragraphs = repository.query_blocks(
        where=WhereClause(type=BlockType.PARAGRAPH),
        include_trashed=True,
    )
    assert [block.id for block in all_paragraphs] == [paragraph_id]

    document = repository.get_block(document_id, depth=0)
    assert document is not None
    assert document.children_ids == (heading_id,)

    repository.set_in_trash([heading_id, paragraph_id], in_trash=False)

    restored_paragraph = repository.get_block(paragraph_id)
    assert restored_paragraph is not None
    assert restored_paragraph.parent_id == heading_id


def test_query_blocks_supports_nested_json_paths_and_operators(repository, block_factory):
    document_id = uuid4()
    dataset_id = uuid4()
    record_active_id = uuid4()
    record_draft_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
                children_ids=(dataset_id,),
            ),
            block_factory(
                block_id=dataset_id,
                block_type=BlockType.DATASET,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(record_active_id, record_draft_id),
                properties={"category": "controls"},
            ),
            block_factory(
                block_id=record_active_id,
                block_type=BlockType.RECORD,
                parent_id=dataset_id,
                root_id=document_id,
                content=Content(
                    data={"category": "Preventive"},
                    object={"status": "Active", "tags": ["finance", "risk"]},
                    plain_text="Preventive Control summary",
                ),
            ),
            block_factory(
                block_id=record_draft_id,
                block_type=BlockType.RECORD,
                parent_id=dataset_id,
                root_id=document_id,
                content=Content(
                    data={"category": "Detective"},
                    object={"status": "Draft", "tags": ["operations"]},
                    plain_text="Detective insight note",
                ),
            ),
        ]
    )

    nested_match = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD),
        property_filter=PropertyFilter(
            path="content.object.status",
            value="Active",
        ),
    )
    assert [block.id for block in nested_match] == [record_active_id]

    prefixed_match = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD),
        property_filter=PropertyFilter(
            path="content.data.category",
            value="Detective",
        ),
    )
    assert [block.id for block in prefixed_match] == [record_draft_id]

    not_equals_match = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD),
        property_filter=PropertyFilter(
            path="content.object.status",
            value="Retired",
            operator=FilterOperator.NOT_EQUALS,
        ),
    )
    assert {block.id for block in not_equals_match} == {record_active_id, record_draft_id}

    in_match = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD),
        property_filter=PropertyFilter(
            path="content.data.category",
            value=["Preventive", "Detective"],
            operator=FilterOperator.IN,
        ),
    )
    assert {block.id for block in in_match} == {record_active_id, record_draft_id}

    contains_match = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD),
        property_filter=PropertyFilter(
            path="content.plain_text",
            value="Control",
            operator=FilterOperator.CONTAINS,
        ),
    )
    assert [block.id for block in contains_match] == [record_active_id]

    and_filter = BooleanFilter(
        operator=LogicalOperator.AND,
        operands=(
            PropertyFilter(path="content.object.status", value="Active"),
            PropertyFilter(path="content.data.category", value="Preventive"),
        ),
    )
    and_match = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD),
        property_filter=and_filter,
    )
    assert [block.id for block in and_match] == [record_active_id]

    or_filter = BooleanFilter(
        operator=LogicalOperator.OR,
        operands=(
            PropertyFilter(path="content.object.status", value="Draft"),
            PropertyFilter(path="content.object.status", value="Retired"),
        ),
    )
    or_match = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD),
        property_filter=or_filter,
    )
    assert [block.id for block in or_match] == [record_draft_id]

    not_filter = BooleanFilter(
        operator=LogicalOperator.NOT,
        operands=(PropertyFilter(path="content.object.status", value="Draft"),),
    )
    not_match = repository.query_blocks(
        where=WhereClause(type=BlockType.RECORD),
        property_filter=not_filter,
    )
    assert {block.id for block in not_match} == {record_active_id}
