"""Errors exposed by the domain and application layers."""


class GitLabAgentError(Exception):
    """Base class for safe, user-facing errors."""


class ConfigurationError(GitLabAgentError):
    """The server configuration is invalid."""


class InvalidUrlError(GitLabAgentError):
    """A project or merge request URL is invalid or unsafe."""


class ValidationError(GitLabAgentError):
    """Tool input violates a business rule."""


class AuthenticationError(GitLabAgentError):
    """GitLab rejected the configured credentials."""


class AuthorizationError(GitLabAgentError):
    """The authenticated GitLab user lacks permission."""


class ResourceNotFoundError(GitLabAgentError):
    """The requested GitLab resource does not exist or is not visible."""


class RateLimitError(GitLabAgentError):
    """GitLab rate-limited the request."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class GitLabValidationError(GitLabAgentError):
    """GitLab rejected a request as invalid."""


class GitLabConflictError(GitLabAgentError):
    """GitLab reported a state conflict."""


class GitLabUnavailableError(GitLabAgentError):
    """GitLab could not be reached or returned a transient server error."""


class StaleDiffPositionError(GitLabAgentError):
    """A requested inline comment position is not in the latest diff."""


class WriteDisabledError(GitLabAgentError):
    """A write was attempted while write mode is disabled."""
