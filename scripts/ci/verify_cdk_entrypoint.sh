#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CDK_JSON="$ROOT/infra/cdk/cdk.json"
ENTRY_EXPECTED="python infra/cdk/run_cdk_app.py"

if [[ ! -f "$CDK_JSON" ]]; then
  echo "::error::Missing canonical cdk.json at infra/cdk/cdk.json"
  exit 1
fi

APP_CMD="$(jq -r '.app // empty' "$CDK_JSON")"
if [[ -z "$APP_CMD" || "$APP_CMD" == "null" ]]; then
  echo "::error::cdk.json \"app\" field is empty"
  exit 1
fi

echo "cdk.json app => $APP_CMD"

# Validate duplicates
MAPFILE_DUPES=$(git ls-files | grep -E '(^|/)cdk.json$' | grep -v '^infra/cdk/cdk.json' || true)
if [[ -n "$MAPFILE_DUPES" ]]; then
  echo "::error::Non-canonical cdk.json files detected:" >&2
  echo "$MAPFILE_DUPES" >&2
  exit 1
fi

# Ensure nested infra/cdk/infra/cdk is absent
if git ls-files | grep -q '^infra/cdk/infra/cdk/'; then
  echo "::error::Nested infra/cdk/infra/cdk directory detected"
  exit 1
fi

ENTRY_PATH="$ROOT/infra/cdk/run_cdk_app.py"
if [[ ! -f "$ENTRY_PATH" ]]; then
  echo "::error::Missing entry script at infra/cdk/run_cdk_app.py"
  exit 1
fi

if [[ "$APP_CMD" != "$ENTRY_EXPECTED" ]]; then
  echo "::warning::cdk.json app command is \"$APP_CMD\" (expected \"$ENTRY_EXPECTED\")."
  # Attempt to verify the referenced python script exists
  TARGET=$(awk '{for(i=1;i<=NF;i++){if($i ~ /\.py$/){print $i; exit}}}' <<< "$APP_CMD")
  if [[ -n "$TARGET" ]]; then
    if [[ ! -f "$ROOT/$TARGET" ]]; then
      echo "::error::App entry file not found at $TARGET"
      exit 1
    fi
  else
    echo "::warning::Unable to detect python script path from app command"
  fi
fi

echo "CDK entrypoint verification passed."
