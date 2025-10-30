"""Filter primitives and helpers for Block repository queries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable, Sequence
from uuid import UUID

from sqlalchemy import and_, not_, or_
from sqlalchemy.sql.elements import ClauseElement

from block_data_store.models.block import BlockType


@dataclass(frozen=True, slots=True)
class WhereClause:
    """Structural filters applied to blocks (type, parent, root)."""

    type: BlockType | str | None = None
    parent_id: UUID | str | None = None
    root_id: UUID | str | None = None


class FilterOperator(str, Enum):
    """Supported comparison operators for JSON property filters."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    CONTAINS = "contains"


@dataclass(frozen=True, slots=True)
class PropertyFilter:
    """Semantic filter specifying a JSON path match with an operator."""

    path: str
    value: Any
    operator: FilterOperator = FilterOperator.EQUALS

    def __post_init__(self) -> None:
        if not self.path or not self.path.strip():
            raise ValueError("PropertyFilter.path cannot be empty.")
        if self.operator is FilterOperator.IN:
            if isinstance(self.value, (str, bytes)) or not isinstance(self.value, Iterable):
                raise TypeError(
                    "PropertyFilter with operator 'in' expects a non-string iterable value."
                )
        if self.operator is FilterOperator.CONTAINS and not isinstance(self.value, str):
            raise TypeError(
                "PropertyFilter with operator 'contains' expects a string value."
            )


@dataclass(frozen=True, slots=True)
class BooleanFilter:
    """Boolean composition of property filters."""

    operator: "LogicalOperator"
    operands: tuple["FilterExpression", ...]

    def __post_init__(self) -> None:
        if not self.operands:
            raise ValueError("BooleanFilter requires at least one operand.")
        if self.operator in (LogicalOperator.AND, LogicalOperator.OR) and len(self.operands) < 2:
            raise ValueError(f"{self.operator.value} requires two or more operands.")
        if self.operator is LogicalOperator.NOT and len(self.operands) != 1:
            raise ValueError("NOT requires exactly one operand.")


class LogicalOperator(str, Enum):
    """Supported boolean operators for filter composition."""

    AND = "and"
    OR = "or"
    NOT = "not"


FilterExpression = PropertyFilter | BooleanFilter


@dataclass(frozen=True, slots=True)
class ParentFilter:
    """Composite filter applied to a block's canonical parent."""

    where: WhereClause | None = None
    property_filter: "FilterExpression | None" = None


def apply_structural_filters(query, model, where: WhereClause):
    """Apply structural filters (type/parent/root) to a SQLAlchemy query."""
    if where.type is not None:
        type_value = where.type.value if isinstance(where.type, BlockType) else str(where.type)
        query = query.filter(model.type == type_value)
    if where.parent_id is not None:
        query = query.filter(model.parent_id == str(where.parent_id))
    if where.root_id is not None:
        query = query.filter(model.root_id == str(where.root_id))
    return query


def _resolve_json_filter_target(model, path: str) -> tuple[Any, list[str]]:
    segments = [segment for segment in path.split(".") if segment]
    if not segments:
        raise ValueError("JSON path cannot be empty.")

    column_map: dict[str, str] = {
        "properties": "properties",
        "content": "content",
        "metadata": "metadata_json",
    }

    first_segment = segments[0]
    if first_segment in column_map:
        column_name = column_map[first_segment]
        json_segments = segments[1:]
    else:
        column_name = "properties"
        json_segments = segments

    try:
        column = getattr(model, column_name)
    except AttributeError as exc:
        raise ValueError(f"Model does not expose column '{column_name}'.") from exc

    return column, json_segments


def _build_json_path_expression(column: ClauseElement, segments: Sequence[str]) -> ClauseElement:
    expression = column
    for segment in segments:
        if segment.isdigit():
            expression = expression[int(segment)]
        else:
            expression = expression[segment]
    return expression


def _expect_bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"Expected value of type bool, received {type(value).__name__}.")
    return value


def _expect_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Expected value of type int, received {type(value).__name__}.")
    return value


def _expect_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            "Expected value of type float (or int), "
            f"received {type(value).__name__}."
        )
    return float(value)


def _expect_str(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Expected value of type str, received {type(value).__name__}.")
    return value


def _coerce_expression(
    expression: ClauseElement, sample_value: Any
) -> tuple[ClauseElement, Callable[[Any], Any]]:
    comparator = expression.comparator

    if isinstance(sample_value, bool):
        return comparator.as_boolean(), _expect_bool
    if isinstance(sample_value, int) and not isinstance(sample_value, bool):
        return comparator.as_integer(), _expect_int
    if isinstance(sample_value, float):
        return comparator.as_float(), _expect_float

    return comparator.as_string(), _expect_str


def _build_property_expression(model, property_filter: PropertyFilter) -> ClauseElement:
    column, segments = _resolve_json_filter_target(model, property_filter.path)
    json_expression = _build_json_path_expression(column, segments)
    operator = property_filter.operator

    if operator is FilterOperator.EQUALS:
        coerced_expression, convert = _coerce_expression(json_expression, property_filter.value)
        return coerced_expression == convert(property_filter.value)
    if operator is FilterOperator.NOT_EQUALS:
        coerced_expression, convert = _coerce_expression(json_expression, property_filter.value)
        return coerced_expression != convert(property_filter.value)
    if operator is FilterOperator.IN:
        values = list(property_filter.value)
        if not values:
            raise ValueError("PropertyFilter with operator 'in' requires at least one value.")
        coerced_expression, convert = _coerce_expression(json_expression, values[0])
        converted_values = [convert(value) for value in values]
        return coerced_expression.in_(converted_values)
    if operator is FilterOperator.CONTAINS:
        comparator = json_expression.comparator.as_string()
        return comparator.contains(property_filter.value)

    raise ValueError(f"Unsupported filter operator: {operator}")


def build_filter_expression(model, filter_expression: FilterExpression) -> ClauseElement:
    """Construct a SQLAlchemy expression for the provided filter expression."""
    if isinstance(filter_expression, PropertyFilter):
        return _build_property_expression(model, filter_expression)
    if isinstance(filter_expression, BooleanFilter):
        compiled_operands = [
            build_filter_expression(model, operand) for operand in filter_expression.operands
        ]
        if filter_expression.operator is LogicalOperator.AND:
            return and_(*compiled_operands)
        if filter_expression.operator is LogicalOperator.OR:
            return or_(*compiled_operands)
        if filter_expression.operator is LogicalOperator.NOT:
            return not_(compiled_operands[0])
        raise ValueError(f"Unsupported logical operator: {filter_expression.operator}")

    raise TypeError(f"Unsupported filter expression type: {type(filter_expression)!r}")


__all__ = [
    "BooleanFilter",
    "FilterExpression",
    "FilterOperator",
    "LogicalOperator",
    "ParentFilter",
    "PropertyFilter",
    "WhereClause",
    "apply_structural_filters",
    "build_filter_expression",
]
