from __future__ import annotations

from pathlib import Path

import pytest

from block_data_store.db.engine import create_engine


def test_create_engine_supports_sqlite_path(tmp_path: Path) -> None:
    db_path = tmp_path / "blocks.db"

    engine = create_engine(sqlite_path=db_path)

    expected_url = f"sqlite+pysqlite:///{db_path.resolve().as_posix()}"
    assert str(engine.url) == expected_url


def test_create_engine_rejects_conflicting_configuration(tmp_path: Path) -> None:
    db_path = tmp_path / "blocks.db"

    with pytest.raises(ValueError):
        create_engine(connection_string="sqlite:///ignored.db", sqlite_path=db_path)
