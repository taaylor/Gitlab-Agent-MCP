"""FastMCP server composition."""

from fastmcp import FastMCP

from gitlab_agent_mcp.application.services.merge_request_service import MergeRequestService
from gitlab_agent_mcp.infrastructure.config import Settings
from gitlab_agent_mcp.presentation.mcp.tools.discussions import register_discussion_tools
from gitlab_agent_mcp.presentation.mcp.tools.merge_requests import register_merge_request_tools
from gitlab_agent_mcp.presentation.mcp.tools.pipelines import register_pipeline_tools
from gitlab_agent_mcp.presentation.mcp.tools.reviews import register_review_tools


def create_server(service: MergeRequestService, settings: Settings) -> FastMCP:
    """Create a server whose registered tools match the configured safety mode."""

    mcp = FastMCP(
        name="GitLab Agent MCP",
        instructions=(
            "Use this server only for GitLab merge request workflows. Read operations are safe. "
            "Tools described as WRITE have external side effects and require explicit user "
            "approval. Never use create_merge_request unless the user directly requested it."
        ),
    )
    register_merge_request_tools(mcp, service, write_enabled=settings.mcp_write_enabled)
    register_discussion_tools(mcp, service, write_enabled=settings.mcp_write_enabled)
    register_review_tools(mcp, service, write_enabled=settings.mcp_write_enabled)
    register_pipeline_tools(mcp, service)
    return mcp
