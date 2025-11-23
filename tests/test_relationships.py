"""Tests for relationship functionality in DocumentStore."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from block_data_store.models.block import BlockType
from block_data_store.store import DocumentStore


from block_data_store.models.relationship import Relationship

def test_create_relationship(document_store: DocumentStore, block_factory):
    """Verify basic relationship creation."""
    root_id = uuid4()
    workspace_id = uuid4()
    block_a = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    block_b = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    document_store.save_blocks([block_a, block_b])

    rel = Relationship(
        workspace_id=str(workspace_id),
        source_block_id=str(block_a.id),
        target_block_id=str(block_b.id),
        rel_type="supports"
    )
    document_store.upsert_relationships([rel])

    # Verify it exists
    rels = document_store.get_relationships(block_a.id, direction="outgoing")
    assert len(rels) == 1
    assert rels[0].target_block_id == str(block_b.id)
    assert rels[0].rel_type == "supports"


def test_relationship_directionality(document_store: DocumentStore, block_factory):
    """Verify relationships are directional."""
    root_id = uuid4()
    workspace_id = uuid4()
    block_a = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    block_b = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    document_store.save_blocks([block_a, block_b])

    rel = Relationship(
        workspace_id=str(workspace_id),
        source_block_id=str(block_a.id),
        target_block_id=str(block_b.id),
        rel_type="supports"
    )
    document_store.upsert_relationships([rel])

    # Check outgoing from A
    rels_a = document_store.get_relationships(block_a.id, direction="outgoing")
    assert len(rels_a) == 1
    assert rels_a[0].target_block_id == str(block_b.id)

    # Check incoming to A (should be empty)
    rels_a_in = document_store.get_relationships(block_a.id, direction="incoming")
    assert len(rels_a_in) == 0

    # Check incoming to B
    rels_b = document_store.get_relationships(block_b.id, direction="incoming")
    assert len(rels_b) == 1
    assert rels_b[0].source_block_id == str(block_a.id)


def test_relationship_uniqueness(document_store: DocumentStore, block_factory):
    """Verify duplicate relationships are handled (idempotent creation)."""
    root_id = uuid4()
    workspace_id = uuid4()
    block_a = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    block_b = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    document_store.save_blocks([block_a, block_b])

    rel1 = Relationship(
        workspace_id=str(workspace_id),
        source_block_id=str(block_a.id),
        target_block_id=str(block_b.id),
        rel_type="supports"
    )
    # Create twice
    document_store.upsert_relationships([rel1])
    document_store.upsert_relationships([rel1])

    rels = document_store.get_relationships(block_a.id)
    assert len(rels) == 1


def test_delete_relationship(document_store: DocumentStore, block_factory):
    """Verify relationship deletion."""
    root_id = uuid4()
    workspace_id = uuid4()
    block_a = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    block_b = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    document_store.save_blocks([block_a, block_b])

    rel = Relationship(
        workspace_id=str(workspace_id),
        source_block_id=str(block_a.id),
        target_block_id=str(block_b.id),
        rel_type="supports"
    )
    document_store.upsert_relationships([rel])
    
    deleted = document_store.delete_relationships([(block_a.id, block_b.id, "supports")])
    assert deleted is True

    rels = document_store.get_relationships(block_a.id)
    assert len(rels) == 0


def test_soft_delete_visibility(document_store: DocumentStore, block_factory):
    """Verify relationships are hidden when endpoints are trashed."""
    root_id = uuid4()
    workspace_id = uuid4()
    block_a = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    block_b = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    document_store.save_blocks([block_a, block_b])

    rel = Relationship(
        workspace_id=str(workspace_id),
        source_block_id=str(block_a.id),
        target_block_id=str(block_b.id),
        rel_type="supports"
    )
    document_store.upsert_relationships([rel])

    # Trash block B
    document_store.set_in_trash([block_b.id], in_trash=True)

    # Should be hidden by default
    rels = document_store.get_relationships(block_a.id)
    assert len(rels) == 0

    # Should be visible if include_trashed=True
    rels_trashed = document_store.get_relationships(block_a.id, include_trashed=True)
    assert len(rels_trashed) == 1


def test_hard_delete_cascade(document_store: DocumentStore, block_factory, engine):
    """Verify DB cascade deletes relationships when block is hard deleted."""
    root_id = uuid4()
    workspace_id = uuid4()
    block_a = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    block_b = block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
    document_store.save_blocks([block_a, block_b])

    rel = Relationship(
        workspace_id=str(workspace_id),
        source_block_id=str(block_a.id),
        target_block_id=str(block_b.id),
        rel_type="supports"
    )
    document_store.upsert_relationships([rel])

    # Hard delete block A via SQL
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM blocks WHERE id = :id"), {"id": str(block_a.id)})

    # Verify relationship is gone
    rels = document_store.get_relationships(block_b.id, include_trashed=True)
    assert len(rels) == 0


def test_batch_create_relationships(document_store: DocumentStore, block_factory):
    """Verify batch relationship creation."""
    root_id = uuid4()
    workspace_id = uuid4()
    blocks = [
        block_factory(block_type=BlockType.PARAGRAPH, parent_id=None, root_id=root_id, workspace_id=workspace_id)
        for _ in range(5)
    ]
    document_store.save_blocks(blocks)

    # Create chain: 0->1, 1->2, 2->3, 3->4
    rels = [
        Relationship(
            workspace_id=str(workspace_id),
            source_block_id=str(blocks[i].id),
            target_block_id=str(blocks[i+1].id),
            rel_type="next",
            metadata={"index": i}
        )
        for i in range(4)
    ]

    document_store.upsert_relationships(rels)
    
    # Verify persistence
    all_rels = []
    for i in range(4):
        rels = document_store.get_relationships(blocks[i].id, direction="outgoing")
        all_rels.extend(rels)
    
    assert len(all_rels) == 4
