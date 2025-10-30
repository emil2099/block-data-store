"""Database engine helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_SQLITE_URL = "sqlite+pysqlite:///:memory:"


def create_engine(
    connection_string: str | None = None,
    *,
    sqlite_path: str | Path | None = None,
    echo: bool = False,
    connect_args: Mapping[str, Any] | None = None,
) -> Engine:
    """Create a SQLAlchemy engine with optional persistent SQLite or custom URLs.

    Parameters
    ----------
    connection_string:
        Full SQLAlchemy URL. Takes precedence over ``sqlite_path``.
    sqlite_path:
        Filesystem path to a SQLite database file. Expanded to an absolute path.
    echo:
        Enable SQLAlchemy engine echo logging.
    connect_args:
        Optional mapping passed through to ``sqlalchemy.create_engine``.

    Notes
    -----
    - When neither ``connection_string`` nor ``sqlite_path`` are provided, an
      in-memory SQLite URL is used (the previous default behaviour).
    - ``sqlite_path`` accepts strings or ``pathlib.Path`` instances and expands
      user/home references.
    """
    if connection_string and sqlite_path is not None:
        raise ValueError("Provide either 'connection_string' or 'sqlite_path', not both.")

    if connection_string:
        url = connection_string
    elif sqlite_path is not None:
        db_path = Path(sqlite_path).expanduser().resolve()
        url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    else:
        url = DEFAULT_SQLITE_URL

    return sa_create_engine(url, echo=echo, future=True, connect_args=connect_args or {})


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a configured session factory bound to the given engine."""
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False, future=True)
