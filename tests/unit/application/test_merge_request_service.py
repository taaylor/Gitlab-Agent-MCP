from unittest.mock import AsyncMock

import pytest

from gitlab_agent_mcp.application.services.merge_request_service import MergeRequestService
from gitlab_agent_mcp.domain.entities import (
    ChangedFile,
    DiffRefs,
    Discussion,
    DiscussionNote,
    MergeRequest,
    Project,
    ProjectLabel,
    User,
)
from gitlab_agent_mcp.domain.exceptions import (
    ResourceNotFoundError,
    StaleDiffPositionError,
    ValidationError,
    WriteDisabledError,
)


def merge_request() -> MergeRequest:
    return MergeRequest(
        id=10,
        iid=2,
        project_id=5,
        title="feature: Add export (ABC-1)",
        description=None,
        state="opened",
        web_url="https://gitlab.example.com/group/project/-/merge_requests/2",
        source_branch="feature/ABC-1",
        target_branch="main",
        sha="head",
        draft=False,
        author=User(username="maxim"),
        labels=("feature",),
        diff_refs=DiffRefs(base_sha="base", head_sha="head", start_sha="start"),
    )


def service(repository: AsyncMock, *, write_enabled: bool = False) -> MergeRequestService:
    return MergeRequestService(
        repository,
        gitlab_url="https://gitlab.example.com",
        write_enabled=write_enabled,
    )


def changed_file() -> ChangedFile:
    return ChangedFile(
        old_path="app.py",
        new_path="app.py",
        diff="@@ -1,2 +1,3 @@\n old\n-removed\n+added\n+second",
        new_file=False,
        renamed_file=False,
        deleted_file=False,
    )


@pytest.mark.asyncio
async def test_write_is_blocked_by_default() -> None:
    repository = AsyncMock()
    application = service(repository)

    with pytest.raises(WriteDisabledError):
        await application.create_mr_comment(
            "https://gitlab.example.com/group/project/-/merge_requests/2", "hello"
        )

    repository.create_merge_request_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_unresolved_discussions_are_filtered() -> None:
    repository = AsyncMock()
    repository.get_discussions.return_value = (
        Discussion(
            id="open",
            individual_note=False,
            notes=(
                DiscussionNote(
                    id=1,
                    body="fix",
                    author=User(username="reviewer"),
                    type="DiffNote",
                    system=False,
                    resolvable=True,
                    resolved=False,
                ),
            ),
        ),
        Discussion(id="system", individual_note=True, notes=()),
    )
    application = service(repository)

    result = await application.get_unresolved_discussions(
        "https://gitlab.example.com/group/project/-/merge_requests/2"
    )

    assert result["count"] == 1
    assert result["discussions"][0]["id"] == "open"


@pytest.mark.asyncio
async def test_diff_comment_validates_latest_hunk_position() -> None:
    repository = AsyncMock()
    repository.get_latest_diff_refs.return_value = DiffRefs(
        base_sha="base", head_sha="head", start_sha="start"
    )
    repository.get_merge_request_diffs.return_value = (changed_file(),)
    repository.create_diff_comment.return_value = Discussion(
        id="created", individual_note=False, notes=()
    )
    application = service(repository, write_enabled=True)

    await application.create_diff_comment(
        mr_url="https://gitlab.example.com/group/project/-/merge_requests/2",
        file_path="app.py",
        body="Please change this",
        new_line=2,
    )

    position = repository.create_diff_comment.await_args.args[2]
    assert position.new_line == 2
    assert position.old_line is None


@pytest.mark.asyncio
async def test_diff_comment_rejects_stale_position() -> None:
    repository = AsyncMock()
    repository.get_latest_diff_refs.return_value = DiffRefs(
        base_sha="base", head_sha="head", start_sha="start"
    )
    repository.get_merge_request_diffs.return_value = (changed_file(),)
    application = service(repository, write_enabled=True)

    with pytest.raises(StaleDiffPositionError):
        await application.create_diff_comment(
            mr_url="https://gitlab.example.com/group/project/-/merge_requests/2",
            file_path="app.py",
            body="Please change this",
            new_line=999,
        )


@pytest.mark.asyncio
async def test_create_merge_request_returns_link_and_existing_label() -> None:
    repository = AsyncMock()
    repository.get_project.return_value = Project(
        id=5,
        path_with_namespace="group/project",
        web_url="https://gitlab.example.com/group/project",
        default_branch="main",
    )
    repository.branch_exists.side_effect = [True, True]
    repository.find_open_merge_request.return_value = None
    repository.get_project_labels.return_value = (
        ProjectLabel(
            name="feature",
            color="#000000",
            description=None,
            is_project_label=True,
        ),
    )
    repository.create_merge_request.return_value = merge_request()
    application = service(repository, write_enabled=True)

    result = await application.create_merge_request(
        project_url="https://gitlab.example.com/group/project",
        source_branch="feature/ABC-1",
        task_type="feature",
        task_number="ABC-1",
        description="Add export",
        user_requested=True,
    )

    assert result["created"] is True
    assert result["web_url"].endswith("/merge_requests/2")
    assert result["web_url"] in result["message"]
    command = repository.create_merge_request.await_args.args[1]
    assert command.labels == ("feature",)
    assert command.title == "feature: Add export (ABC-1)"


@pytest.mark.asyncio
async def test_create_merge_request_requires_explicit_request() -> None:
    repository = AsyncMock()
    application = service(repository, write_enabled=True)

    with pytest.raises(ValidationError):
        await application.create_merge_request(
            project_url="https://gitlab.example.com/group/project",
            source_branch="feature/ABC-1",
            task_type="feature",
            task_number="ABC-1",
            description="Add export",
            user_requested=False,
        )

    repository.get_project.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_merge_request_requires_remote_source_branch() -> None:
    repository = AsyncMock()
    repository.get_project.return_value = Project(
        id=5,
        path_with_namespace="group/project",
        web_url="https://gitlab.example.com/group/project",
        default_branch="main",
    )
    repository.branch_exists.side_effect = [False, True]
    application = service(repository, write_enabled=True)

    with pytest.raises(ResourceNotFoundError):
        await application.create_merge_request(
            project_url="https://gitlab.example.com/group/project",
            source_branch="bugfix/42",
            task_type="bugfix",
            task_number="42",
            description="Fix race",
            user_requested=True,
        )


@pytest.mark.asyncio
async def test_existing_merge_request_is_not_duplicated() -> None:
    repository = AsyncMock()
    repository.get_project.return_value = Project(
        id=5,
        path_with_namespace="group/project",
        web_url="https://gitlab.example.com/group/project",
        default_branch="main",
    )
    repository.branch_exists.side_effect = [True, True]
    repository.find_open_merge_request.return_value = merge_request()
    application = service(repository, write_enabled=True)

    result = await application.create_merge_request(
        project_url="https://gitlab.example.com/group/project",
        source_branch="feature/ABC-1",
        task_type="feature",
        task_number="ABC-1",
        description="Add export",
        user_requested=True,
    )

    assert result["created"] is False
    repository.create_merge_request.assert_not_awaited()
