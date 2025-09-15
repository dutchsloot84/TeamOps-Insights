from services.ingest.jira_ingestor.handler import normalize_issue


def build_adf(text):
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def test_normalize_issue_shapes_payload():
    description = build_adf("Example description")
    deployment_notes = build_adf("Deployed to prod")
    comment_body = build_adf("Looks good")

    issue = {
        "id": "2001",
        "key": "MOB-1234",
        "fields": {
            "project": {"key": "MOB", "name": "Mobile"},
            "issuetype": {"name": "Bug"},
            "status": {"name": "In Progress"},
            "summary": "Production incident",
            "description": description,
            "comment": {
                "comments": [
                    {
                        "author": {"displayName": "Alice"},
                        "created": "2025-09-15T12:00:00.000+0000",
                        "body": comment_body,
                    }
                ],
                "total": 1,
            },
            "issuelinks": [
                {
                    "type": {
                        "name": "Relates",
                        "outward": "relates to",
                        "inward": "is related to",
                    },
                    "outwardIssue": {"key": "SRNGR-42"},
                }
            ],
            "labels": ["ccc", "postmortem"],
            "components": [{"name": "PolicyCenter"}],
            "fixVersions": [{"name": "9/19 Release"}],
            "reporter": {"displayName": "Reporter One"},
            "assignee": None,
            "created": "2025-09-10T08:00:00.000+0000",
            "updated": "2025-09-15T12:00:00.000+0000",
            "customfield_deploy": deployment_notes,
        },
    }

    field_map = {"acceptance_criteria": None, "deployment_notes": "customfield_deploy"}
    fetched_at = "2025-09-15T13:00:00Z"

    normalized = normalize_issue(
        issue,
        field_map,
        "https://example.atlassian.net",
        fetched_at,
        comments=issue["fields"]["comment"]["comments"],
    )

    assert normalized["source"] == "jira"
    assert normalized["key"] == "MOB-1234"
    assert normalized["project"] == "MOB"
    assert normalized["issue_type"] == "Bug"
    assert normalized["status"] == "In Progress"
    assert normalized["summary"] == "Production incident"
    assert normalized["description"]["adf"] == description
    assert normalized["description"]["markdown"] == "Example description"
    assert normalized["acceptance_criteria"]["adf"] is None
    assert normalized["acceptance_criteria"]["markdown"] == ""
    assert normalized["deployment_notes"]["adf"] == deployment_notes
    assert normalized["deployment_notes"]["markdown"] == "Deployed to prod"
    assert normalized["comments"] == [
        {
            "author": "Alice",
            "created": "2025-09-15T12:00:00.000+0000",
            "adf": comment_body,
            "markdown": "Looks good",
        }
    ]
    assert normalized["links"] == [
        {"type": "relates to", "direction": "outward", "key": "SRNGR-42"}
    ]
    assert normalized["labels"] == ["ccc", "postmortem"]
    assert normalized["components"] == ["PolicyCenter"]
    assert normalized["fix_versions"] == ["9/19 Release"]
    assert normalized["reporter"] == "Reporter One"
    assert normalized["assignee"] is None
    assert normalized["created"] == "2025-09-10T08:00:00.000+0000"
    assert normalized["updated"] == "2025-09-15T12:00:00.000+0000"
    assert normalized["uri"] == "https://example.atlassian.net/browse/MOB-1234"
    assert normalized["fetched_at"] == fetched_at
