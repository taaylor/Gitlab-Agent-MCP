"""Dependency-free domain entities."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ProjectRef:
    base_url: str
    project_path: str


@dataclass(frozen=True, slots=True)
class MergeRequestRef:
    project: ProjectRef
    iid: int


@dataclass(frozen=True, slots=True)
class User:
    username: str
    name: str | None = None
    web_url: str | None = None


@dataclass(frozen=True, slots=True)
class DiffRefs:
    base_sha: str
    head_sha: str
    start_sha: str


@dataclass(frozen=True, slots=True)
class MergeRequest:
    id: int
    iid: int
    project_id: int
    title: str
    description: str | None
    state: str
    web_url: str
    source_branch: str
    target_branch: str
    sha: str | None
    draft: bool
    author: User
    labels: tuple[str, ...] = ()
    detailed_merge_status: str | None = None
    diff_refs: DiffRefs | None = None


@dataclass(frozen=True, slots=True)
class ChangedFile:
    old_path: str
    new_path: str
    diff: str
    new_file: bool
    renamed_file: bool
    deleted_file: bool
    generated_file: bool = False
    collapsed: bool = False
    too_large: bool = False
    a_mode: str | None = None
    b_mode: str | None = None


@dataclass(frozen=True, slots=True)
class DiffPosition:
    base_sha: str
    head_sha: str
    start_sha: str
    old_path: str
    new_path: str
    old_line: int | None = None
    new_line: int | None = None
    position_type: str = "text"


@dataclass(frozen=True, slots=True)
class Suggestion:
    id: int | None
    from_line: int | None
    to_line: int | None
    appliable: bool | None
    applied: bool | None


@dataclass(frozen=True, slots=True)
class DiscussionNote:
    id: int
    body: str
    author: User
    type: str | None
    system: bool
    resolvable: bool
    resolved: bool
    created_at: str | None = None
    updated_at: str | None = None
    position: DiffPosition | None = None
    suggestions: tuple[Suggestion, ...] = ()


@dataclass(frozen=True, slots=True)
class Discussion:
    id: str
    individual_note: bool
    notes: tuple[DiscussionNote, ...]


@dataclass(frozen=True, slots=True)
class Pipeline:
    id: int
    status: str
    sha: str
    ref: str | None
    web_url: str | None
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineJob:
    id: int
    name: str
    stage: str
    status: str
    web_url: str | None
    allow_failure: bool
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass(frozen=True, slots=True)
class Project:
    id: int
    path_with_namespace: str
    web_url: str
    default_branch: str


@dataclass(frozen=True, slots=True)
class ProjectLabel:
    name: str
    color: str | None
    description: str | None
    is_project_label: bool | None
    archived: bool = False


@dataclass(frozen=True, slots=True)
class CreateMergeRequest:
    source_branch: str
    target_branch: str
    title: str
    description: str | None
    labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GitLabObject:
    """A typed envelope for write responses not requiring a dedicated entity."""

    data: dict[str, Any] = field(default_factory=dict)
