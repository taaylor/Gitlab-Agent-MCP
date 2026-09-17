from gitlab_agent_mcp.infrastructure.gitlab.mapper import (
    map_changed_file,
    map_discussion,
    map_merge_request,
)


def test_map_merge_request_with_diff_refs() -> None:
    result = map_merge_request(
        {
            "id": 10,
            "iid": 2,
            "project_id": 5,
            "title": "Test",
            "description": None,
            "state": "opened",
            "web_url": "https://gitlab.example.com/group/project/-/merge_requests/2",
            "source_branch": "feature/ABC-1",
            "target_branch": "main",
            "sha": "head",
            "draft": False,
            "author": {"username": "maxim", "name": "Maksim"},
            "labels": ["feature"],
            "diff_refs": {
                "base_sha": "base",
                "head_sha": "head",
                "start_sha": "start",
            },
        }
    )

    assert result.iid == 2
    assert result.author.username == "maxim"
    assert result.diff_refs is not None
    assert result.diff_refs.head_sha == "head"


def test_map_optional_diff_flags() -> None:
    result = map_changed_file(
        {
            "old_path": "old.py",
            "new_path": "new.py",
            "diff": "@@ -1 +1 @@\n-old\n+new",
            "new_file": False,
            "renamed_file": True,
            "deleted_file": False,
            "collapsed": True,
            "too_large": False,
        }
    )

    assert result.renamed_file is True
    assert result.collapsed is True


def test_map_discussion_position_and_resolution() -> None:
    result = map_discussion(
        {
            "id": "discussion-1",
            "individual_note": False,
            "notes": [
                {
                    "id": 7,
                    "body": "Fix this",
                    "author": {"username": "reviewer"},
                    "type": "DiffNote",
                    "system": False,
                    "resolvable": True,
                    "resolved": False,
                    "position": {
                        "base_sha": "base",
                        "head_sha": "head",
                        "start_sha": "start",
                        "old_path": "app.py",
                        "new_path": "app.py",
                        "new_line": 2,
                    },
                }
            ],
        }
    )

    assert result.notes[0].resolved is False
    assert result.notes[0].position is not None
    assert result.notes[0].position.new_line == 2
