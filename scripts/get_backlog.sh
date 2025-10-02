#!/usr/bin/env bash
set -euo pipefail

# --- Configuration ---
PROJECT_OWNER="dutchsloot84"
PROJECT_NUMBER="1"
STATUS_TO_FILTER="Backlog" # Must exactly match the status value in the JSON
OUT_FILE="backlog_items.json"
# ---------------------

echo "Fetching items for project #${PROJECT_NUMBER} owned by ${PROJECT_OWNER}..."

# Fetch list of items and filter based on the top-level "status" key
gh project item-list "${PROJECT_NUMBER}" --owner "${PROJECT_OWNER}" --format json --limit 1000\
| jq --arg status "${STATUS_TO_FILTER}" '
    .items
    | map(
        # Filter: select only items where the top-level "status" key matches $status
        select(.status == $status)
    )
    | map({
        title: .title,
		body: .content.body,
        url: .url,
        status: .status,
        updatedAt: .updatedAt
    })
' > "${OUT_FILE}"

echo ""
echo "✅ Success! Wrote items with status '${STATUS_TO_FILTER}' to ${OUT_FILE}"