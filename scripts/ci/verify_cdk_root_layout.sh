#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
cd "${ROOT_DIR}"

if [[ ! -f cdk.json ]]; then
  echo "::error::Missing cdk.json at repository root" >&2
  exit 1
fi

APP_COMMAND=$(node -e "const c=require('./cdk.json'); if(!c.app){process.exit(1)} console.log(c.app)") || {
  echo "::error::Unable to read app command from cdk.json" >&2
  exit 1
}

APP_ENTRY=$(node -e "const c=require('./cdk.json'); const parts=(c.app||'').split(' '); console.log(parts.slice(1).join(' '))")

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
