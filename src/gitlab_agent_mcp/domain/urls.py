"""Safe parsing of GitLab project and merge request URLs."""

import re
from urllib.parse import unquote, urlsplit

from gitlab_agent_mcp.domain.entities import MergeRequestRef, ProjectRef
from gitlab_agent_mcp.domain.exceptions import InvalidUrlError

_MR_SUFFIX = re.compile(r"^(?P<project>.+)/-/merge_requests/(?P<iid>[1-9][0-9]*)/?$")


def parse_project_url(value: str, configured_url: str) -> ProjectRef:
    """Parse a project URL and ensure credentials cannot escape the configured origin."""

    relative_path = _validated_relative_path(value, configured_url)
    if "/-/" in relative_path:
        msg = "Expected a GitLab project URL, not a nested GitLab resource URL"
        raise InvalidUrlError(msg)
    _validate_project_path(relative_path)
    return ProjectRef(base_url=configured_url, project_path=relative_path)


def parse_merge_request_url(value: str, configured_url: str) -> MergeRequestRef:
    """Parse a canonical GitLab merge request URL."""

    relative_path = _validated_relative_path(value, configured_url)
    match = _MR_SUFFIX.fullmatch(relative_path)
    if match is None:
        msg = "Expected a URL ending with /-/merge_requests/<positive IID>"
        raise InvalidUrlError(msg)
    project_path = match.group("project")
    _validate_project_path(project_path)
    return MergeRequestRef(
        project=ProjectRef(base_url=configured_url, project_path=project_path),
        iid=int(match.group("iid")),
    )


def _validated_relative_path(value: str, configured_url: str) -> str:
    candidate = urlsplit(value.strip())
    configured = urlsplit(configured_url)
    if candidate.scheme.lower() != configured.scheme.lower() or candidate.netloc.lower() != (
        configured.netloc.lower()
    ):
        msg = "URL origin must exactly match GITLAB_URL"
        raise InvalidUrlError(msg)
    if candidate.username or candidate.password or candidate.query or candidate.fragment:
        msg = "GitLab URLs must not contain user information, query parameters, or fragments"
        raise InvalidUrlError(msg)

    base_path = configured.path.rstrip("/")
    candidate_path = candidate.path.rstrip("/")
    prefix = f"{base_path}/" if base_path else "/"
    if not candidate_path.startswith(prefix):
        msg = "URL path is outside the configured GitLab installation"
        raise InvalidUrlError(msg)
    relative_path = unquote(candidate_path[len(prefix) :]).strip("/")
    if not relative_path:
        msg = "GitLab URL does not contain a project path"
        raise InvalidUrlError(msg)
    return relative_path


def _validate_project_path(project_path: str) -> None:
    segments = project_path.split("/")
    if len(segments) < 2 or any(segment in {"", ".", ".."} for segment in segments):
        msg = "GitLab project path must include a namespace and project"
        raise InvalidUrlError(msg)
    if any("\x00" in segment or "\\" in segment for segment in segments):
        msg = "GitLab project path contains invalid characters"
        raise InvalidUrlError(msg)
