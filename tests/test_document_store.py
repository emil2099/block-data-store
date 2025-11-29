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
                content=Content(plain_text="Intro"),
            ),
        ]
    )

    document = document_store.get_root_tree(document_id, depth=1)
    assert document.id == document_id
    assert document.children()[0].id == heading_id


def test_get_root_tree_allows_non_document_roots(document_store, repository, block_factory):
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

    result = document_store.get_root_tree(heading_id)
    assert result.id == heading_id


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


def test_set_in_trash_cascades_descendants(document_store, repository, block_factory):
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
                properties={"level": 2},
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

    document_store.set_in_trash([heading_id], in_trash=True)

    document = document_store.get_root_tree(document_id, depth=None)
    assert document.children_ids == (heading_id,)
    assert document.children() == []
    heading = repository.get_block(heading_id, include_trashed=True)
    paragraph = repository.get_block(paragraph_id, include_trashed=True)
    assert heading is not None and heading.in_trash
    assert paragraph is not None and paragraph.in_trash


def test_restore_unsets_trash_for_descendants(document_store, repository, block_factory):
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

    document_store.set_in_trash([heading_id], in_trash=True)
    document_store.set_in_trash([heading_id], in_trash=False)

    restored_heading = repository.get_block(heading_id)
    restored_paragraph = repository.get_block(paragraph_id)
    assert restored_heading is not None and not restored_heading.in_trash
    assert restored_paragraph is not None and not restored_paragraph.in_trash


def test_trashing_document_makes_root_inaccessible(document_store, repository, block_factory):
    document_id = uuid4()

    repository.upsert_blocks(
        [
            block_factory(
                block_id=document_id,
                block_type=BlockType.DOCUMENT,
                parent_id=None,
                root_id=document_id,
            )
        ]
    )

    document_store.set_in_trash([document_id], in_trash=True)

    with pytest.raises(DocumentStoreError):
        document_store.get_root_tree(document_id, depth=0)
