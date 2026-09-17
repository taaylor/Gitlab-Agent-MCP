"""GitLab REST implementation of the application repository contract."""

from urllib.parse import quote

from gitlab_agent_mcp.domain.entities import (
    ChangedFile,
    CreateMergeRequest,
    DiffPosition,
    DiffRefs,
    Discussion,
    GitLabObject,
    MergeRequest,
    MergeRequestRef,
    Pipeline,
    PipelineJob,
    Project,
    ProjectLabel,
    ProjectRef,
)
from gitlab_agent_mcp.domain.exceptions import GitLabValidationError, ResourceNotFoundError
from gitlab_agent_mcp.infrastructure.gitlab.client import GitLabClient
from gitlab_agent_mcp.infrastructure.gitlab.mapper import (
    map_changed_file,
    map_diff_refs,
    map_discussion,
    map_merge_request,
    map_pipeline,
    map_pipeline_job,
    map_project,
    map_project_label,
)


class GitLabApiRepository:
    """A deliberately narrow GitLab adapter with no arbitrary request escape hatch."""

    def __init__(self, client: GitLabClient) -> None:
        self._client = client

    async def get_merge_request(self, ref: MergeRequestRef) -> MergeRequest:
        data = await self._client.request_object("GET", _mr_path(ref))
        return map_merge_request(data)

    async def get_merge_request_diffs(self, ref: MergeRequestRef) -> tuple[ChangedFile, ...]:
        data = await self._client.request_list(f"{_mr_path(ref)}/diffs", params={"unidiff": True})
        return tuple(map_changed_file(item) for item in data)

    async def get_latest_diff_refs(self, ref: MergeRequestRef) -> DiffRefs:
        versions = await self._client.request_list(f"{_mr_path(ref)}/versions")
        if not versions:
            msg = "The merge request has no diff versions"
            raise GitLabValidationError(msg)
        return map_diff_refs(versions[0])

    async def get_discussions(self, ref: MergeRequestRef) -> tuple[Discussion, ...]:
        data = await self._client.request_list(f"{_mr_path(ref)}/discussions")
        return tuple(map_discussion(item) for item in data)

    async def get_discussion(self, ref: MergeRequestRef, discussion_id: str) -> Discussion:
        encoded_id = quote(discussion_id, safe="")
        data = await self._client.request_object("GET", f"{_mr_path(ref)}/discussions/{encoded_id}")
        return map_discussion(data)

    async def get_merge_request_pipelines(self, ref: MergeRequestRef) -> tuple[Pipeline, ...]:
        data = await self._client.request_list(f"{_mr_path(ref)}/pipelines")
        return tuple(map_pipeline(item) for item in data)

    async def get_pipeline(self, project: ProjectRef, pipeline_id: int) -> Pipeline:
        data = await self._client.request_object(
            "GET", f"{_project_path(project)}/pipelines/{pipeline_id}"
        )
        return map_pipeline(data)

    async def get_pipeline_jobs(
        self, project: ProjectRef, pipeline_id: int
    ) -> tuple[PipelineJob, ...]:
        data = await self._client.request_list(
            f"{_project_path(project)}/pipelines/{pipeline_id}/jobs",
            params={"include_retried": True},
        )
        return tuple(map_pipeline_job(item) for item in data)

    async def create_merge_request_comment(self, ref: MergeRequestRef, body: str) -> GitLabObject:
        data = await self._client.request_object(
            "POST", f"{_mr_path(ref)}/notes", json={"body": body}
        )
        return GitLabObject(data=data)

    async def create_diff_comment(
        self, ref: MergeRequestRef, body: str, position: DiffPosition
    ) -> Discussion:
        position_payload: dict[str, object] = {
            "position_type": position.position_type,
            "base_sha": position.base_sha,
            "head_sha": position.head_sha,
            "start_sha": position.start_sha,
            "old_path": position.old_path,
            "new_path": position.new_path,
        }
        if position.old_line is not None:
            position_payload["old_line"] = position.old_line
        if position.new_line is not None:
            position_payload["new_line"] = position.new_line
        data = await self._client.request_object(
            "POST",
            f"{_mr_path(ref)}/discussions",
            json={"body": body, "position": position_payload},
        )
        return map_discussion(data)

    async def reply_to_discussion(
        self, ref: MergeRequestRef, discussion_id: str, body: str
    ) -> Discussion:
        encoded_id = quote(discussion_id, safe="")
        await self._client.request_object(
            "POST",
            f"{_mr_path(ref)}/discussions/{encoded_id}/notes",
            json={"body": body},
        )
        return await self.get_discussion(ref, discussion_id)

    async def resolve_discussion(self, ref: MergeRequestRef, discussion_id: str) -> Discussion:
        encoded_id = quote(discussion_id, safe="")
        data = await self._client.request_object(
            "PUT",
            f"{_mr_path(ref)}/discussions/{encoded_id}",
            json={"resolved": True},
        )
        return map_discussion(data)

    async def get_project(self, ref: ProjectRef) -> Project:
        data = await self._client.request_object("GET", _project_path(ref))
        return map_project(data)

    async def get_project_labels(self, ref: ProjectRef) -> tuple[ProjectLabel, ...]:
        data = await self._client.request_list(
            f"{_project_path(ref)}/labels",
            params={"include_ancestor_groups": True, "with_counts": False},
        )
        return tuple(map_project_label(item) for item in data)

    async def branch_exists(self, ref: ProjectRef, branch_name: str) -> bool:
        encoded_branch = quote(branch_name, safe="")
        try:
            await self._client.request_object(
                "GET", f"{_project_path(ref)}/repository/branches/{encoded_branch}"
            )
        except ResourceNotFoundError:
            return False
        return True

    async def find_open_merge_request(
        self, ref: ProjectRef, source_branch: str, target_branch: str
    ) -> MergeRequest | None:
        data = await self._client.request_list(
            f"{_project_path(ref)}/merge_requests",
            params={
                "state": "opened",
                "source_branch": source_branch,
                "target_branch": target_branch,
            },
        )
        return map_merge_request(data[0]) if data else None

    async def create_merge_request(
        self, ref: ProjectRef, command: CreateMergeRequest
    ) -> MergeRequest:
        payload: dict[str, object] = {
            "source_branch": command.source_branch,
            "target_branch": command.target_branch,
            "title": command.title,
        }
        if command.description is not None:
            payload["description"] = command.description
        if command.labels:
            payload["labels"] = ",".join(command.labels)
        data = await self._client.request_object(
            "POST", f"{_project_path(ref)}/merge_requests", json=payload
        )
        return map_merge_request(data)


def _project_path(ref: ProjectRef) -> str:
    return f"/projects/{quote(ref.project_path, safe='')}"


def _mr_path(ref: MergeRequestRef) -> str:
    return f"{_project_path(ref.project)}/merge_requests/{ref.iid}"
