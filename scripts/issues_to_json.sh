#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-}"; shift || true
OUT_DIR="${1:-}"; shift || true

if [[ -z "${REPO}" || -z "${OUT_DIR}" || "$#" -lt 1 ]]; then
  echo "Usage: $0 <owner/repo> <out_dir> <label1> [label2] ..."
  exit 1
fi

mkdir -p "${OUT_DIR}"
COMBINED="${OUT_DIR}/issues_by_label.json"
echo "{}" | jq '.' > "${COMBINED}"

for LBL in "$@"; do
  echo "Fetching label: ${LBL}"
  DATA="$(gh issue list --repo "${REPO}" --label "${LBL}" --state open \
           --json number,title,labels,updatedAt,url,assignees)"
  NORMALIZED="$(echo "${DATA}" \
    | jq 'map({
        number,
        title,
        labels: [.labels[].name],
        assignees: [.assignees[].login],
        updatedAt,
        url
      })')"
  echo "${NORMALIZED}" > "${OUT_DIR}/issues_${LBL}.json"
  TMP="$(jq --arg lbl "${LBL}" --argjson arr "${NORMALIZED}" '. + {($lbl): $arr}' "${COMBINED}")"
  echo "${TMP}" > "${COMBINED}"
done

DATE_LOCAL="$(TZ="${TZ:-America/Phoenix}" date -Iseconds)"
jq --arg generatedAt "${DATE_LOCAL}" '. + {generatedAt: $generatedAt}' "${COMBINED}" > "${COMBINED}.tmp"
mv "${COMBINED}.tmp" "${COMBINED}"

echo "Wrote ${COMBINED} and per-label files to ${OUT_DIR}/"
