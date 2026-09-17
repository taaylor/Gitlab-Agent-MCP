from unittest.mock import AsyncMock

import pytest

from gitlab_agent_mcp.application.services.merge_request_service import MergeRequestService
from gitlab_agent_mcp.infrastructure.config import Settings
from gitlab_agent_mcp.presentation.mcp.server import create_server

READ_TOOLS = {
    "get_merge_request",
    "get_merge_request_diff",
    "get_changed_files",
    "get_review_context",
    "get_project_labels",
    "get_mr_discussions",
    "get_unresolved_discussions",
    "get_discussion",
    "get_pipeline",
    "get_pipeline_jobs",
}

WRITE_TOOLS = {
    "create_merge_request",
    "create_mr_comment",
    "reply_to_discussion",
    "resolve_discussion",
    "create_diff_comment",
    "create_suggestion",
}


def settings(*, write_enabled: bool) -> Settings:
    return Settings(
        gitlab_url="https://gitlab.example.com",
        gitlab_token="test-token",
        mcp_write_enabled=write_enabled,
        _env_file=None,
    )


@pytest.mark.asyncio
async def test_read_only_server_does_not_expose_write_tools() -> None:
    configured = settings(write_enabled=False)
    service = MergeRequestService(
        AsyncMock(),
        gitlab_url=configured.gitlab_url,
        write_enabled=configured.mcp_write_enabled,
    )
    server = create_server(service, configured)

    tools = await server.list_tools()

    assert {tool.name for tool in tools} == READ_TOOLS


@pytest.mark.asyncio
async def test_write_server_describes_external_side_effects_and_mr_link() -> None:
    configured = settings(write_enabled=True)
    service = MergeRequestService(
        AsyncMock(),
        gitlab_url=configured.gitlab_url,
        write_enabled=configured.mcp_write_enabled,
    )
    server = create_server(service, configured)

    tools = await server.list_tools()
    tools_by_name = {tool.name: tool for tool in tools}

    assert set(tools_by_name) == READ_TOOLS | WRITE_TOOLS
    for name in WRITE_TOOLS:
        assert "external side effect" in (tools_by_name[name].description or "")
    assert "web_url" in (tools_by_name["create_merge_request"].description or "")
