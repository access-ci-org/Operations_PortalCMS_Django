#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_DUMP="${ROOT_DIR}/backups/portalcms1_pre_versioning_20260331T174604Z.dump"
TARGET_DB="${1:-portalcms1_clone}"
INPUT="${2:-$DEFAULT_DUMP}"
DRY_RUN_ARGS=()

if [[ "${3:-}" == "--dry-run" ]]; then
    DRY_RUN_ARGS+=(--dry-run)
fi

cat <<EOF
Clone plan
  source dump: ${INPUT}
  target db:   ${TARGET_DB}

This script restores the dump into a clone database and verifies it.
It refuses to target the configured live database.
EOF

"${ROOT_DIR}/database/pg_restore_cms.sh" \
    --input "${INPUT}" \
    --target-db "${TARGET_DB}" \
    --recreate-db \
    "${DRY_RUN_ARGS[@]}"
