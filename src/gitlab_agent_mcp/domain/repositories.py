"""Repository interfaces used by the application layer."""

from typing import Protocol

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


class GitLabRepository(Protocol):
    async def get_merge_request(self, ref: MergeRequestRef) -> MergeRequest: ...

    async def get_merge_request_diffs(self, ref: MergeRequestRef) -> tuple[ChangedFile, ...]: ...

    async def get_latest_diff_refs(self, ref: MergeRequestRef) -> DiffRefs: ...

    async def get_discussions(self, ref: MergeRequestRef) -> tuple[Discussion, ...]: ...

    async def get_discussion(self, ref: MergeRequestRef, discussion_id: str) -> Discussion: ...

    async def get_merge_request_pipelines(self, ref: MergeRequestRef) -> tuple[Pipeline, ...]: ...

    async def get_pipeline(self, project: ProjectRef, pipeline_id: int) -> Pipeline: ...

    async def get_pipeline_jobs(
        self, project: ProjectRef, pipeline_id: int
    ) -> tuple[PipelineJob, ...]: ...

    async def create_merge_request_comment(
        self, ref: MergeRequestRef, body: str
    ) -> GitLabObject: ...

    async def create_diff_comment(
        self, ref: MergeRequestRef, body: str, position: DiffPosition
    ) -> Discussion: ...

    async def reply_to_discussion(
        self, ref: MergeRequestRef, discussion_id: str, body: str
    ) -> Discussion: ...

    async def resolve_discussion(self, ref: MergeRequestRef, discussion_id: str) -> Discussion: ...

    async def get_project(self, ref: ProjectRef) -> Project: ...

    async def get_project_labels(self, ref: ProjectRef) -> tuple[ProjectLabel, ...]: ...

    async def branch_exists(self, ref: ProjectRef, branch_name: str) -> bool: ...

    async def find_open_merge_request(
        self, ref: ProjectRef, source_branch: str, target_branch: str
    ) -> MergeRequest | None: ...

    async def create_merge_request(
        self, ref: ProjectRef, command: CreateMergeRequest
    ) -> MergeRequest: ...
