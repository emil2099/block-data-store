"""Tests for atomic parent-child updates in upsert_blocks."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from block_data_store.models.block import BlockType, Content
from block_data_store.models.blocks import DocumentBlock, HeadingBlock, ParagraphBlock
from block_data_store.store import DocumentStoreError


def _now():
    """Helper to get current UTC datetime."""
    return datetime.now(timezone.utc)


def test_upsert_blocks_backward_compatible(document_store):
    """Test that upsert_blocks without parameters works as before."""
    doc = DocumentBlock(
        id=uuid4(),
        parent_id=None,
        root_id=uuid4(),
        created_time=_now(),
        last_edited_time=_now(),
        properties={"title": "Test Document"},
    )
    para = ParagraphBlock(
        id=uuid4(),
        parent_id=doc.id,
        root_id=doc.id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={},
        content=Content(plain_text="Test paragraph"),
    )

    # Old-style usage should still work
    document_store.upsert_blocks([doc, para])

    # Verify blocks were saved
    saved_doc = document_store.get_block(doc.id)
    saved_para = document_store.get_block(para.id)

    assert saved_doc is not None
    assert saved_para is not None
    assert saved_para.parent_id == doc.id


def test_upsert_blocks_with_parent_append_to_end(document_store):
    """Test appending blocks to parent (no insert_after)."""
    workspace = DocumentBlock(
        id=uuid4(),
        parent_id=None,
        root_id=uuid4(),
        created_time=_now(),
        last_edited_time=_now(),
        properties={"title": "Workspace"},
    )
    document_store.upsert_blocks([workspace])

    # Add a document to workspace
    doc_id = uuid4()
    doc = DocumentBlock(
        id=doc_id,
        parent_id=None,
        root_id=doc_id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={"title": "New Document"},
    )

    document_store.upsert_blocks([doc], parent_id=workspace.id)

    # Verify workspace children updated
    updated_workspace = document_store.get_block(workspace.id)
    assert doc.id in updated_workspace.children_ids
    assert len(updated_workspace.children_ids) == 1

    # Verify document parent updated
    saved_doc = document_store.get_block(doc.id)
    assert saved_doc.parent_id == workspace.id


def test_upsert_blocks_with_insert_after(document_store):
    """Test inserting blocks after a specific child."""
    doc_id = uuid4()
    doc = DocumentBlock(
        id=doc_id,
        parent_id=None,
        root_id=doc_id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={"title": "Document"},
    )
    para1 = ParagraphBlock(
        id=uuid4(),
        parent_id=doc.id,
        root_id=doc.id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={},
        content=Content(plain_text="First"),
    )
    para2 = ParagraphBlock(
        id=uuid4(),
        parent_id=doc.id,
        root_id=doc.id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={},
        content=Content(plain_text="Second"),
    )

    # Save document with two paragraphs
    document_store.upsert_blocks([doc])
    document_store.upsert_blocks([para1, para2], parent_id=doc.id)

    # Insert new paragraph after para1
    para_new = ParagraphBlock(
        id=uuid4(),
        parent_id=None,
        root_id=doc.id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={},
        content=Content(plain_text="Inserted"),
    )

    document_store.upsert_blocks(
        [para_new],
        parent_id=doc.id,
        insert_after=para1.id
    )

    # Verify order: para1, para_new, para2
    updated_doc = document_store.get_block(doc.id)
    assert list(updated_doc.children_ids) == [para1.id, para_new.id, para2.id]


def test_upsert_blocks_top_level_only_single_document(document_store):
    """Test that only top-level block is added as child (single document tree)."""
    workspace_id = uuid4()
    workspace = DocumentBlock(
        id=workspace_id,
        parent_id=None,
        root_id=workspace_id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={"title": "Workspace"},
    )
    document_store.upsert_blocks([workspace])

    # Create document with nested content
    doc_id = uuid4()
    heading_id = uuid4()
    para_id = uuid4()
    
    doc = DocumentBlock(
        id=doc_id,
        parent_id=None,
        root_id=doc_id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={"title": "Document"},
    )
    heading = HeadingBlock(
        id=heading_id,
        parent_id=doc_id,
        root_id=doc_id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={"level": 1},
        content=Content(plain_text="Heading"),
    )
    para = ParagraphBlock(
        id=para_id,
        parent_id=heading_id,
        root_id=doc_id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={},
        content=Content(plain_text="Paragraph"),
    )
    
    # Update to reflect full tree structure
    doc = doc.model_copy(update={"children_ids": (heading_id,)})
    heading = heading.model_copy(update={"children_ids": (para_id,)})

    # Save all blocks with parent_id (top_level_only=True by default)
    document_store.upsert_blocks([doc, heading, para], parent_id=workspace.id)

    # Verify only document is child of workspace
    updated_workspace = document_store.get_block(workspace.id, depth=2)
    assert list(updated_workspace.children_ids) == [doc.id]

    # Verify all blocks were saved
    assert document_store.get_block(doc.id) is not None
    assert document_store.get_block(heading.id) is not None
    assert document_store.get_block(para.id) is not None

    # Verify document's hierarchy preserved
    saved_doc = document_store.get_block(doc.id, depth=2)
    assert heading.id in saved_doc.children_ids


def test_upsert_blocks_top_level_only_batch_documents(document_store):
    """Test batch upload of multiple documents (only documents added as children)."""
    workspace_id = uuid4()
    workspace = DocumentBlock(
        id=workspace_id,
        parent_id=None,
        root_id=workspace_id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={"title": "Workspace"},
    )
    document_store.upsert_blocks([workspace])

    # Create 3 documents with content
    blocks = []
    doc_ids = []

    for i in range(3):
        doc_id = uuid4()
        doc_ids.append(doc_id)
        doc = DocumentBlock(
            id=doc_id,
            parent_id=None,
            root_id=doc_id,
            created_time=_now(),
            last_edited_time=_now(),
            properties={"title": f"Document {i}"},
        )
        para = ParagraphBlock(
            id=uuid4(),
            parent_id=doc_id,
            root_id=doc_id,
            created_time=_now(),
            last_edited_time=_now(),
            properties={},
            content=Content(plain_text=f"Content {i}"),
        )
        blocks.extend([doc, para])

    # Save all in one call
    document_store.upsert_blocks(blocks, parent_id=workspace.id)

    # Verify only 3 documents added to workspace (not 6 blocks)
    updated_workspace = document_store.get_block(workspace.id)
    assert len(updated_workspace.children_ids) == 3
    assert set(updated_workspace.children_ids) == set(doc_ids)


def test_upsert_blocks_top_level_only_false(document_store):
    """Test top_level_only=False adds all blocks as children."""
    doc_id = uuid4()
    doc = DocumentBlock(
        id=doc_id,
        parent_id=None,
        root_id=doc_id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={"title": "Document"},
    )
    document_store.upsert_blocks([doc])

    # Create heading and paragraph
    heading = HeadingBlock(
        id=uuid4(),
        parent_id=None,
        root_id=doc.id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={"level": 1},
        content=Content(plain_text="Heading"),
    )
    para = ParagraphBlock(
        id=uuid4(),
        parent_id=heading.id,
        root_id=doc.id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={},
        content=Content(plain_text="Paragraph"),
    )

    # Save with top_level_only=False (adds ALL blocks as children)
    document_store.upsert_blocks(
        [heading, para],
        parent_id=doc.id,
        top_level_only=False
    )

    # Verify both blocks are children of document
    updated_doc = document_store.get_block(doc.id)
    assert heading.id in updated_doc.children_ids
    assert para.id in updated_doc.children_ids
    assert len(updated_doc.children_ids) == 2





def test_upsert_blocks_insert_after_not_found(document_store):
    """Test error when insert_after block not in parent's children."""
    doc_id = uuid4()
    doc = DocumentBlock(
        id=doc_id,
        parent_id=None,
        root_id=doc_id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={"title": "Document"},
    )
    document_store.upsert_blocks([doc])

    para = ParagraphBlock(
        id=uuid4(),
        parent_id=None,
        root_id=doc.id,
        created_time=_now(),
        last_edited_time=_now(),
        properties={},
        content=Content(plain_text="Paragraph"),
    )

    # Should fail - nonexistent insert_after
    with pytest.raises(DocumentStoreError, match="not found in parent"):
        document_store.upsert_blocks(
            [para],
            parent_id=doc.id,
            insert_after=uuid4()  # Doesn't exist
        )



