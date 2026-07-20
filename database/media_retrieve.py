#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "boto3",
# ]
# ///
"""media_retrieve.py

Retrieve portal media backups from S3.

Usage:
  # list available media backups (production database portal1, default)
  uv run database/media_retrieve.py -l

  # list portal_dev media backups
  uv run database/media_retrieve.py -l media.portal_dev.

  # retrieve most recent portal1 media backup
  uv run database/media_retrieve.py -r

  # retrieve most recent portal_dev media backup
  uv run database/media_retrieve.py -r media.portal_dev.

  # dry run — show what would be downloaded without fetching
  uv run database/media_retrieve.py -r --dry-run

  # production server (software user, newbackup profile)
  uv run database/media_retrieve.py -r --profile newbackup

Notes:
  - Downloads to database/mediarestore/ by default (relative to repo root).
  - Pass the downloaded archive to database/media_restore.sh to extract it.
  - Default AWS profile is opsbackupreader (local dev).
    On the production server use --profile newbackup.
"""

import argparse
import datetime
import os
import sys

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, ProfileNotFound
except ImportError:
    print(
        "ERROR: boto3 is required for this script. Install with `pip install boto3`.",
        file=sys.stderr,
    )
    sys.exit(1)

ME = os.path.splitext(os.path.basename(__file__))[0]
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RESTORE_DIR = os.path.join(REPO_ROOT, "database", "mediarestore")
LOG_DIR = os.path.join(REPO_ROOT, "var")
LOG_FILE = os.path.join(LOG_DIR, f"{ME}.log")

PROJECT = "portal.operations.access-ci.org"
S3_BUCKET = "s3://backup.operations.access-ci.org"
S3_PATH = lambda: f"{S3_BUCKET}/{PROJECT}/media.backup/"
AWS_PROFILE = "opsbackupreader"

MEDIA_PATTERNS = [
    "media.portal1.",       # production (default)
    "media.portal_beta.",
    "media.portal_dev.",
]

VERBOSE = False


def ensure_dirs():
    os.makedirs(RESTORE_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)


def validate_profile(profile):
    try:
        boto3.Session(profile_name=profile)
    except ProfileNotFound:
        print(f"ERROR: AWS profile '{profile}' not found.", file=sys.stderr)
        available = boto3.Session().available_profiles
        if available:
            print(f"Available profiles: {', '.join(available)}", file=sys.stderr)
        sys.exit(1)
    except (BotoCoreError, ClientError) as e:
        print(f"ERROR: Failed to load AWS profile '{profile}': {e}", file=sys.stderr)
        sys.exit(1)


def parse_s3_url(s3_url: str):
    if not s3_url.startswith("s3://"):
        raise ValueError("S3 URL must start with s3://")
    without = s3_url[5:]
    parts = without.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    if prefix and not prefix.endswith("/"):
        prefix = prefix + "/"
    return bucket, prefix


def run_aws_list():
    """Return list of (key, last_modified) tuples sorted by last_modified ascending."""
    bucket_name, prefix = parse_s3_url(S3_PATH())
    session = boto3.Session(profile_name=AWS_PROFILE) if AWS_PROFILE else boto3.Session()
    s3 = session.client("s3")
    objects = []
    paginator = s3.get_paginator("list_objects_v2")
    try:
        for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix or ""):
            for obj in page.get("Contents", []):
                full_key = obj["Key"]
                relative = full_key[len(prefix):] if prefix and full_key.startswith(prefix) else full_key
                if relative:
                    objects.append((relative, obj["LastModified"]))
    except (BotoCoreError, ClientError) as e:
        print(f"ERROR: S3 list failed: {e}", file=sys.stderr)
        sys.exit(1)
    objects.sort(key=lambda x: x[1])
    return objects


def filter_keys(objects, pattern=None):
    if not pattern:
        return objects
    return [(k, ts) for k, ts in objects if pattern in k]


