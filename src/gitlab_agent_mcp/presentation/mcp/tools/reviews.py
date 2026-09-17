"""Inline review MCP tools."""

from typing import Any

from fastmcp import FastMCP

from gitlab_agent_mcp.application.services.merge_request_service import MergeRequestService


def register_review_tools(
    mcp: FastMCP, service: MergeRequestService, *, write_enabled: bool
) -> None:
    if not write_enabled:
        return

    @mcp.tool(
        description=(
            "WRITE operation with an external side effect: publishes an inline GitLab diff "
            "discussion. Call only after explicit user approval. Use new_line for added lines, "
            "old_line for removed lines, and both for an unchanged context line."
        )
    )
    async def create_diff_comment(
        mr_url: str,
        file_path: str,
        body: str,
        new_line: int | None = None,
        old_line: int | None = None,
    ) -> dict[str, Any]:
        return await service.create_diff_comment(
            mr_url=mr_url,
            file_path=file_path,
            body=body,
            new_line=new_line,
            old_line=old_line,
        )

    @mcp.tool(
        description=(
            "WRITE operation with an external side effect: publishes a real GitLab suggestion "
            "on an added or current new-side line. Call only after explicit user approval."
        )
    )
    async def create_suggestion(
        mr_url: str,
        file_path: str,
        line: int,
        replacement: str,
        explanation: str,
    ) -> dict[str, Any]:
        return await service.create_suggestion(
            mr_url=mr_url,
            file_path=file_path,
            line=line,
            replacement=replacement,
            explanation=explanation,
        )
