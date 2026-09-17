"""Small, defensive asynchronous client for the GitLab REST API."""

import asyncio
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import aiohttp

from gitlab_agent_mcp.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    GitLabConflictError,
    GitLabUnavailableError,
    GitLabValidationError,
    RateLimitError,
    ResourceNotFoundError,
)
from gitlab_agent_mcp.infrastructure.config import Settings

_RETRYABLE_STATUS_CODES = {
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.BAD_GATEWAY,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
}


@dataclass(frozen=True, slots=True)
class _Response:
    status: int
    headers: Mapping[str, str]
    payload: object
    reason: str


class GitLabClient:
    """aiohttp transport exposing JSON objects and complete paginated lists."""

    def __init__(
        self,
        settings: Settings,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._settings = settings
        self._api_url = f"{settings.gitlab_url}/api/v4"
        self._session = session
        self._owns_session = session is None

    async def close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()

    async def request_object(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        json: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        response = await self._request(method, path, params=params, json=json)
        if not isinstance(response.payload, dict):
            msg = "GitLab returned an unexpected non-object response"
            raise GitLabValidationError(msg)
        return response.payload

    async def request_list(
        self,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        page = 1
        base_params = dict(params or {})
        per_page = 100

        while page <= self._settings.gitlab_max_pages:
            page_params = {**base_params, "page": page, "per_page": per_page}
            response = await self._request("GET", path, params=page_params)
            if not isinstance(response.payload, list):
                msg = "GitLab returned an unexpected non-list response"
                raise GitLabValidationError(msg)
            for item in response.payload:
                if not isinstance(item, dict):
                    msg = "GitLab returned a list containing a non-object item"
                    raise GitLabValidationError(msg)
                result.append(item)

            next_page = response.headers.get("X-Next-Page")
            if next_page:
                try:
                    page = int(next_page)
                except ValueError as exc:
                    msg = "GitLab returned an invalid X-Next-Page header"
                    raise GitLabValidationError(msg) from exc
                continue
            if len(response.payload) < per_page:
                return result
            page += 1

        msg = (
            "GitLab pagination exceeded the configured limit of "
            f"{self._settings.gitlab_max_pages} pages"
        )
        raise GitLabValidationError(msg)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        json: Mapping[str, object] | None = None,
    ) -> _Response:
        normalized_method = method.upper()
        attempts = self._settings.gitlab_read_retries + 1 if normalized_method == "GET" else 1

        for attempt in range(attempts):
            try:
                response = await self._perform_request(
                    normalized_method,
                    path,
                    params=params,
                    json=json,
                )
            except (aiohttp.ClientError, TimeoutError) as exc:
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.25 * (2**attempt))
                    continue
                msg = "GitLab request failed because the server could not be reached"
                raise GitLabUnavailableError(msg) from exc

            if response.status in _RETRYABLE_STATUS_CODES and attempt + 1 < attempts:
                await asyncio.sleep(_retry_delay(response, attempt))
                continue
            self._raise_for_status(response)
            return response

        msg = "GitLab request failed after all retry attempts"
        raise GitLabUnavailableError(msg)

    async def _perform_request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, object] | None,
        json: Mapping[str, object] | None,
    ) -> _Response:
        session = await self._get_session()
        async with session.request(
            method,
            f"{self._api_url}{path}",
            params=_stringify_params(params),
            json=json,
            allow_redirects=False,
        ) as raw_response:
            try:
                payload: object = await raw_response.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError):
                payload = None
            response = _Response(
                status=raw_response.status,
                headers=raw_response.headers,
                payload=payload,
                reason=raw_response.reason or "unknown error",
            )
        if payload is None and HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES:
            msg = "GitLab returned invalid JSON"
            raise GitLabValidationError(msg)
        return response

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is not None:
            return self._session
        ssl_context = ssl.create_default_context(
            cafile=(
                str(self._settings.gitlab_ca_bundle)
                if self._settings.gitlab_ca_bundle is not None
                else None
            )
        )
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self._session = aiohttp.ClientSession(
            headers={
                "PRIVATE-TOKEN": self._settings.gitlab_token.get_secret_value(),
                "Accept": "application/json",
                "User-Agent": "gitlab-agent-mcp/0.1.0",
            },
            timeout=aiohttp.ClientTimeout(total=self._settings.gitlab_timeout_seconds),
            connector=connector,
            raise_for_status=False,
        )
        return self._session

    @staticmethod
    def _raise_for_status(response: _Response) -> None:
        status = response.status
        if HTTPStatus.OK <= status < HTTPStatus.MULTIPLE_CHOICES:
            return
        detail = _error_detail(response)
        match status:
            case HTTPStatus.UNAUTHORIZED:
                raise AuthenticationError(f"GitLab authentication failed: {detail}")
            case HTTPStatus.FORBIDDEN:
                raise AuthorizationError(f"GitLab authorization failed: {detail}")
            case HTTPStatus.NOT_FOUND:
                raise ResourceNotFoundError(f"GitLab resource was not found: {detail}")
            case HTTPStatus.CONFLICT:
                raise GitLabConflictError(f"GitLab reported a conflict: {detail}")
            case HTTPStatus.TOO_MANY_REQUESTS:
                raise RateLimitError(
                    f"GitLab rate limit exceeded: {detail}",
                    retry_after=_retry_after(response),
                )
            case (
                HTTPStatus.BAD_REQUEST
                | HTTPStatus.METHOD_NOT_ALLOWED
                | HTTPStatus.PRECONDITION_FAILED
                | HTTPStatus.UNPROCESSABLE_ENTITY
            ):
                raise GitLabValidationError(f"GitLab rejected the request ({status}): {detail}")
            case _ if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
                raise GitLabUnavailableError(f"GitLab returned status {status}: {detail}")
            case _:
                raise GitLabValidationError(f"Unexpected GitLab status {status}: {detail}")


def _retry_after(response: _Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, min(float(value), 30.0))
    except ValueError:
        return None


def _retry_delay(response: _Response, attempt: int) -> float:
    return _retry_after(response) or 0.25 * (2**attempt)


def _error_detail(response: _Response) -> str:
    if isinstance(response.payload, dict):
        message = response.payload.get("message") or response.payload.get("error")
        if isinstance(message, str):
            return message[:500]
        if isinstance(message, dict):
            return str(message)[:500]
    return response.reason


def _stringify_params(params: Mapping[str, object] | None) -> dict[str, str] | None:
    if params is None:
        return None
    return {
        key: str(value).lower() if isinstance(value, bool) else str(value)
        for key, value in params.items()
    }
