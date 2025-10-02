#!/usr/bin/env bash

set -euo pipefail
mapfile -t CDK_JSONS < <(git ls-files | grep -E '(^|/)cdk.json$' || true)
BAD=0
for p in "${CDK_JSONS[@]}"; do
  if [ "$p" != "infra/cdk/cdk.json" ]; then
    echo "::error::Non-canonical cdk.json found at $p. Keep only infra/cdk/cdk.json."
    BAD=1
  fi
done
exit $BAD
