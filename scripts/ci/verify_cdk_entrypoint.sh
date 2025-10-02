#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CDK_JSON="$ROOT/infra/cdk/cdk.json"
ENTRY_EXPECTED_A="python infra/cdk/run_cdk_app.py"
ENTRY_EXPECTED_A_PY3="python3 infra/cdk/run_cdk_app.py"
ENTRY_EXPECTED_B="python run_cdk_app.py"
ENTRY_EXPECTED_B_PY3="python3 run_cdk_app.py"

if [[ ! -f "$CDK_JSON" ]]; then
  echo "::error::Missing infra/cdk/cdk.json"
  exit 1
fi

APP_CMD="$(jq -r '.app // empty' "$CDK_JSON")"
if [[ -z "$APP_CMD" || "$APP_CMD" == "null" ]]; then
  echo "::error::The \"app\" field in infra/cdk/cdk.json is empty"
  exit 1
fi

echo "infra/cdk/cdk.json app => $APP_CMD"

mapfile -t CDK_JSONS < <(git ls-files | grep -E '(^|/)cdk.json$' || true)
for p in "${CDK_JSONS[@]}"; do
  if [[ "$p" != "infra/cdk/cdk.json" ]]; then
    echo "::error::Non-canonical cdk.json files detected: $p"
    exit 1
  fi
done

if git ls-files | grep -q '^infra/cdk/infra/cdk/'; then
  echo "::error::Nested infra/cdk/infra/cdk directory detected; please flatten the CDK layout."
  exit 1
fi

ENTRY_SCRIPT=""
case "$APP_CMD" in
  "$ENTRY_EXPECTED_A"|"$ENTRY_EXPECTED_A_PY3")
    ENTRY_SCRIPT="infra/cdk/run_cdk_app.py"
    ;;
  "$ENTRY_EXPECTED_B"|"$ENTRY_EXPECTED_B_PY3")
    ENTRY_SCRIPT="infra/cdk/run_cdk_app.py"
    ;;
  python*|python3*)
    ENTRY_SCRIPT="$(awk '{for (i=1;i<=NF;i++){if ($i ~ /\.py$/){print $i; exit}}}' <<<"$APP_CMD")"
    ;;
  *)
    echo "::warning::App command does not start with python: $APP_CMD"
    ;;
esac

if [[ -n "$ENTRY_SCRIPT" ]]; then
  if [[ ! -f "$ROOT/$ENTRY_SCRIPT" ]]; then
    echo "::error::App entry file not found: $ENTRY_SCRIPT"
    exit 1
  fi
else
  echo "::warning::Unable to determine entry script from app command."
fi

echo "CDK entrypoint verification passed."
