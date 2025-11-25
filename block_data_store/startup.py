"""Startup helpers for bootstrapping a workspace and store."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from block_data_store.models.block import BlockType
from block_data_store.models.blocks.workspace import WorkspaceBlock, WorkspaceProps
from block_data_store.repositories.filters import WhereClause
from block_data_store.store.document_store import DocumentStore


def ensure_workspace(
    store: DocumentStore,
    *,
    workspace_id: UUID | None = None,
    title: str = "Default Workspace",
) -> WorkspaceBlock:
    """Return an existing workspace block or create one if missing.

    - If `workspace_id` is provided, it is preferred; otherwise the first
      existing workspace is returned.
    - When none exist, a new `WorkspaceBlock` is created with the given title.
    """
    existing = store.query_blocks(where=WhereClause(type=BlockType.WORKSPACE))
    if workspace_id:
        for ws in existing:
            if ws.id == workspace_id:
                return ws
    if existing:
        return existing[0]

    ws_id = workspace_id or uuid4()
    now = datetime.now(timezone.utc)
    workspace = WorkspaceBlock(
        id=ws_id,
        parent_id=None,
        root_id=ws_id,
        children_ids=(),
        created_time=now,
        last_edited_time=now,
        properties=WorkspaceProps(title=title),
    )
    store.upsert_blocks([workspace])
    return workspace


__all__ = ["ensure_workspace"]
