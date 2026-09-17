from http import HTTPStatus

import pytest

from gitlab_agent_mcp.domain.exceptions import (
    AuthenticationError,
    GitLabUnavailableError,
    GitLabValidationError,
    RateLimitError,
)
from gitlab_agent_mcp.infrastructure.gitlab.client import GitLabClient, _Response


def response(status: HTTPStatus) -> _Response:
    return _Response(
        status=status,
        headers={},
        payload={"message": "failure"},
        reason=status.phrase,
    )


def test_success_status_is_accepted() -> None:
    GitLabClient._raise_for_status(response(HTTPStatus.OK))


def test_unauthorized_uses_typed_error() -> None:
    with pytest.raises(AuthenticationError):
        GitLabClient._raise_for_status(response(HTTPStatus.UNAUTHORIZED))


@pytest.mark.parametrize(
    "status",
    [
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.METHOD_NOT_ALLOWED,
        HTTPStatus.PRECONDITION_FAILED,
        HTTPStatus.UNPROCESSABLE_ENTITY,
    ],
)
def test_validation_status_group(status: HTTPStatus) -> None:
    with pytest.raises(GitLabValidationError):
        GitLabClient._raise_for_status(response(status))


def test_rate_limit_preserves_retry_after() -> None:
    limited = _Response(
        status=HTTPStatus.TOO_MANY_REQUESTS,
        headers={"Retry-After": "3"},
        payload={"message": "slow down"},
        reason=HTTPStatus.TOO_MANY_REQUESTS.phrase,
    )

    with pytest.raises(RateLimitError) as caught:
        GitLabClient._raise_for_status(limited)

    assert caught.value.retry_after == 3


def test_server_error_uses_unavailable_error() -> None:
    with pytest.raises(GitLabUnavailableError):
        GitLabClient._raise_for_status(response(HTTPStatus.SERVICE_UNAVAILABLE))