def aws_cp(key, dest):
    bucket_name, prefix = parse_s3_url(S3_PATH())
    full_key = f"{prefix}{key}" if prefix else key
    session = boto3.Session(profile_name=AWS_PROFILE) if AWS_PROFILE else boto3.Session()
    s3 = session.client("s3")
    if VERBOSE:
        print(f"Downloading s3://{bucket_name}/{full_key}")
    try:
        s3.download_file(bucket_name, full_key, dest)
    except (BotoCoreError, ClientError) as e:
        print(f"ERROR: Download failed: {e}", file=sys.stderr)
        return False
    print(f"Retrieved {os.path.getsize(dest)} bytes => {dest}", file=sys.stderr)
    return True


def write_log(msg: str):
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%F_%T")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {msg}\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Retrieve portal media backups from S3"
    )
    parser.add_argument(
        "pattern",
        type=str,
        nargs="?",
        help=(
            "Optional pattern to filter backup files "
            f"(default: {MEDIA_PATTERNS[0]}). "
            f"Known patterns: {', '.join(MEDIA_PATTERNS)}"
        ),
    )
    parser.add_argument(
        "-r", "--retrieve",
        action="store_true",
        help="Download the most recent matching backup",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available backups matching the pattern",
    )
    parser.add_argument(
        "--profile",
        default=AWS_PROFILE,
        help="AWS CLI profile to use (default: %(default)s). Use newbackup on the production server.",
    )
    parser.add_argument(
        "--bucket",
        default=S3_BUCKET,
        help="S3 bucket (default: %(default)s)",
    )
    parser.add_argument(
        "--restore-dir",
        default=RESTORE_DIR,
        help="Directory to download backups into (default: %(default)s)",
    )
    parser.add_argument(
        "--log-dir",
        default=LOG_DIR,
        help="Directory to write logs into (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without downloading",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Increase verbosity",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    global S3_BUCKET, AWS_PROFILE, RESTORE_DIR, LOG_DIR, LOG_FILE, VERBOSE
    S3_BUCKET = args.bucket
    AWS_PROFILE = args.profile
    RESTORE_DIR = args.restore_dir
    LOG_DIR = args.log_dir
    LOG_FILE = os.path.join(LOG_DIR, f"{ME}.log")
    VERBOSE = args.verbose

    # Default to list if neither flag given
    if not args.list and not args.retrieve:
        args.list = True

    pattern = args.pattern or MEDIA_PATTERNS[0]
    if not args.pattern:
        print(f"Using default pattern '{pattern}'", file=sys.stderr)

    ensure_dirs()
    validate_profile(AWS_PROFILE)

    mode = "retrieve" if args.retrieve else "list"
    write_log(f"{ME} Start: mode={mode} pattern={pattern}")

    if VERBOSE:
        print(f"Remote path: {S3_PATH()}")

    objects = run_aws_list()
    if not objects:
        print("No objects found in bucket", file=sys.stderr)
        sys.exit(1)

    matching = filter_keys(objects, pattern)
    print(f"Found {len(matching)} matching objects", file=sys.stderr)

    if args.list:
        for k, ts in matching:
            print(f"=> {S3_PATH()}{k}  ({ts.strftime('%Y-%m-%d %H:%M UTC')})")
        write_log(f"{ME} Listed {len(matching)} items")
        return

    # retrieve
    if not matching:
        print("No matching objects found", file=sys.stderr)
        sys.exit(1)

    chosen, chosen_ts = matching[-1]  # last = most recently modified
    print(f"Selecting most recent: {chosen}  ({chosen_ts.strftime('%Y-%m-%d %H:%M UTC')})", file=sys.stderr)
    dest = os.path.join(RESTORE_DIR, chosen)

    if args.dry_run:
        print(f"Dry-run: would download {S3_PATH()}{chosen}")
        print(f"         modified:    {chosen_ts.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"         destination: {dest}")
        write_log(f"{ME} Dry-run: {chosen}")
        return

    if not aws_cp(chosen, dest):
        write_log(f"{ME} Failed to download {chosen}")
        sys.exit(1)

    print(f"\nArchive ready: {dest}", file=sys.stderr)
    print(f"Next step: bash database/media_restore.sh '{dest}'")
    write_log(f"{ME} Done: {chosen}")


if __name__ == "__main__":
    main()
