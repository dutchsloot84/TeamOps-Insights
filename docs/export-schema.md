# Audit Export Schema

ReleaseCopilot exporters emit a stable JSON document describing a single audit run. The
schema below is the contract consumed by the diff tooling and the Streamlit dashboard.

## Top-level shape

```jsonc
{
  "stories": [Story, ...],
  "commits": [Commit, ...],
  "summary": Summary
}
```

Unknown properties may be added over time, but the keys documented here must always be
present.

## Story objects

Each `Story` element describes a single work item.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | string | Internal identifier from the source tracker (e.g. Jira). |
| `key` | string | Human readable issue key, used as the primary identifier. |
| `summary` | string | Short description or title. |
| `status` | string | Current workflow status. |
| `assignee` | string or null | Display name of the current assignee. |
| `components` | array of strings | Optional component or label names. |
| `fixVersions` | array of strings | Versions associated with the story. |
| `commitIds` | array of strings | Commit identifiers linked to the story. |

Additional metadata (like URLs) can be stored alongside these fields without breaking the
contract.

## Commit objects

Each `Commit` element captures a single VCS commit.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | string | Commit SHA or identifier. |
| `repo` | string | Repository name. |
| `author` | string | Author display name. |
| `date` | string | ISO-8601 timestamp. |
| `message` | string | Commit message subject. |
| `linkedStoryKeys` | array of strings | Story keys associated with the commit. Empty when the commit is orphaned. |

## Summary block

The `summary` object aggregates counters and high-level timestamps for the run.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `generatedAt` | string | ISO-8601 timestamp when the run completed. |
| `storyCount` | integer | Total number of stories exported. |
| `storyWithCommitsCount` | integer | Number of stories that have at least one linked commit. |
| `storyWithoutCommitsCount` | integer | Number of stories with no linked commits. |
| `orphanCommitCount` | integer | Number of commits without a linked story. |
| `coveragePercent` | number | Percentage of stories with commits (`storyWithCommitsCount / storyCount * 100`). |

Exporters may include additional metrics, but these fields provide a consistent baseline
for diffing and reporting.
