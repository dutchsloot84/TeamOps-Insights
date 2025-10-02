#!/usr/bin/env bash

set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

if [[ -z "${GITHUB_ENV:-}" ]]; then
  GITHUB_ENV="$(mktemp)"
fi

CDK_JSON="infra/cdk/cdk.json"
ENTRY_EXPECTED="infra/cdk/run_cdk_app.py"

if [[ ! -f "$CDK_JSON" ]]; then
  echo "::error::Missing canonical cdk.json at $CDK_JSON" >&2
  exit 1
fi

mapfile -t CDK_JSONS < <(git ls-files | grep -E '(^|/)cdk.json$' || true)
for path in "${CDK_JSONS[@]}"; do
  if [[ "$path" != "$CDK_JSON" ]]; then
    echo "::error::Non-canonical cdk.json detected at: $path" >&2
    exit 1
  fi
done

if [[ -d "infra/cdk/infra/cdk" ]]; then
  echo "::error::Nested infra/cdk/infra/cdk directory detected; please keep CDK app files flat under infra/cdk/" >&2
  exit 1
fi

APP_CMD=$(python3 - "$CDK_JSON" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open() as fh:
    data = json.load(fh)
app = data.get("app")
if not isinstance(app, str) or not app.strip():
    print("::error::cdk.json missing non-empty \"app\" string", file=sys.stderr)
    sys.exit(1)
print(app.strip())
PY
)

APP_CMD=$(echo "$APP_CMD" | tr -d '\r')
APP_NORMALIZED="$APP_CMD"
if [[ "$APP_NORMALIZED" =~ ^python([[:space:]]|$) ]]; then
  APP_NORMALIZED="python3${APP_NORMALIZED#python}"
fi

ENTRY_PATH=$(python3 - <<'PY' "$APP_CMD"
import shlex
import sys

parts = shlex.split(sys.argv[1])
for token in parts[1:]:
    if token.endswith('.py'):
        print(token)
        break
else:
    print('')
PY
)

ENTRY_PATH=$(echo "$ENTRY_PATH" | tr -d '\r')
if [[ -z "$ENTRY_PATH" ]]; then
  echo "::error::Unable to detect Python entry file from app command: $APP_CMD" >&2
  exit 1
fi

if [[ "$ENTRY_PATH" != "$ENTRY_EXPECTED" ]]; then
  echo "::error::App entry path must be $ENTRY_EXPECTED but was $ENTRY_PATH" >&2
  exit 1
fi

if [[ ! -f "$ENTRY_PATH" ]]; then
  echo "::error::App entry file not found: $ENTRY_PATH" >&2
  exit 1
fi

CDK_CONTEXT_ARGS_SHELL=$(python3 - "$CDK_JSON" <<'PY'
import json
import shlex
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open() as fh:
    data = json.load(fh)
context = data.get("context", {})
if not isinstance(context, dict):
    context = {}
parts = []
for key, value in context.items():
    parts.append('-c')
    parts.append(f"{key}={value}")
print(" ".join(shlex.quote(part) for part in parts))
PY
)

{
  echo "APP=$APP_NORMALIZED"
  echo "CDK_APP_CANONICAL=$APP_CMD"
  echo "CDK_ENTRY_FILE=$ENTRY_PATH"
  echo "CDK_CONTEXT_ARGS_SHELL=$CDK_CONTEXT_ARGS_SHELL"
} >> "$GITHUB_ENV"

echo "cdk.json app => $APP_CMD"
echo "Normalized CLI app => $APP_NORMALIZED"
echo "Entry file verified at $ENTRY_PATH"
if [[ -n "$CDK_CONTEXT_ARGS_SHELL" ]]; then
  echo "Context arguments => $CDK_CONTEXT_ARGS_SHELL"
else
  echo "Context arguments => <none>"
fi

echo "CDK entrypoint verification passed."
