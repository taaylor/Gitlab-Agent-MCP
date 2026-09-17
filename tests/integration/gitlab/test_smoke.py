import os

import pytest

from gitlab_agent_mcp.domain.urls import parse_project_url
from gitlab_agent_mcp.infrastructure.config import Settings
from gitlab_agent_mcp.infrastructure.gitlab.client import GitLabClient
from gitlab_agent_mcp.infrastructure.gitlab.repository import GitLabApiRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_configured_project() -> None:
    project_url = os.getenv("GITLAB_INTEGRATION_PROJECT_URL")
    if project_url is None:
        pytest.skip("GITLAB_INTEGRATION_PROJECT_URL is not configured")

    settings = Settings.model_validate({})
    client = GitLabClient(settings)
    try:
        repository = GitLabApiRepository(client)
        project_ref = parse_project_url(project_url, settings.gitlab_url)
        project = await repository.get_project(project_ref)
    finally:
        await client.close()

    assert project.path_with_namespace == project_ref.project_path
