from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Callable

import pytest
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from block_data_store.db.engine import create_engine
from block_data_store.db.schema import Base, DbBlock, create_all
from block_data_store.models.block import Block, BlockType, Content, block_class_for, properties_model_for
from block_data_store.repositories.block_repository import BlockRepository
from block_data_store.store import DocumentStore, create_document_store


@pytest.fixture(scope="session")
def postgres_url() -> str | None:
    """Return the Postgres test URL if provided via env."""
    return os.getenv("POSTGRES_TEST_URL") or os.getenv("DATABASE_URL")


@pytest.fixture
def engine(postgres_url: str | None) -> Iterator[Engine]:
    """Yield an engine targeting Postgres when configured; otherwise SQLite in-memory."""
    engine = create_engine(postgres_url) if postgres_url else create_engine()
    
    if engine.dialect.name == "sqlite":
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    create_all(engine)
    try:
        yield engine
    finally:
        with engine.begin() as connection:
            if engine.dialect.name == "sqlite":
                Base.metadata.drop_all(bind=connection)
            else:
                connection.execute(DbBlock.__table__.delete())


@pytest.fixture
def session_factory(engine: Engine):
    from block_data_store.db.engine import create_session_factory

    return create_session_factory(engine)


@pytest.fixture
def repository(session_factory) -> BlockRepository:
    return BlockRepository(session_factory)


@pytest.fixture
def document_store(session_factory) -> DocumentStore:
    return create_document_store(session_factory)


@pytest.fixture
def block_factory() -> Callable[..., Block]:
    from datetime import datetime, timezone
    from uuid import uuid4

    def _factory(
        *,
        block_type,
        parent_id,
        root_id,
        children_ids=(),
        content=None,
        properties=None,
        metadata=None,
        block_id=None,
        workspace_id=None,
    ) -> Block:
        timestamp = datetime.now(timezone.utc)
        block_cls = block_class_for(block_type)
        return block_cls(
            id=block_id or uuid4(),
            type=block_type,
            parent_id=parent_id,
            root_id=root_id,
            children_ids=tuple(children_ids),
            workspace_id=workspace_id,
            version=0,
            created_time=timestamp,
            last_edited_time=timestamp,
            created_by=None,
            last_edited_by=None,
            properties=_normalise_properties(block_type, properties),
            metadata=metadata or {},
            content=_normalise_content(content),
        )

    return _factory


def _normalise_properties(block_type: BlockType, properties: dict | BaseModel | None) -> BaseModel:
    props_cls = properties_model_for(block_type)
    if isinstance(properties, BaseModel):
        return properties
    return props_cls(**(properties or {}))


def _normalise_content(content) -> Content | None:
    if content is None:
        return None
    if isinstance(content, Content):
        return content
    if isinstance(content, str):
        return Content(plain_text=content)
    if isinstance(content, dict):
        return Content(**content)
    raise TypeError(f"Unsupported content payload: {type(content)!r}")
