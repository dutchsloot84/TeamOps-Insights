#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
cd "${ROOT_DIR}"

if [[ ! -f cdk.json ]]; then
  echo "::error::Missing cdk.json at repository root" >&2
  exit 1
fi

APP_COMMAND=$(python - <<'PY'
import json
import sys

with open('cdk.json', 'r', encoding='utf-8') as fh:
    data = json.load(fh)

app = data.get('app')
if not isinstance(app, str) or not app.strip():
    sys.exit(1)

print(app.strip())
PY
) || {
  echo "::error::Unable to read app command from cdk.json" >&2
  exit 1
}

APP_ENTRY=$(python - <<'PY'
import json
import pathlib
import shlex
import sys

with open('cdk.json', 'r', encoding='utf-8') as fh:
    command = json.load(fh).get('app', '')

parts = shlex.split(command)
if not parts:
    sys.exit(1)

args = parts[1:]
if not args:
    sys.exit(1)

entry = None
if args[0] == '-m':
    if len(args) < 2:
        sys.exit(1)
    module = args[1]
    entry = pathlib.Path(*module.split('.')).with_suffix('.py')
else:
    entry = pathlib.Path(args[0])

print(entry.as_posix())
PY
)

if [[ -z "${APP_ENTRY}" ]]; then
  echo "::error::Unable to resolve app entry from command '${APP_COMMAND}'" >&2
  exit 1
fi

if [[ ! -f ${APP_ENTRY} ]]; then
  echo "::error::CDK app entry '${APP_ENTRY}' not found" >&2
  exit 1
fi

if git ls-files --error-unmatch infra/cdk/infra/cdk >/dev/null 2>&1; then
  echo "::error::Nested infra/cdk/infra/cdk directory detected; flatten the CDK app layout" >&2
  exit 1
fi

echo "cdk.json located at ${ROOT_DIR}/cdk.json"
echo "app command: ${APP_COMMAND}"
echo "app entry: ${APP_ENTRY}"
echo "CDK root layout OK"
