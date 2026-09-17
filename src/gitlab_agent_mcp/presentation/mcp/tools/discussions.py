"""Discussion MCP tools."""

from typing import Any

from fastmcp import FastMCP

from gitlab_agent_mcp.application.services.merge_request_service import MergeRequestService


def register_discussion_tools(
    mcp: FastMCP, service: MergeRequestService, *, write_enabled: bool
) -> None:
    @mcp.tool(description="List all discussions for a GitLab MR. This is a READ-only operation.")
    async def get_mr_discussions(mr_url: str) -> dict[str, Any]:
        return await service.get_mr_discussions(mr_url)

    @mcp.tool(
        description=(
            "List discussions containing at least one resolvable, unresolved note. "
            "This is a READ-only operation."
        )
    )
    async def get_unresolved_discussions(mr_url: str) -> dict[str, Any]:
        return await service.get_unresolved_discussions(mr_url)

    @mcp.tool(description="Get one GitLab MR discussion. This is a READ-only operation.")
    async def get_discussion(mr_url: str, discussion_id: str) -> dict[str, Any]:
        return await service.get_discussion(mr_url, discussion_id)

    if not write_enabled:
        return

    @mcp.tool(
        description=(
            "WRITE operation with an external side effect: posts a general comment on a GitLab "
            "Merge Request. Call only after explicit user approval to publish it."
        )
    )
    async def create_mr_comment(mr_url: str, body: str) -> dict[str, Any]:
        return await service.create_mr_comment(mr_url, body)

    @mcp.tool(
        description=(
            "WRITE operation with an external side effect: replies to an existing GitLab MR "
            "discussion. Call only after explicit user approval to publish the reply."
        )
    )
    async def reply_to_discussion(mr_url: str, discussion_id: str, body: str) -> dict[str, Any]:
        return await service.reply_to_discussion(mr_url, discussion_id, body)

    @mcp.tool(
        description=(
            "WRITE operation with an external side effect: resolves a GitLab MR discussion. "
            "Call only after the user explicitly asked to resolve it."
        )
    )
    async def resolve_discussion(mr_url: str, discussion_id: str) -> dict[str, Any]:
        return await service.resolve_discussion(mr_url, discussion_id)
