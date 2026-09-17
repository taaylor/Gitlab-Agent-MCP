"""Mapping between GitLab JSON documents and domain entities."""

from collections.abc import Mapping
from typing import Any

from gitlab_agent_mcp.domain.entities import (
    ChangedFile,
    DiffPosition,
    DiffRefs,
    Discussion,
    DiscussionNote,
    MergeRequest,
    Pipeline,
    PipelineJob,
    Project,
    ProjectLabel,
    Suggestion,
    User,
)
from gitlab_agent_mcp.domain.exceptions import GitLabValidationError


def map_user(data: Mapping[str, Any] | None) -> User:
    source = data or {}
    return User(
        username=_string(source, "username", default="unknown"),
        name=_optional_string(source, "name"),
        web_url=_optional_string(source, "web_url"),
    )


def map_diff_refs(data: Mapping[str, Any]) -> DiffRefs:
    return DiffRefs(
        base_sha=_string(data, "base_sha", fallback="base_commit_sha"),
        head_sha=_string(data, "head_sha", fallback="head_commit_sha"),
        start_sha=_string(data, "start_sha", fallback="start_commit_sha"),
    )


def map_merge_request(data: Mapping[str, Any]) -> MergeRequest:
    raw_diff_refs = data.get("diff_refs")
    return MergeRequest(
        id=_integer(data, "id"),
        iid=_integer(data, "iid"),
        project_id=_integer(data, "project_id", fallback="target_project_id"),
        title=_string(data, "title"),
        description=_optional_string(data, "description"),
        state=_string(data, "state"),
        web_url=_string(data, "web_url"),
        source_branch=_string(data, "source_branch"),
        target_branch=_string(data, "target_branch"),
        sha=_optional_string(data, "sha"),
        draft=bool(data.get("draft", data.get("work_in_progress", False))),
        author=map_user(_mapping_or_none(data.get("author"))),
        labels=tuple(str(label) for label in data.get("labels", []) if isinstance(label, str)),
        detailed_merge_status=_optional_string(data, "detailed_merge_status"),
        diff_refs=(map_diff_refs(raw_diff_refs) if isinstance(raw_diff_refs, Mapping) else None),
    )


def map_changed_file(data: Mapping[str, Any]) -> ChangedFile:
    return ChangedFile(
        old_path=_string(data, "old_path"),
        new_path=_string(data, "new_path"),
        diff=_string(data, "diff", default=""),
        new_file=bool(data.get("new_file", False)),
        renamed_file=bool(data.get("renamed_file", False)),
        deleted_file=bool(data.get("deleted_file", False)),
        generated_file=bool(data.get("generated_file", False)),
        collapsed=bool(data.get("collapsed", False)),
        too_large=bool(data.get("too_large", False)),
        a_mode=_optional_string(data, "a_mode"),
        b_mode=_optional_string(data, "b_mode"),
    )


def map_position(data: Mapping[str, Any] | None) -> DiffPosition | None:
    if not data:
        return None
    base_sha = data.get("base_sha")
    head_sha = data.get("head_sha")
    start_sha = data.get("start_sha")
    old_path = data.get("old_path")
    new_path = data.get("new_path")
    if (
        not isinstance(base_sha, str)
        or not isinstance(head_sha, str)
        or not isinstance(start_sha, str)
        or not isinstance(old_path, str)
        or not isinstance(new_path, str)
    ):
        return None
    return DiffPosition(
        base_sha=base_sha,
        head_sha=head_sha,
        start_sha=start_sha,
        old_path=old_path,
        new_path=new_path,
        old_line=_optional_integer(data, "old_line"),
        new_line=_optional_integer(data, "new_line"),
        position_type=_string(data, "position_type", default="text"),
    )


def map_suggestion(data: Mapping[str, Any]) -> Suggestion:
    return Suggestion(
        id=_optional_integer(data, "id"),
        from_line=_optional_integer(data, "from_line"),
        to_line=_optional_integer(data, "to_line"),
        appliable=_optional_boolean(data, "appliable"),
        applied=_optional_boolean(data, "applied"),
    )


