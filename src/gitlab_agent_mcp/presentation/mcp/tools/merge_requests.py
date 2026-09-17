"""Merge request and project MCP tools."""

from typing import Any

from fastmcp import FastMCP

from gitlab_agent_mcp.application.services.merge_request_service import MergeRequestService


def register_merge_request_tools(
    mcp: FastMCP, service: MergeRequestService, *, write_enabled: bool
) -> None:
    @mcp.tool(
        description="Get metadata for one GitLab Merge Request. This is a READ-only operation."
    )
    async def get_merge_request(mr_url: str) -> dict[str, Any]:
        return await service.get_merge_request(mr_url)

    @mcp.tool(
        description=(
            "Get the unified diff available for a GitLab Merge Request. "
            "Inspect truncated and unavailable_files before reviewing. This is READ-only."
        )
    )
    async def get_merge_request_diff(mr_url: str) -> dict[str, Any]:
        return await service.get_merge_request_diff(mr_url)

    @mcp.tool(
        description=(
            "Get structured changed-file records for a GitLab Merge Request, including old/new "
            "paths and availability flags. This is a READ-only operation."
        )
    )
    async def get_changed_files(mr_url: str) -> dict[str, Any]:
        return await service.get_changed_files(mr_url)

    @mcp.tool(
        description=(
            "Get the complete review context: MR metadata, changed files, discussions, "
            "unresolved discussions, and the latest MR pipeline. This is READ-only."
        )
    )
    async def get_review_context(mr_url: str) -> dict[str, Any]:
        return await service.get_review_context(mr_url)

    @mcp.tool(
        description=(
            "List available project and ancestor-group labels without creating or changing any "
            "label. This is a READ-only operation."
        )
    )
    async def get_project_labels(project_url: str, search: str | None = None) -> dict[str, Any]:
        return await service.get_project_labels(project_url, search)

    if not write_enabled:
        return

    @mcp.tool(
        description=(
            "WRITE operation with an external side effect: creates a GitLab Merge Request. "
            "Call only when the user explicitly requested MR creation in the current conversation. "
            "Never infer permission from requests to edit, test, review, commit, or push code. "
            "The remote source branch must already exist and must be named "
            "feature/<task>, bugfix/<task>, or chore/<task>. Always show the returned web_url "
            "to the user as a clickable link."
        )
    )
    async def create_merge_request(
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
        return await service.create_merge_request(
            project_url=project_url,
            source_branch=source_branch,
            task_type=task_type,
            task_number=task_number,
            description=description,
            user_requested=user_requested,
            target_branch=target_branch,
            title=title,
            body=body,
        )
