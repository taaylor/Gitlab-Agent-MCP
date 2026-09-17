"""JSON-safe conversion helpers for MCP responses."""

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any


def to_jsonable(value: object) -> Any:
    """Convert domain dataclasses into structures supported by MCP JSON output."""

    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: to_jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value
