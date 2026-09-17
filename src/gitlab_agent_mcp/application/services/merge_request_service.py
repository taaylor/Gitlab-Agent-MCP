"""Application use cases for merge request review and creation."""

import asyncio
import re
from collections.abc import Iterable
from typing import Any

from gitlab_agent_mcp.application.dto import to_jsonable
from gitlab_agent_mcp.domain.entities import (
    ChangedFile,
    CreateMergeRequest,
    DiffPosition,
    Discussion,
    MergeRequestRef,
    Pipeline,
    ProjectLabel,
)
from gitlab_agent_mcp.domain.enums import TaskType
from gitlab_agent_mcp.domain.exceptions import (
    ResourceNotFoundError,
    StaleDiffPositionError,
    ValidationError,
    WriteDisabledError,
)
from gitlab_agent_mcp.domain.repositories import GitLabRepository
from gitlab_agent_mcp.domain.urls import (
    parse_merge_request_url,
    parse_project_url,
)

_TASK_NUMBER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HUNK_HEADER = re.compile(r"^@@ -(?P<old>[0-9]+)(?:,[0-9]+)? \+(?P<new>[0-9]+)(?:,[0-9]+)? @@")


class MergeRequestService:
    """Coordinates safe, typed GitLab operations for MCP tools."""

    def __init__(
        self,
        repository: GitLabRepository,
        *,
        gitlab_url: str,
        write_enabled: bool,
    ) -> None:
        self._repository = repository
        self._gitlab_url = gitlab_url
        self._write_enabled = write_enabled

    async def get_merge_request(self, mr_url: str) -> dict[str, Any]:
        ref = self._mr_ref(mr_url)
        merge_request = await self._repository.get_merge_request(ref)
        return {"merge_request": to_jsonable(merge_request)}

    async def get_changed_files(self, mr_url: str) -> dict[str, Any]:
        ref = self._mr_ref(mr_url)
        files = await self._repository.get_merge_request_diffs(ref)
        return _files_result(files)

    async def get_merge_request_diff(self, mr_url: str) -> dict[str, Any]:
        ref = self._mr_ref(mr_url)
        files = await self._repository.get_merge_request_diffs(ref)
        chunks = []
        for file in files:
            chunks.append(f"--- a/{file.old_path}\n+++ b/{file.new_path}\n{file.diff}")
        unavailable = [file.new_path for file in files if file.collapsed or file.too_large]
        return {
            "diff": "\n".join(chunks),
            "file_count": len(files),
            "truncated": bool(unavailable),
            "unavailable_files": unavailable,
        }

    async def get_mr_discussions(self, mr_url: str) -> dict[str, Any]:
        ref = self._mr_ref(mr_url)
        discussions = await self._repository.get_discussions(ref)
        return {"discussions": to_jsonable(discussions), "count": len(discussions)}

    async def get_unresolved_discussions(self, mr_url: str) -> dict[str, Any]:
        ref = self._mr_ref(mr_url)
        discussions = await self._repository.get_discussions(ref)
        unresolved = tuple(item for item in discussions if _is_unresolved(item))
        return {"discussions": to_jsonable(unresolved), "count": len(unresolved)}

    async def get_discussion(self, mr_url: str, discussion_id: str) -> dict[str, Any]:
        ref = self._mr_ref(mr_url)
        _require_text(discussion_id, "discussion_id", maximum=255)
        discussion = await self._repository.get_discussion(ref, discussion_id)
        return {"discussion": to_jsonable(discussion)}

    async def get_pipeline(self, mr_url: str, pipeline_id: int | None = None) -> dict[str, Any]:
        ref = self._mr_ref(mr_url)
        pipeline = await self._select_pipeline(ref, pipeline_id)
        return {"pipeline": to_jsonable(pipeline) if pipeline is not None else None}

    async def get_pipeline_jobs(
        self, mr_url: str, pipeline_id: int | None = None
    ) -> dict[str, Any]:
        ref = self._mr_ref(mr_url)
        pipeline = await self._select_pipeline(ref, pipeline_id)
        if pipeline is None:
            return {"pipeline": None, "jobs": [], "count": 0}
        jobs = await self._repository.get_pipeline_jobs(ref.project, pipeline.id)
        return {
            "pipeline": to_jsonable(pipeline),
            "jobs": to_jsonable(jobs),
            "count": len(jobs),
        }

    async def get_review_context(self, mr_url: str) -> dict[str, Any]:
        ref = self._mr_ref(mr_url)
        merge_request, diff_refs, files, discussions, pipelines = await asyncio.gather(
            self._repository.get_merge_request(ref),
            self._repository.get_latest_diff_refs(ref),
            self._repository.get_merge_request_diffs(ref),
            self._repository.get_discussions(ref),
            self._repository.get_merge_request_pipelines(ref),
        )
        pipeline = (
            await self._repository.get_pipeline(ref.project, pipelines[0].id) if pipelines else None
        )
        unresolved = tuple(item for item in discussions if _is_unresolved(item))
        files_result = _files_result(files)
        return {
            "merge_request": to_jsonable(merge_request),
            "diff_refs": to_jsonable(diff_refs),
            "changed_files": files_result["files"],
            "changed_file_count": files_result["count"],
            "diff_truncated": files_result["truncated"],
            "discussions": to_jsonable(discussions),
            "unresolved_discussions": to_jsonable(unresolved),
            "pipeline": to_jsonable(pipeline) if pipeline is not None else None,
        }

    async def get_project_labels(
        self, project_url: str, search: str | None = None
    ) -> dict[str, Any]:
        ref = parse_project_url(project_url, self._gitlab_url)
        project, labels = await asyncio.gather(
            self._repository.get_project(ref),
            self._repository.get_project_labels(ref),
        )
        if search:
            needle = search.casefold()
            labels = tuple(label for label in labels if needle in label.name.casefold())
        return {
            "project": to_jsonable(project),
            "labels": to_jsonable(labels),
            "count": len(labels),
        }

    async def create_mr_comment(self, mr_url: str, body: str) -> dict[str, Any]:
        self._require_write()
        _require_text(body, "body", maximum=1_000_000)
        ref = self._mr_ref(mr_url)
        note = await self._repository.create_merge_request_comment(ref, body)
        return {"note": to_jsonable(note.data), "external_side_effect": True}

    async def create_diff_comment(
        self,
        mr_url: str,
        file_path: str,
        body: str,
        new_line: int | None = None,
        old_line: int | None = None,
    ) -> dict[str, Any]:
        self._require_write()
        _require_text(body, "body", maximum=1_000_000)
        ref = self._mr_ref(mr_url)
        position = await self._build_position(ref, file_path, new_line, old_line)
        discussion = await self._repository.create_diff_comment(ref, body, position)
        return {"discussion": to_jsonable(discussion), "external_side_effect": True}

    async def create_suggestion(
        self,
        mr_url: str,
        file_path: str,
        line: int,
        replacement: str,
        explanation: str,
    ) -> dict[str, Any]:
        self._require_write()
        _require_text(explanation, "explanation", maximum=100_000)
        if not replacement:
            msg = "replacement must not be empty"
            raise ValidationError(msg)
        if "```" in replacement:
            msg = "replacement must not contain a Markdown code fence"
            raise ValidationError(msg)
        ref = self._mr_ref(mr_url)
        position = await self._build_position(ref, file_path, line, None)
        body = f"{explanation.strip()}\n\n```suggestion\n{replacement}\n```"
        discussion = await self._repository.create_diff_comment(ref, body, position)
        return {"discussion": to_jsonable(discussion), "external_side_effect": True}

    async def reply_to_discussion(
        self, mr_url: str, discussion_id: str, body: str
    ) -> dict[str, Any]:
        self._require_write()
        _require_text(discussion_id, "discussion_id", maximum=255)
        _require_text(body, "body", maximum=1_000_000)
        ref = self._mr_ref(mr_url)
        discussion = await self._repository.reply_to_discussion(ref, discussion_id, body)
        return {"discussion": to_jsonable(discussion), "external_side_effect": True}

    async def resolve_discussion(self, mr_url: str, discussion_id: str) -> dict[str, Any]:
        self._require_write()
        _require_text(discussion_id, "discussion_id", maximum=255)
        ref = self._mr_ref(mr_url)
        current = await self._repository.get_discussion(ref, discussion_id)
        if not any(note.resolvable for note in current.notes):
            msg = "The discussion is not resolvable"
            raise ValidationError(msg)
        if not _is_unresolved(current):
            return {
                "discussion": to_jsonable(current),
                "external_side_effect": False,
                "message": "Discussion is already resolved",
            }
        discussion = await self._repository.resolve_discussion(ref, discussion_id)
        return {"discussion": to_jsonable(discussion), "external_side_effect": True}

    async def create_merge_request(
        self,
        project_url: str,
        source_branch: str,
        task_type: str,
        task_number: str,
        description: str,
        user_requested: bool,
        target_branch: str | None = None,
        title: str | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        self._require_write()
        if not user_requested:
            msg = "Merge Request creation requires an explicit request from the user"
            raise ValidationError(msg)
        try:
            normalized_type = TaskType(task_type)
        except ValueError as exc:
            msg = "task_type must be one of: feature, bugfix, chore"
            raise ValidationError(msg) from exc
        if _TASK_NUMBER.fullmatch(task_number) is None:
            msg = "task_number may contain only letters, digits, dots, underscores, and hyphens"
            raise ValidationError(msg)
        _require_text(description, "description", maximum=500)
        expected_branch = f"{normalized_type.value}/{task_number}"
        if source_branch != expected_branch:
            msg = f"source_branch must be exactly {expected_branch!r}"
            raise ValidationError(msg)

        ref = parse_project_url(project_url, self._gitlab_url)
        project = await self._repository.get_project(ref)
        selected_target = target_branch or project.default_branch
        if source_branch == selected_target:
            msg = "source_branch and target_branch must be different"
            raise ValidationError(msg)

        source_exists, target_exists = await asyncio.gather(
            self._repository.branch_exists(ref, source_branch),
            self._repository.branch_exists(ref, selected_target),
        )
        if not source_exists:
            raise ResourceNotFoundError(
                f"Remote source branch {source_branch!r} does not exist; "
                "push it before creating the MR"
            )
        if not target_exists:
            raise ResourceNotFoundError(f"Target branch {selected_target!r} does not exist")

        existing = await self._repository.find_open_merge_request(
            ref, source_branch, selected_target
        )
        if existing is not None:
            return {
                "created": False,
                "merge_request": to_jsonable(existing),
                "message": f"Merge Request уже существует: {existing.web_url}",
                "web_url": existing.web_url,
                "external_side_effect": False,
            }

        labels = await self._repository.get_project_labels(ref)
        selected_label, label_warning = _select_label(labels, normalized_type.value)
        mr_title = (
            title.strip()
            if title is not None
            else (f"{normalized_type.value}: {description.strip()} ({task_number})")
        )
        _require_text(mr_title, "title", maximum=255)
        command = CreateMergeRequest(
            source_branch=source_branch,
            target_branch=selected_target,
            title=mr_title,
            description=body.strip() if body else None,
            labels=(selected_label,) if selected_label is not None else (),
        )
        merge_request = await self._repository.create_merge_request(ref, command)
        result: dict[str, Any] = {
            "created": True,
            "merge_request": to_jsonable(merge_request),
            "web_url": merge_request.web_url,
            "message": f"Merge Request создан: {merge_request.web_url}",
            "label_resolution": {
                "requested": normalized_type.value,
                "assigned": selected_label is not None,
                "assigned_name": selected_label,
                "created": False,
            },
            "external_side_effect": True,
        }
        if label_warning is not None:
            result["warning"] = label_warning
        return result

    async def _select_pipeline(
        self, ref: MergeRequestRef, pipeline_id: int | None
    ) -> Pipeline | None:
        pipelines = await self._repository.get_merge_request_pipelines(ref)
        if not pipelines:
            if pipeline_id is not None:
                raise ResourceNotFoundError("The merge request has no pipelines")
            return None
        selected: Pipeline | None
        if pipeline_id is None:
            selected = pipelines[0]
        else:
            selected = next((item for item in pipelines if item.id == pipeline_id), None)
            if selected is None:
                msg = f"Pipeline {pipeline_id} does not belong to this merge request"
                raise ResourceNotFoundError(msg)
        return await self._repository.get_pipeline(ref.project, selected.id)

    async def _build_position(
        self,
        ref: MergeRequestRef,
        file_path: str,
        new_line: int | None,
        old_line: int | None,
    ) -> DiffPosition:
        _require_text(file_path, "file_path", maximum=4096)
        if new_line is None and old_line is None:
            msg = "At least one of new_line or old_line is required"
            raise ValidationError(msg)
        if new_line is not None and new_line <= 0:
            raise ValidationError("new_line must be positive")
        if old_line is not None and old_line <= 0:
            raise ValidationError("old_line must be positive")
        refs, files = await asyncio.gather(
            self._repository.get_latest_diff_refs(ref),
            self._repository.get_merge_request_diffs(ref),
        )
        candidates = [item for item in files if file_path in {item.old_path, item.new_path}]
        if len(candidates) != 1:
            msg = f"File {file_path!r} was not found uniquely in the latest merge request diff"
            raise StaleDiffPositionError(msg)
        file = candidates[0]
        if file.collapsed or file.too_large or not file.diff:
            msg = f"Diff for {file_path!r} is unavailable or too large for an inline comment"
            raise StaleDiffPositionError(msg)
        valid_positions = _diff_positions(file.diff)
        if (old_line, new_line) not in valid_positions:
            msg = (
                f"Position old_line={old_line}, new_line={new_line} is not present "
                "in the latest diff"
            )
            raise StaleDiffPositionError(msg)
        return DiffPosition(
            base_sha=refs.base_sha,
            head_sha=refs.head_sha,
            start_sha=refs.start_sha,
            old_path=file.old_path,
            new_path=file.new_path,
            old_line=old_line,
            new_line=new_line,
        )

    def _mr_ref(self, mr_url: str) -> MergeRequestRef:
        return parse_merge_request_url(mr_url, self._gitlab_url)

    def _require_write(self) -> None:
        if not self._write_enabled:
            raise WriteDisabledError("WRITE operations are disabled by MCP_WRITE_ENABLED=false")


def _files_result(files: tuple[ChangedFile, ...]) -> dict[str, Any]:
    unavailable = [file.new_path for file in files if file.collapsed or file.too_large]
    return {
        "files": to_jsonable(files),
        "count": len(files),
        "truncated": bool(unavailable),
        "unavailable_files": unavailable,
    }


def _is_unresolved(discussion: Discussion) -> bool:
    return any(note.resolvable and not note.resolved for note in discussion.notes)


def _require_text(value: str, name: str, *, maximum: int) -> None:
    if not value.strip():
        raise ValidationError(f"{name} must not be empty")
    if len(value) > maximum:
        raise ValidationError(f"{name} must not exceed {maximum} characters")


def _select_label(labels: Iterable[ProjectLabel], requested: str) -> tuple[str | None, str | None]:
    available = tuple(label for label in labels if not label.archived)
    exact = [label.name for label in available if label.name == requested]
    if exact:
        return exact[0], None
    folded = [label.name for label in available if label.name.casefold() == requested.casefold()]
    if len(folded) == 1:
        return folded[0], None
    if len(folded) > 1:
        return None, f"Label {requested!r} is ambiguous and was not assigned"
    return None, f"Label {requested!r} is not available and was not created"


def _diff_positions(diff: str) -> set[tuple[int | None, int | None]]:
    positions: set[tuple[int | None, int | None]] = set()
    old_line: int | None = None
    new_line: int | None = None
    for line in diff.splitlines():
        match = _HUNK_HEADER.match(line)
        if match is not None:
            old_line = int(match.group("old"))
            new_line = int(match.group("new"))
            continue
        if old_line is None or new_line is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            positions.add((None, new_line))
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            positions.add((old_line, None))
            old_line += 1
        elif line.startswith(" "):
            positions.add((old_line, new_line))
            old_line += 1
            new_line += 1
    return positions
