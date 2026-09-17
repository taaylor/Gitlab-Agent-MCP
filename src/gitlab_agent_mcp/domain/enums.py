"""Domain enumerations."""

from enum import StrEnum


class TaskType(StrEnum):
    """Supported GitFlow task categories."""

    FEATURE = "feature"
    BUGFIX = "bugfix"
    CHORE = "chore"


class DiffSide(StrEnum):
    """A side of a Git diff."""

    OLD = "old"
    NEW = "new"
    BOTH = "both"
