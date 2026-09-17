"""Console entry point for the GitLab Agent MCP stdio server."""

import argparse
import asyncio

from pydantic import ValidationError

from gitlab_agent_mcp import __version__
from gitlab_agent_mcp.application.services.merge_request_service import MergeRequestService
from gitlab_agent_mcp.infrastructure.config import Settings
from gitlab_agent_mcp.infrastructure.gitlab.client import GitLabClient
from gitlab_agent_mcp.infrastructure.gitlab.repository import GitLabApiRepository
from gitlab_agent_mcp.presentation.mcp.server import create_server


def main() -> None:
    """Load configuration and run the local stdio MCP server."""

    parser = argparse.ArgumentParser(
        prog="gitlab-agent-mcp",
        description="Local stdio MCP server for safe GitLab Merge Request workflows.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate environment configuration without starting the MCP server",
    )
    arguments = parser.parse_args()

    try:
        settings = Settings.model_validate({})
    except ValidationError as exc:
        raise SystemExit(f"Invalid GitLab Agent MCP configuration: {exc}") from exc

    if arguments.check_config:
        mode = "READ/WRITE" if settings.mcp_write_enabled else "READ-only"
        print(f"Configuration is valid for {settings.gitlab_url} ({mode})")
        return

    client = GitLabClient(settings)
    repository = GitLabApiRepository(client)
    service = MergeRequestService(
        repository,
        gitlab_url=settings.gitlab_url,
        write_enabled=settings.mcp_write_enabled,
    )
    server = create_server(service, settings)
    try:
        server.run(transport="stdio", show_banner=False)
    finally:
        asyncio.run(client.close())


if __name__ == "__main__":
    main()
