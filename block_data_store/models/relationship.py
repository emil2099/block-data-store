"""Pydantic model for relationships."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Relationship(BaseModel):
    """Represents a directional relationship between two blocks.

    ``workspace_id`` is optional for now to align with block records; callers
    may supply it when multi-tenant scoping is desired, otherwise it can be
    left ``None`` and treated as unscoped.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str | None = None
    source_block_id: str
    target_block_id: str
    rel_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = 0
    created_time: datetime = Field(default_factory=datetime.now)
    last_edited_time: datetime = Field(default_factory=datetime.now)
    created_by: str | None = None
    last_edited_by: str | None = None

    model_config = ConfigDict(from_attributes=True)
