#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT/dist/lambda"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install -r "$ROOT/requirements.txt" -t "$OUT_DIR" >/dev/null

cp "$ROOT/main.py" "$OUT_DIR/"
for path in aws clients config exporters processors; do
  cp -R "$ROOT/$path" "$OUT_DIR/$path"
  find "$OUT_DIR/$path" -name "__pycache__" -type d -prune -exec rm -rf {} +
  find "$OUT_DIR/$path" -name "*.pyc" -delete

done

cat <<MSG
Packaged Lambda runtime into $OUT_DIR
MSG
