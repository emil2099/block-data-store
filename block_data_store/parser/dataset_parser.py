"""Convert CSV/Excel sources into Dataset + Record blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import io
from pathlib import Path
from typing import IO, Any, Literal
from uuid import UUID, uuid4

from block_data_store.models.block import Block, Content
from block_data_store.models.blocks import DatasetBlock, DatasetProps, RecordBlock, RecordProps


@dataclass(slots=True)
class DatasetParserConfig:
    select_columns: list[str] | None = None
    title: str | None = None
    category: str | None = None
    data_schema: dict[str, Any] | None = None
    reader: Literal["auto", "csv", "excel"] = "auto"
    read_kwargs: dict[str, Any] = field(default_factory=dict)


def dataset_to_blocks(
    source: str | Path | bytes | IO[bytes],
    *,
    config: DatasetParserConfig | None = None,
    workspace_id: UUID | None = None,
    dataset_id: UUID | None = None,
    timestamp: datetime | None = None,
) -> list[Block]:
    """Parse a tabular source into a Dataset root with Record children."""

    cfg = config or DatasetParserConfig()
    timestamp = timestamp or datetime.now(timezone.utc)
    dataset_id = dataset_id or uuid4()

    df, source_name = _load_dataframe(source, cfg)
    if cfg.select_columns:
        missing = [column for column in cfg.select_columns if column not in df.columns]
        if missing:
            raise ValueError(f"Missing columns in dataset source: {missing}")
        df = df[cfg.select_columns]

    df = df.where(df.notna(), None)
    records = df.to_dict(orient="records")

    record_blocks: list[Block] = []
    record_ids: list[UUID] = []
    for row in records:
        record_id = uuid4()
        record_ids.append(record_id)
        record_blocks.append(
            RecordBlock(
                id=record_id,
                parent_id=dataset_id,
                root_id=dataset_id,
                children_ids=tuple(),
                workspace_id=workspace_id,
                version=0,
                created_time=timestamp,
                last_edited_time=timestamp,
                created_by=None,
                last_edited_by=None,
                properties=RecordProps(),
                metadata={},
                content=Content(data=row),
            )
        )

    metadata = {"source": "dataset_parser"}
    if source_name:
        metadata["original_name"] = source_name

    dataset_block = DatasetBlock(
        id=dataset_id,
        parent_id=None,
        root_id=dataset_id,
        children_ids=tuple(record_ids),
        workspace_id=workspace_id,
        version=0,
        created_time=timestamp,
        last_edited_time=timestamp,
        created_by=None,
        last_edited_by=None,
        properties=DatasetProps(
            title=cfg.title or source_name,
            category=cfg.category,
            data_schema=cfg.data_schema,
        ),
        metadata=metadata,
        content=None,
    )

    return [dataset_block, *record_blocks]


# ---------------------------------------------------------------------------
# Internals


def _load_dataframe(
    source: str | Path | bytes | IO[bytes],
    config: DatasetParserConfig,
):
    pandas = _import_pandas()

    path: Path | None = None
    buffer: IO[bytes] | None = None
    name: str | None = None

    if isinstance(source, (str, Path)):
        path = Path(source)
        name = path.name
        data_input: Any = path
    elif isinstance(source, (bytes, bytearray)):
        buffer = io.BytesIO(source)
        data_input = buffer
    elif hasattr(source, "read"):
        data = source.read()
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("Dataset parser expects byte streams")
        buffer = io.BytesIO(data)
        data_input = buffer
    else:
        raise TypeError("Unsupported source type for dataset parser")

    if buffer is not None:
        buffer.seek(0)

    reader = _determine_reader(config.reader, path)
    kwargs = dict(config.read_kwargs)

    if reader == "excel":
        dataframe = pandas.read_excel(data_input, **kwargs)
    else:
        dataframe = pandas.read_csv(data_input, **kwargs)

    dataframe.columns = [str(column) for column in dataframe.columns]
    return dataframe, name


def _determine_reader(desired: Literal["auto", "csv", "excel"], path: Path | None) -> Literal["csv", "excel"]:
    if desired != "auto":
        return desired
    if path:
        suffix = path.suffix.lower()
        if suffix in {".xls", ".xlsx"}:
            return "excel"
    return "csv"


def _import_pandas():  # pragma: no cover - simple import helper
    try:
        import pandas as pd  # type: ignore

        return pd
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "pandas is required for dataset parsing. Install with `pip install -r requirements.dataset.txt`."
        ) from exc


__all__ = ["DatasetParserConfig", "dataset_to_blocks"]
