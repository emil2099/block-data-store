from __future__ import annotations

from uuid import uuid4

import pytest

from block_data_store.models.block import BlockType, Content
from block_data_store.store import DocumentStoreError


def test_get_document_hydrates_tree(document_store, repository, block_factory):
    document_id = uuid4()
    heading_id = uuid4()

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
                properties={"level": 2},
                content=Content(text="Intro"),
            ),
        ]
    )

    document = document_store.get_root_tree(document_id, depth=1)
    assert document.id == document_id
    assert document.children()[0].id == heading_id


def test_get_document_rejects_non_document_roots(document_store, repository, block_factory):
    heading_id = uuid4()
    repository.upsert_blocks(
        [
            block_factory(
                block_id=heading_id,
                block_type=BlockType.HEADING,
                parent_id=None,
                root_id=heading_id,
            )
        ]
    )

    with pytest.raises(DocumentStoreError):
        document_store.get_root_tree(heading_id)


def test_move_block_auto_fills_versions(document_store, repository, block_factory):
    document_id = uuid4()
    heading_a_id = uuid4()
    heading_b_id = uuid4()
    paragraph_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
                children_ids=(heading_a_id, heading_b_id),
            ),
            block_factory(
                block_id=heading_a_id,
                block_type=BlockType.HEADING,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(paragraph_id,),
            ),
            block_factory(
                block_id=heading_b_id,
                block_type=BlockType.HEADING,
                parent_id=document_id,
                root_id=document_id,
            ),
            block_factory(
                block_id=paragraph_id,
                block_type=BlockType.PARAGRAPH,
                parent_id=heading_a_id,
                root_id=document_id,
            ),
        ]
    )

    document_store.move_block(paragraph_id, heading_b_id, index=0)

    moved_parent = repository.get_block(heading_b_id)
    moved_child = repository.get_block(paragraph_id)
    assert moved_parent is not None
    assert moved_child is not None
    assert moved_parent.children_ids == (paragraph_id,)
    assert moved_child.parent_id == heading_b_id


def test_set_children_without_version(document_store, repository, block_factory):
    heading_id = uuid4()
    para_a = uuid4()
    para_b = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=heading_id,
                block_type=BlockType.HEADING,
                parent_id=None,
                root_id=heading_id,
                children_ids=(para_a, para_b),
            ),
            block_factory(
                block_id=para_a,
                block_type=BlockType.PARAGRAPH,
                parent_id=heading_id,
                root_id=heading_id,
            ),
            block_factory(
                block_id=para_b,
                block_type=BlockType.PARAGRAPH,
                parent_id=heading_id,
                root_id=heading_id,
            ),
        ]
    )

    document_store.set_children(heading_id, (para_b, para_a))

    section = repository.get_block(heading_id)
    assert section is not None
    assert section.children_ids == (para_b, para_a)


def test_get_page_group_resolves_synced_children(document_store, repository, block_factory):
    document_id = uuid4()
    heading_a_id = uuid4()
    heading_b_id = uuid4()
    page_group_id = uuid4()
    synced_a_id = uuid4()
    synced_b_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
                children_ids=(heading_a_id, heading_b_id, page_group_id),
            ),
            block_factory(
                block_id=heading_a_id,
                block_type=BlockType.HEADING,
                parent_id=document_id,
                root_id=document_id,
                properties={"level": 2},
                content=Content(text="A"),
            ),
            block_factory(
                block_id=heading_b_id,
                block_type=BlockType.HEADING,
                parent_id=document_id,
                root_id=document_id,
                properties={"level": 2},
                content=Content(text="B"),
            ),
            block_factory(
                block_id=page_group_id,
                block_type=BlockType.PAGE_GROUP,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(synced_a_id, synced_b_id),
            ),
            block_factory(
                block_id=synced_a_id,
                block_type=BlockType.SYNCED,
                parent_id=page_group_id,
                root_id=document_id,
                content={"synced_from": heading_a_id},
            ),
            block_factory(
                block_id=synced_b_id,
                block_type=BlockType.SYNCED,
                parent_id=page_group_id,
                root_id=document_id,
                content={"synced_from": heading_b_id},
            ),
        ]
    )

    view = document_store.get_slice(page_group_id, resolve_synced=True)

    assert view.page_group.id == page_group_id
    assert [child.id for child in view.synced_children] == [synced_a_id, synced_b_id]
    assert [resolved.target.id for resolved in view.resolved_children] == [heading_a_id, heading_b_id]


def test_get_page_group_rejects_non_page_group(document_store, repository, block_factory):
    heading_id = uuid4()
    repository.upsert_blocks(
        [
            block_factory(
                block_id=heading_id,
                block_type=BlockType.HEADING,
                parent_id=None,
                root_id=heading_id,
            )
        ]
    )

    with pytest.raises(DocumentStoreError):
        document_store.get_slice(heading_id)


def test_get_page_group_errors_when_synced_reference_missing(document_store, repository, block_factory):
    document_id = uuid4()
    page_group_id = uuid4()
    synced_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
                children_ids=(page_group_id,),
            ),
            block_factory(
                block_id=page_group_id,
                block_type=BlockType.PAGE_GROUP,
                parent_id=document_id,
                root_id=document_id,
                children_ids=(synced_id,),
            ),
            block_factory(
                block_id=synced_id,
                block_type=BlockType.SYNCED,
                parent_id=page_group_id,
                root_id=document_id,
                # missing synced_from
                content={},
            ),
        ]
    )

    with pytest.raises(DocumentStoreError):
        document_store.get_slice(page_group_id)
