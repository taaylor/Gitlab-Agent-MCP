"""Pipeline MCP tools."""

from typing import Any

from fastmcp import FastMCP

from gitlab_agent_mcp.application.services.merge_request_service import MergeRequestService


def register_pipeline_tools(mcp: FastMCP, service: MergeRequestService) -> None:
    @mcp.tool(
        description=(
            "Get the latest pipeline associated with an MR, or a specific pipeline after "
            "verifying that it belongs to the MR. This is a READ-only operation."
        )
    )
    async def get_pipeline(mr_url: str, pipeline_id: int | None = None) -> dict[str, Any]:
        return await service.get_pipeline(mr_url, pipeline_id)

    @mcp.tool(
        description=(
            "Get jobs for the latest MR pipeline, or for a verified pipeline ID. "
            "This is a READ-only operation."
        )
    )
    async def get_pipeline_jobs(mr_url: str, pipeline_id: int | None = None) -> dict[str, Any]:
        return await service.get_pipeline_jobs(mr_url, pipeline_id)
