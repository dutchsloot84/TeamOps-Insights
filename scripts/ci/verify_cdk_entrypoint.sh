#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CDK_JSON="$ROOT/infra/cdk/cdk.json"
ENTRY_EXPECTED_A="python infra/cdk/run_cdk_app.py"
ENTRY_EXPECTED_B="python run_cdk_app.py"

if [[ ! -f "$CDK_JSON" ]]; then
  echo "::error::Missing infra/cdk/cdk.json"
  exit 1
fi

APP_CMD="$(jq -r '.app // empty' "$CDK_JSON")"
if [[ -z "$APP_CMD" || "$APP_CMD" == "null" ]]; then
  echo "::error::\"app\" field missing in $CDK_JSON"
  exit 1
fi

echo "cdk.json app => $APP_CMD"

DUPS=$(git ls-files | grep -E '(^|/)cdk.json$' | grep -v '^infra/cdk/cdk.json$' || true)
if [[ -n "$DUPS" ]]; then
  echo "::error::Non-canonical cdk.json files detected:"
  echo "$DUPS"
  exit 1
fi

if [[ -d "$ROOT/infra/cdk/infra" ]] || git ls-files | grep -q '^infra/cdk/infra/'; then
  echo "::error::Nested infra/cdk/infra directory detected; please flatten to infra/cdk/."
  exit 1
fi

check_entry() {
  local target="$1"
  if [[ ! -f "$ROOT/$target" ]]; then
    echo "::error::Entry script not found at $target"
    exit 1
  fi
}

if [[ "$APP_CMD" == "$ENTRY_EXPECTED_A" || "$APP_CMD" == "$ENTRY_EXPECTED_B" ]]; then
  check_entry "infra/cdk/run_cdk_app.py"
else
  ENTRY=$(awk '{for(i=1;i<=NF;i++){if($i ~ /\.py$/){print $i; exit}}}' <<<"$APP_CMD")
  if [[ -n "$ENTRY" ]]; then
    check_entry "$ENTRY"
  else
    echo "::warning::Unable to determine Python entry script from app command."
  fi
fi

echo "CDK entrypoint verification passed."
