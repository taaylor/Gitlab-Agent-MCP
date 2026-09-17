"""GitLab Agent MCP package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("gitlab-agent-mcp")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["__version__"]
