#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LATEST_DUMP="$(find "${ROOT_DIR}/backups" -maxdepth 1 -type f -name '*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {print $2}')"
DEFAULT_DUMP="${LATEST_DUMP:-${ROOT_DIR}/backups/portalcms1_pre_versioning_20260331T174604Z.dump}"
TARGET_DB="portalcms1_clone"
INPUT="$DEFAULT_DUMP"
DRY_RUN_ARGS=()
ALLOW_REMOTE_HOST=0

load_config_value() {
    local key="$1"
    local config_file="${APP_CONFIG:-}"

    if [[ -z "$config_file" ]]; then
        if [[ -f "${ROOT_DIR}/portal.conf.dev.json" ]]; then
            config_file="${ROOT_DIR}/portal.conf.dev.json"
        elif [[ -f "${ROOT_DIR}/portal.conf.json" ]]; then
            config_file="${ROOT_DIR}/portal.conf.json"
        elif [[ -f "${ROOT_DIR}/portalcms.conf.dev.json" ]]; then
            config_file="${ROOT_DIR}/portalcms.conf.dev.json"
        elif [[ -f "${ROOT_DIR}/portalcms.conf.json" ]]; then
            config_file="${ROOT_DIR}/portalcms.conf.json"
        fi
    fi

    if [[ -n "$config_file" && -f "$config_file" ]]; then
        python3 - "$config_file" "$key" <<'PY'
import json
import sys

config_path, key = sys.argv[1], sys.argv[2]
with open(config_path, "r", encoding="utf-8") as fh:
    value = json.load(fh).get(key, "")
if isinstance(value, list):
    print(",".join(str(v) for v in value))
elif value is None:
    print("")
else:
    print(value)
PY
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN_ARGS+=(--dry-run)
            shift
            ;;
        --allow-remote-host)
            ALLOW_REMOTE_HOST=1
            shift
            ;;
        -*)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
        *)
            if [[ "$TARGET_DB" == "portalcms1_clone" ]]; then
                TARGET_DB="$1"
            elif [[ "$INPUT" == "$DEFAULT_DUMP" ]]; then
                INPUT="$1"
            else
                echo "Unexpected argument: $1" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

TARGET_HOST="${DB_HOSTNAME_WRITE:-${DB_HOSTNAME_READ:-$(load_config_value DB_HOSTNAME_WRITE)}}"
TARGET_HOST="${TARGET_HOST:-localhost}"

if [[ "$TARGET_HOST" != "localhost" && "$TARGET_HOST" != "127.0.0.1" && "$ALLOW_REMOTE_HOST" -ne 1 ]]; then
    echo "Refusing clone workflow against non-local host '${TARGET_HOST}'." >&2
    echo "This helper is intended for local disposable clone databases." >&2
    echo "If you truly want a remote clone/restore target, rerun with --allow-remote-host." >&2
    exit 1
fi

cat <<EOF
Clone plan
  source dump: ${INPUT}
  target db:   ${TARGET_DB}
  target host: ${TARGET_HOST}

This script restores the dump into a clone database and verifies it.
It refuses to target the configured live database.
EOF

"${ROOT_DIR}/database/pg_restore_cms.sh" \
    --input "${INPUT}" \
    --target-db "${TARGET_DB}" \
    --recreate-db \
    "${DRY_RUN_ARGS[@]}"
