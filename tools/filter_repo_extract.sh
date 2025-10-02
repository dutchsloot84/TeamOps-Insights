#!/usr/bin/env bash
set -euo pipefail

# Usage: ./tools/filter_repo_extract.sh <SOURCE_REPO_PATH> <NEW_REPO_GITHUB_SSH>
# Example:
#   ./tools/filter_repo_extract.sh /c/projects/ReleaseCopilot-AI git@github.com:your-org/git-historian.git

SRC_REPO="${1:-}"
DEST_REMOTE="${2:-}"

if [[ -z "${SRC_REPO}" || -z "${DEST_REMOTE}" ]]; then
  echo "Usage: $0 <SOURCE_REPO_PATH> <NEW_REPO_GITHUB_SSH>"
  exit 1
fi

if ! command -v git-filter-repo >/dev/null 2>&1; then
  echo "Installing git-filter-repo (pip user install)..."
  python -m pip install --user git-filter-repo
  export PATH="$HOME/.local/bin:$PATH"
fi

WORKDIR="$(cd "$(dirname "$0")/.." && pwd)"
EXTRACT_DIR="${WORKDIR}/../git-historian-src"

echo "Cloning source repo (no-local copy) to ${EXTRACT_DIR} ..."
rm -rf "${EXTRACT_DIR}"
git clone --no-local "${SRC_REPO}" "${EXTRACT_DIR}"

cd "${EXTRACT_DIR}"

echo "Running git filter-repo for Historian paths ..."
git filter-repo \
  --path scripts/generate_history.py \
  --path docs/git-historian.md \
  --path config/defaults.yml \
  --path .github/workflows/weekly-history.yml \
  --path docs/history \
  --path docs/context \
  --path templates \
  --force

echo "Repointing remote to ${DEST_REMOTE} ..."
git remote remove origin || true
git remote add origin "${DEST_REMOTE}"

echo "Pushing extracted history to main ..."
git push -u origin HEAD:main

echo "Done. New repo now contains only Historian-related history and files."
