import pytest

from gitlab_agent_mcp.domain.exceptions import InvalidUrlError
from gitlab_agent_mcp.domain.urls import (
    parse_merge_request_url,
    parse_project_url,
)


def test_parse_nested_project_url() -> None:
    ref = parse_project_url(
        "https://gitlab.example.com/platform/services/backend",
        "https://gitlab.example.com",
    )

    assert ref.project_path == "platform/services/backend"


def test_parse_merge_request_url_with_installation_prefix() -> None:
    ref = parse_merge_request_url(
        "https://example.com/gitlab/platform/backend/-/merge_requests/142",
        "https://example.com/gitlab",
    )

    assert ref.project.project_path == "platform/backend"
    assert ref.iid == 142


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/platform/backend/-/merge_requests/1",
        "https://gitlab.example.com/platform/backend/-/merge_requests/0",
        "https://gitlab.example.com/platform/backend/-/merge_requests/not-a-number",
        "https://user@gitlab.example.com/platform/backend/-/merge_requests/1",
        "https://gitlab.example.com/platform/backend/-/merge_requests/1?token=secret",
    ],
)
def test_reject_unsafe_merge_request_urls(url: str) -> None:
    with pytest.raises(InvalidUrlError):
        parse_merge_request_url(url, "https://gitlab.example.com")


def test_project_url_rejects_nested_resource() -> None:
    with pytest.raises(InvalidUrlError):
        parse_project_url(
            "https://gitlab.example.com/platform/backend/-/issues/1",
            "https://gitlab.example.com",
        )
