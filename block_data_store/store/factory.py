"""Factory helpers for constructing the document store façade."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from block_data_store.repositories.block_repository import BlockRepository

from .document_store import DocumentStore


def create_document_store(session_factory: sessionmaker[Session]) -> DocumentStore:
    """Build a DocumentStore with the default repository implementation."""
    repository = BlockRepository(session_factory)
    return DocumentStore(repository)


__all__ = ["create_document_store"]
