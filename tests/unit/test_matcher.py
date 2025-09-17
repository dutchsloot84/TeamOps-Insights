from src.matcher.engine import match


def test_match_basic():
    issues = [{"key": "MOB-1"}, {"key": "MOB-2"}]
    commits = [
        {"message": "feat: MOB-1 add feature", "hash": "abc123"},
        {"message": "chore: refactor"},
    ]

    matched, missing, orphans, summary = match(issues, commits)

    assert any(item["issue_key"] == "MOB-1" for item in matched)
    assert {issue["key"] for issue in missing} == {"MOB-2"}
    assert any("refactor" in commit["message"] for commit in orphans)
    assert summary["total_issues"] == 2
