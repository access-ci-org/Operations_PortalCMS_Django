#!/bin/bash
# Restore portal media from a backup archive.
#
# Extracts filer_public/ and filer_public_thumbnails/ from the archive into
# the target media directory. Handles both .tar and .tar.gz archives.
#
# Usage:
#   bash database/media_restore.sh <path_to_archive> [options]
#
# Examples:
#   # Local dev (default target: <repo_root>/operations_portalcms_django/media/)
#   bash database/media_restore.sh database/mediarestore/media.portal1.1784507401.tar
#
#   # Production: Ansible-managed server
#   bash database/media_restore.sh media.portal1.tar --target-dir /soft/django-cms-01/www/media
#
#   # Production: pre-Ansible server (manual deploy)
#   bash database/media_restore.sh media.portal1.tar \
#     --target-dir /soft/django-cms-01/tags/Operations_PortalCMS_Django/operations_portalcms_django/media
#
#   # Dry run — preview without extracting
#   bash database/media_restore.sh media.portal1.tar --dry-run

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_TARGET_DIR="${REPO_ROOT}/operations_portalcms_django/media"

FILE=""
TARGET_DIR=""
DRY_RUN=0

usage() {
    cat <<EOF
Usage: bash database/media_restore.sh <path_to_archive> [options]

Extract a portal media backup archive into the media directory.

Arguments:
  <path_to_archive>      Path to the .tar or .tar.gz archive to restore

Options:
  --target-dir PATH      Target media directory
                         Default: <repo_root>/operations_portalcms_django/media
                         Ansible-managed production: /soft/django-cms-01/www/media
                         Pre-Ansible production: /soft/django-cms-01/tags/{app_tag}/operations_portalcms_django/media
  --dry-run              Preview archive contents without extracting
  --help                 Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target-dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
        *)
            if [[ -z "$FILE" ]]; then
                FILE="$1"
            else
                echo "Unexpected argument: $1" >&2
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$FILE" ]]; then
    echo "Error: archive path is required" >&2
    usage
    exit 1
fi

if [[ ! -f "$FILE" ]]; then
    echo "Error: archive not found: $FILE" >&2
    exit 1
fi

TARGET_DIR="${TARGET_DIR:-$DEFAULT_TARGET_DIR}"

# Detect archive format
if [[ "$FILE" == *.tar.gz || "$FILE" == *.tgz ]]; then
    TAR_FLAGS="-xzf"
elif [[ "$FILE" == *.tar ]]; then
    TAR_FLAGS="-xf"
else
    echo "Error: unrecognised archive format (expected .tar or .tar.gz): $FILE" >&2
    exit 1
fi

echo "Media restore"
echo "  archive:    $FILE"
echo "  target dir: $TARGET_DIR"
echo ""

# Warn if target is non-empty
if [[ -d "$TARGET_DIR" ]]; then
    existing_count=$(find "$TARGET_DIR" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')
    if [[ "$existing_count" -gt 0 ]]; then
        echo "Warning: target directory is non-empty (${existing_count} items). Existing files will be overwritten or merged."
        echo "  Existing top-level contents:"
        ls -1 "$TARGET_DIR" | sed 's/^/    /'
        echo ""
    fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Dry run — no changes will be made."
    echo ""
    echo "Would execute:"
    echo "  mkdir -p $TARGET_DIR"
    echo "  tar $TAR_FLAGS $FILE -C $TARGET_DIR"
    echo ""
    echo "Archive top-level contents:"
    tar -tf "$FILE" | grep -E '^\./[^/]+/?$' | sed 's/^/  /'
    exit 0
fi

mkdir -p "$TARGET_DIR"

echo "Extracting..."
tar $TAR_FLAGS "$FILE" -C "$TARGET_DIR"

echo ""
echo "Verifying..."
exit_code=0

for dir in filer_public filer_public_thumbnails; do
    if [[ -d "${TARGET_DIR}/${dir}" ]]; then
        count=$(find "${TARGET_DIR}/${dir}" -type f | wc -l | tr -d ' ')
        echo "  ✓ ${dir}/ (${count} files)"
    else
        echo "  ✗ ${dir}/ not found" >&2
        exit_code=1
    fi
done

echo ""
if [[ "$exit_code" -eq 0 ]]; then
    echo "Restore complete: $TARGET_DIR"
else
    echo "Restore completed with warnings — check output above." >&2
fi

exit "$exit_code"