def map_note(data: Mapping[str, Any]) -> DiscussionNote:
    raw_suggestions = data.get("suggestions", [])
    suggestions = tuple(
        map_suggestion(item) for item in raw_suggestions if isinstance(item, Mapping)
    )
    return DiscussionNote(
        id=_integer(data, "id"),
        body=_string(data, "body", default=""),
        author=map_user(_mapping_or_none(data.get("author"))),
        type=_optional_string(data, "type"),
        system=bool(data.get("system", False)),
        resolvable=bool(data.get("resolvable", False)),
        resolved=bool(data.get("resolved", False)),
        created_at=_optional_string(data, "created_at"),
        updated_at=_optional_string(data, "updated_at"),
        position=map_position(_mapping_or_none(data.get("position"))),
        suggestions=suggestions,
    )


def map_discussion(data: Mapping[str, Any]) -> Discussion:
    raw_notes = data.get("notes", [])
    return Discussion(
        id=_string(data, "id"),
        individual_note=bool(data.get("individual_note", False)),
        notes=tuple(map_note(item) for item in raw_notes if isinstance(item, Mapping)),
    )


def map_pipeline(data: Mapping[str, Any]) -> Pipeline:
    return Pipeline(
        id=_integer(data, "id"),
        status=_string(data, "status"),
        sha=_string(data, "sha"),
        ref=_optional_string(data, "ref"),
        web_url=_optional_string(data, "web_url"),
        created_at=_optional_string(data, "created_at"),
        updated_at=_optional_string(data, "updated_at"),
        started_at=_optional_string(data, "started_at"),
        finished_at=_optional_string(data, "finished_at"),
    )


def map_pipeline_job(data: Mapping[str, Any]) -> PipelineJob:
    return PipelineJob(
        id=_integer(data, "id"),
        name=_string(data, "name"),
        stage=_string(data, "stage", default=""),
        status=_string(data, "status"),
        web_url=_optional_string(data, "web_url"),
        allow_failure=bool(data.get("allow_failure", False)),
        created_at=_optional_string(data, "created_at"),
        started_at=_optional_string(data, "started_at"),
        finished_at=_optional_string(data, "finished_at"),
    )


def map_project(data: Mapping[str, Any]) -> Project:
    return Project(
        id=_integer(data, "id"),
        path_with_namespace=_string(data, "path_with_namespace"),
        web_url=_string(data, "web_url"),
        default_branch=_string(data, "default_branch"),
    )


def map_project_label(data: Mapping[str, Any]) -> ProjectLabel:
    return ProjectLabel(
        name=_string(data, "name"),
        color=_optional_string(data, "color"),
        description=_optional_string(data, "description"),
        is_project_label=_optional_boolean(data, "is_project_label"),
        archived=bool(data.get("archived", False)),
    )


def _mapping_or_none(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _string(
    data: Mapping[str, Any],
    key: str,
    *,
    default: str | None = None,
    fallback: str | None = None,
) -> str:
    value = data.get(key)
    if value is None and fallback is not None:
        value = data.get(fallback)
    if isinstance(value, str):
        return value
    if default is not None:
        return default
    msg = f"GitLab response field {key!r} must be a string"
    raise GitLabValidationError(msg)


def _optional_string(data: Mapping[str, Any], key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) else None


def _integer(data: Mapping[str, Any], key: str, *, fallback: str | None = None) -> int:
    value = data.get(key)
    if value is None and fallback is not None:
        value = data.get(fallback)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    msg = f"GitLab response field {key!r} must be an integer"
    raise GitLabValidationError(msg)


def _optional_integer(data: Mapping[str, Any], key: str) -> int | None:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_boolean(data: Mapping[str, Any], key: str) -> bool | None:
    value = data.get(key)
    return value if isinstance(value, bool) else None
