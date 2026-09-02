"""Parse Drupal news records from a plain-text MySQL dump.

The cutover input is a ``mysqldump`` SQL file, optionally gzip-compressed.  This
module intentionally has no Django or third-party dependencies so its parser can
be exercised with synthetic fixtures without loading application settings.

Only the explicitly listed Drupal node/field tables are retained.  Other dump
statements are scanned but never parsed into Python objects.
"""

from __future__ import annotations

import gzip
import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, TextIO

SYSTEM_BUNDLE = "infrastructure_news_v2"
INTEGRATION_BUNDLE = "integration_news_v1"
INTEGRATION_ELEMENT_BUNDLE = "integration_element"

REQUIRED_TABLES = {
    "node_field_data",
    "node__field_affected_infrastructure",
    "node__field_affected_intelm",
    "node__field_effective_date",
    "node__field_end_date",
    "node__field_expiration_date",
    "node__field_infra_resourceid",
    "node__field_infrastructure_news_type",
    "node__field_intelm_news_type",
    "node__field_news_content",
    "node__field_start_date",
    "users_field_data",
}

OPTIONAL_TABLES = {
    "node__field_news_distribution_options",
}

TABLES = REQUIRED_TABLES | OPTIONAL_TABLES

# Retain only the non-secret fields needed to resolve Drupal authors.  In
# particular, never decode or store password hashes or email addresses from the
# users table while parsing a dump.
PROJECTED_COLUMNS = {
    "users_field_data": ("uid", "name"),
}

_CREATE_RE = re.compile(r"CREATE TABLE `([^`]+)` \((.*?)\) ENGINE=", re.S)
_COLUMN_RE = re.compile(r"(?:^|,\s*)\s*`([^`]+)`\s+[A-Za-z]", re.S)
_INSERT_RE = re.compile(
    r"INSERT INTO `([^`]+)`(?:\s*\((.*?)\))? VALUES (.*);\s*$",
    re.S,
)
_EXPLICIT_COLUMN_RE = re.compile(r"`([^`]+)`")
_STATEMENT_START_RE = re.compile(r"^\s*(CREATE TABLE|INSERT INTO) `([^`]+)`")


class DrupalDumpError(ValueError):
    """The dump cannot be converted into an unambiguous news payload."""


@dataclass(frozen=True)
class ParsedDump:
    payload: Dict[str, List[dict]]
    sha256: str
    warnings: List[str]
    excluded_system_nids: List[int]
    source_corrections: List[str]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="strict")
    return path.open("rt", encoding="utf-8", errors="strict")


def _split_fields(row: str) -> List[str]:
    fields: List[str] = []
    start = 0
    quoted = False
    escaped = False
    index = 0

    while index < len(row):
        char = row[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "'":
                if index + 1 < len(row) and row[index + 1] == "'":
                    index += 1
                else:
                    quoted = False
        elif char == "'":
            quoted = True
        elif char == ",":
            fields.append(row[start:index].strip())
            start = index + 1
        index += 1

    if quoted or escaped:
        raise DrupalDumpError("Unterminated quoted value in MySQL INSERT row.")
    fields.append(row[start:].strip())
    return fields


def _decode_mysql_literal(token: str):
    if token.upper() == "NULL":
        return None
    if not (len(token) >= 2 and token[0] == token[-1] == "'"):
        return token

    body = token[1:-1]
    decoded: List[str] = []
    escapes = {
        "0": "\0",
        "b": "\b",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "Z": "\x1a",
    }
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body):
            index += 1
            decoded.append(escapes.get(body[index], body[index]))
        elif char == "'" and index + 1 < len(body) and body[index + 1] == "'":
            decoded.append("'")
            index += 1
        else:
            decoded.append(char)
        index += 1
    return "".join(decoded)


def _iter_insert_rows(values: str) -> Iterator[List[str]]:
    quoted = False
    escaped = False
    depth = 0
    start: Optional[int] = None
    index = 0

    while index < len(values):
        char = values[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "'":
                if index + 1 < len(values) and values[index + 1] == "'":
                    index += 1
                else:
                    quoted = False
        elif char == "'":
            quoted = True
        elif char == "(":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise DrupalDumpError("Unbalanced closing parenthesis in MySQL INSERT.")
            if depth == 0 and start is not None:
                yield _split_fields(values[start:index])
                start = None
        index += 1

    if quoted or escaped or depth != 0:
        raise DrupalDumpError("Unterminated row in MySQL INSERT statement.")


def _iter_relevant_statements(handle: TextIO) -> Iterator[tuple[int, str]]:
    pending: List[str] = []
    pending_line = 0

    for line_number, line in enumerate(handle, start=1):
        if pending:
            pending.append(line)
            if line.rstrip().endswith(";"):
                yield pending_line, "".join(pending)
                pending = []
                pending_line = 0
            continue

        match = _STATEMENT_START_RE.match(line)
        if not match or match.group(2) not in TABLES:
            continue
        statement = line[match.start(1):]
        if statement.rstrip().endswith(";"):
            yield line_number, statement
        else:
            pending = [statement]
            pending_line = line_number

    if pending:
        raise DrupalDumpError(
            "Unterminated relevant SQL statement beginning at dump line "
            f"{pending_line}."
        )


def _read_tables(path: Path) -> Dict[str, List[dict]]:
    columns: Dict[str, List[str]] = {}
    rows: Dict[str, List[dict]] = defaultdict(list)

    with _open_text(path) as handle:
        for line_number, statement in _iter_relevant_statements(handle):
            for match in _CREATE_RE.finditer(statement):
                table, body = match.groups()
                if table in TABLES:
                    columns[table] = _COLUMN_RE.findall(body)

            insert = _INSERT_RE.search(statement)
            if not insert or insert.group(1) not in TABLES:
                continue

            table, explicit_columns, values = insert.groups()
            names = (
                _EXPLICIT_COLUMN_RE.findall(explicit_columns)
                if explicit_columns
                else columns.get(table)
            )
            if not names:
                raise DrupalDumpError(
                    f"{table}: INSERT encountered before its column definition "
                    f"at dump line {line_number}."
                )

            projected_names = PROJECTED_COLUMNS.get(table)
            if projected_names:
                missing_projected = sorted(set(projected_names) - set(names))
                if missing_projected:
                    raise DrupalDumpError(
                        f"{table}: missing required author columns: "
                        + ", ".join(missing_projected)
                    )
                projected_indexes = [names.index(name) for name in projected_names]
            else:
                projected_indexes = list(range(len(names)))
                projected_names = tuple(names)

            for raw_values in _iter_insert_rows(values):
                if len(raw_values) != len(names):
                    raise DrupalDumpError(
                        f"{table}: expected {len(names)} values but found "
                        f"{len(raw_values)} at dump line {line_number}."
                    )
                rows[table].append(
                    {
                        name: _decode_mysql_literal(raw_values[index])
                        for name, index in zip(projected_names, projected_indexes)
                    }
                )

    missing = sorted(REQUIRED_TABLES - columns.keys())
    if missing:
        raise DrupalDumpError(
            "Dump is missing required Drupal table definitions: " + ", ".join(missing)
        )
    return rows


def _positive_int(value, context: str) -> int:
    if isinstance(value, bool):
        raise DrupalDumpError(f"{context} must be a positive integer, got {value!r}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DrupalDumpError(
            f"{context} must be a positive integer, got {value!r}."
        ) from exc
    if parsed <= 0:
        raise DrupalDumpError(f"{context} must be positive, got {parsed}.")
    return parsed


def _nonnegative_int(value, context: str) -> int:
    if isinstance(value, bool):
        raise DrupalDumpError(
            f"{context} must be a nonnegative integer, got {value!r}."
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DrupalDumpError(
            f"{context} must be a nonnegative integer, got {value!r}."
        ) from exc
    if parsed < 0:
        raise DrupalDumpError(f"{context} must be nonnegative, got {parsed}.")
    return parsed


def _unix_datetime(value, context: str) -> Optional[str]:
    if value in (None, ""):
        return None
    timestamp = _positive_int(value, context)
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError) as exc:
        raise DrupalDumpError(
            f"{context} is outside the supported timestamp range."
        ) from exc


def _validate_datetime(value, context: str) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DrupalDumpError(f"{context} is not an ISO datetime: {value!r}.") from exc
    if not 2000 <= parsed.year <= 2100:
        raise DrupalDumpError(
            f"{context} has implausible year {parsed.year}: {value!r}. "
            "Correct the Drupal source or document an explicit approved override."
        )
    return str(value)


def _validate_date(value, context: str) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError as exc:
        raise DrupalDumpError(f"{context} is not an ISO date: {value!r}.") from exc
    if not 2000 <= parsed.year <= 2100:
        raise DrupalDumpError(
            f"{context} has implausible year {parsed.year}: {value!r}. "
            "Correct the Drupal source or document an explicit approved override."
        )
    return str(value)


def _current_rows(rows: Iterable[dict], bundle: Optional[str] = None) -> List[dict]:
    current = []
    for row in rows:
        if bundle is not None and row.get("bundle") != bundle:
            continue
        if str(row.get("deleted", "0")) != "0":
            continue
        current.append(row)
    return current


def _group_by_entity(rows: Iterable[dict], bundle: str) -> Dict[int, List[dict]]:
    grouped: Dict[int, List[dict]] = defaultdict(list)
    for row in _current_rows(rows, bundle):
        entity_id = _positive_int(row.get("entity_id"), f"{bundle} entity_id")
        grouped[entity_id].append(row)
    for entity_rows in grouped.values():
        entity_rows.sort(key=lambda row: int(row.get("delta") or 0))
    return grouped


def _one_value(
    grouped: Mapping[int, Sequence[dict]],
    entity_id: int,
    column: str,
    context: str,
    *,
    required: bool,
):
    matching = grouped.get(entity_id, [])
    if len(matching) > 1:
        raise DrupalDumpError(
            f"{context} has {len(matching)} values; expected at most one."
        )
    value = matching[0].get(column) if matching else None
    if required and value in (None, ""):
        raise DrupalDumpError(f"{context} is missing a required value.")
    return value


def _choice_map(choices: Sequence[Sequence[str]], context: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for code, label in choices:
        if label in mapping:
            raise DrupalDumpError(f"{context} contains duplicate label {label!r}.")
        mapping[label] = code
    return mapping


def _news_nodes(table_rows: Mapping[str, List[dict]], bundle: str) -> List[dict]:
    nodes = [row for row in table_rows["node_field_data"] if row.get("type") == bundle]
    seen: set[int] = set()
    normalized = []
    for row in nodes:
        nid = _positive_int(row.get("nid"), f"{bundle} nid")
        if nid in seen:
            raise DrupalDumpError(f"{bundle} contains duplicate node nid {nid}.")
        seen.add(nid)
        normalized.append(row)
    if not normalized:
        raise DrupalDumpError(f"Dump contains no {bundle} nodes.")
    return sorted(normalized, key=lambda row: int(row["nid"]))


def parse_drupal_news_dump(
    path: Path,
    *,
    infrastructure_type_choices: Sequence[Sequence[str]],
    integration_type_choices: Sequence[Sequence[str]],
    integration_element_choices: Sequence[Sequence[str]],
    excluded_system_nids: Sequence[int] = (),
    system_start_datetime_corrections: Mapping[int, tuple[str, str]] | None = None,
) -> ParsedDump:
    """Convert current Drupal news field tables into the importer's JSON shape."""

    path = Path(path)
    if not path.is_file():
        raise DrupalDumpError(f"MySQL dump does not exist or is not a file: {path}")

    table_rows = _read_tables(path)
    usernames_by_uid: Dict[int, str] = {}
    for row in table_rows["users_field_data"]:
        uid = _nonnegative_int(row.get("uid"), "users_field_data uid")
        raw_username = row.get("name")
        if raw_username is None:
            username = ""
        elif isinstance(raw_username, str):
            username = raw_username
        else:
            raise DrupalDumpError(
                f"users_field_data uid={uid} has a non-text username."
            )
        existing_username = usernames_by_uid.get(uid)
        if existing_username is not None and existing_username != username:
            raise DrupalDumpError(
                f"users_field_data uid={uid} has conflicting usernames."
            )
        usernames_by_uid[uid] = username
    infrastructure_types = _choice_map(
        infrastructure_type_choices, "Infrastructure news choices"
    )
    integration_types = _choice_map(
        integration_type_choices, "Integration news choices"
    )
    integration_elements = _choice_map(
        integration_element_choices, "Integration element choices"
    )
    excluded_system_nid_set = {
        _positive_int(value, "Excluded Infrastructure News nid")
        for value in excluded_system_nids
    }
    start_datetime_corrections = dict(system_start_datetime_corrections or {})
    for correction_nid, correction_values in start_datetime_corrections.items():
        _positive_int(correction_nid, "Corrected Infrastructure News nid")
        if len(correction_values) != 2:
            raise DrupalDumpError(
                "Infrastructure News start-date corrections require exact "
                "(source, replacement) pairs."
            )

    content = _group_by_entity(table_rows["node__field_news_content"], SYSTEM_BUNDLE)
    content.update(
        _group_by_entity(table_rows["node__field_news_content"], INTEGRATION_BUNDLE)
    )
    infrastructure_type = _group_by_entity(
        table_rows["node__field_infrastructure_news_type"], SYSTEM_BUNDLE
    )
    integration_type = _group_by_entity(
        table_rows["node__field_intelm_news_type"], INTEGRATION_BUNDLE
    )
    start_dates = _group_by_entity(table_rows["node__field_start_date"], SYSTEM_BUNDLE)
    end_dates = _group_by_entity(table_rows["node__field_end_date"], SYSTEM_BUNDLE)
    effective_dates = _group_by_entity(
        table_rows["node__field_effective_date"], INTEGRATION_BUNDLE
    )
    expiration_dates = _group_by_entity(
        table_rows["node__field_expiration_date"], INTEGRATION_BUNDLE
    )
    affected_infrastructure = _group_by_entity(
        table_rows["node__field_affected_infrastructure"], SYSTEM_BUNDLE
    )
    affected_integration = _group_by_entity(
        table_rows["node__field_affected_intelm"], INTEGRATION_BUNDLE
    )
    distribution_system = _group_by_entity(
        table_rows.get("node__field_news_distribution_options", []), SYSTEM_BUNDLE
    )

    node_by_id: Dict[int, dict] = {}
    for row in table_rows["node_field_data"]:
        nid = _positive_int(row.get("nid"), "node_field_data nid")
        if nid in node_by_id:
            raise DrupalDumpError(f"node_field_data contains duplicate nid {nid}.")
        node_by_id[nid] = row
    for table, rows in table_rows.items():
        if table == "node_field_data":
            continue
        for row in _current_rows(rows):
            if row.get("bundle") not in {
                SYSTEM_BUNDLE,
                INTEGRATION_BUNDLE,
                "infrastructure",
            }:
                continue
            entity_id = _positive_int(row.get("entity_id"), f"{table} entity_id")
            node = node_by_id.get(entity_id)
            if node is None:
                raise DrupalDumpError(
                    f"{table} references missing node_field_data nid {entity_id}."
                )
            revision_id = _positive_int(
                row.get("revision_id"), f"{table} entity_id={entity_id} revision_id"
            )
            node_revision = _positive_int(
                node.get("vid"), f"node_field_data nid={entity_id} vid"
            )
            if revision_id != node_revision:
                raise DrupalDumpError(
                    f"{table} entity_id={entity_id} belongs to revision {revision_id}, "
                    f"but node_field_data selects revision {node_revision}."
                )
    infrastructure_resource_ids = {
        _positive_int(row.get("entity_id"), "infrastructure entity_id"): row.get(
            "field_infra_resourceid_value"
        )
        for row in _current_rows(table_rows["node__field_infra_resourceid"])
    }

    element_code_by_nid: Dict[int, str] = {}
    for nid, node in node_by_id.items():
        if node.get("type") != INTEGRATION_ELEMENT_BUNDLE:
            continue
        label = node.get("title") or ""
        code = integration_elements.get(label)
        if code:
            element_code_by_nid[nid] = code

    warnings: List[str] = []
    excluded_system_nids_found: List[int] = []
    source_corrections: List[str] = []
    corrected_system_nids: set[int] = set()
    system_records: List[dict] = []
    for node in _news_nodes(table_rows, SYSTEM_BUNDLE):
        nid = _positive_int(node.get("nid"), "Infrastructure News nid")
        if nid in excluded_system_nid_set:
            excluded_system_nids_found.append(nid)
            continue
        author_uid = _nonnegative_int(
            node.get("uid"), f"Infrastructure News nid={nid} author uid"
        )
        posted_at = _unix_datetime(
            node.get("created"), f"Infrastructure News nid={nid} created"
        )
        if posted_at is None:
            raise DrupalDumpError(
                f"Infrastructure News nid={nid} is missing its original post date."
            )

        type_label = _one_value(
            infrastructure_type,
            nid,
            "field_infrastructure_news_type_value",
            f"Infrastructure News nid={nid} type",
            required=True,
        )
        type_code = infrastructure_types.get(type_label)
        if not type_code:
            raise DrupalDumpError(
                f"Infrastructure News nid={nid} has unknown type label {type_label!r}."
            )

        related_nodes = []
        resource_ids = []
        seen_resource_ids = set()
        for related in affected_infrastructure.get(nid, []):
            target_nid = _positive_int(
                related.get("field_affected_infrastructure_target_id"),
                f"Infrastructure News nid={nid} affected target",
            )
            target_node = node_by_id.get(target_nid)
            if not target_node or target_node.get("type") != "infrastructure":
                raise DrupalDumpError(
                    f"Infrastructure News nid={nid} references invalid infrastructure "
                    f"node {target_nid}."
                )
            resource_id = infrastructure_resource_ids.get(target_nid)
            if not resource_id:
                raise DrupalDumpError(
                    f"Infrastructure node {target_nid} referenced by news nid={nid} "
                    "has no field_infra_resourceid value."
                )
            if resource_id in seen_resource_ids:
                raise DrupalDumpError(
                    f"Infrastructure News nid={nid} repeats resource ID "
                    f"{resource_id!r}."
                )
            seen_resource_ids.add(resource_id)
            resource_ids.append(resource_id)
            related_nodes.append(
                {"target_nid": target_nid, "resource_id": resource_id}
            )

        distribution_values = {
            row.get("field_news_distribution_options_value")
            for row in distribution_system.get(nid, [])
        }
        start_datetime_source = _one_value(
            start_dates,
            nid,
            "field_start_date_value",
            f"Infrastructure News nid={nid} start date",
            required=True,
        )
        correction = start_datetime_corrections.get(nid)
        if correction is not None:
            expected_source, replacement = correction
            if start_datetime_source != expected_source:
                raise DrupalDumpError(
                    f"Infrastructure News nid={nid} start date correction expected "
                    f"{expected_source!r}, found {start_datetime_source!r}; refusing "
                    "to alter an unexpected source value."
                )
            _validate_datetime(
                replacement,
                f"Infrastructure News nid={nid} corrected start date",
            )
            start_datetime_source = replacement
            corrected_system_nids.add(nid)
            source_corrections.append(
                f"SystemStatusNews nid={nid} start_datetime: "
                f"{expected_source!r} -> {replacement!r}"
            )

        system_records.append(
            {
                "subject": node.get("title") or "Untitled",
                "content": _one_value(
                    content,
                    nid,
                    "field_news_content_value",
                    f"Infrastructure News nid={nid} content",
                    required=False,
                )
                or "",
                "infrastructure_news_type": type_code,
                "affected_infrastructure": ",".join(resource_ids),
                "start_datetime": _validate_datetime(
                    start_datetime_source,
                    f"Infrastructure News nid={nid} start date",
                ),
                "end_datetime": _validate_datetime(
                    _one_value(
                        end_dates,
                        nid,
                        "field_end_date_value",
                        f"Infrastructure News nid={nid} end date",
                        required=False,
                    ),
                    f"Infrastructure News nid={nid} end date",
                ),
                "send_email": bool(
                    distribution_values
                    & {"Email only subscribers", "Email everyone with access"}
                ),
                "post_to_slack": "Post to Slack" in distribution_values,
                "is_active": str(node.get("status")) == "1",
                "status": "published" if str(node.get("status")) == "1" else "draft",
                "source_metadata": {
                    "drupal_nid": nid,
                    "drupal_vid": _positive_int(
                        node.get("vid"), f"Infrastructure News nid={nid} vid"
                    ),
                    "drupal_created_at": posted_at,
                    "drupal_author": {
                        "uid": author_uid,
                        "username": usernames_by_uid.get(author_uid, ""),
                    },
                    "affected_infrastructure_nodes": related_nodes,
                },
            }
        )

    missing_exclusions = sorted(
        excluded_system_nid_set - set(excluded_system_nids_found)
    )
    if missing_exclusions:
        raise DrupalDumpError(
            "Requested Infrastructure News exclusions were not present in the dump: "
            + ", ".join(str(value) for value in missing_exclusions)
        )
    missing_corrections = sorted(
        set(start_datetime_corrections) - corrected_system_nids
    )
    if missing_corrections:
        raise DrupalDumpError(
            "Requested Infrastructure News corrections were not applied: "
            + ", ".join(str(value) for value in missing_corrections)
        )

    integration_records: List[dict] = []
    for node in _news_nodes(table_rows, INTEGRATION_BUNDLE):
        nid = _positive_int(node.get("nid"), "Integration News nid")
        author_uid = _nonnegative_int(
            node.get("uid"), f"Integration News nid={nid} author uid"
        )
        posted_at = _unix_datetime(
            node.get("created"), f"Integration News nid={nid} created"
        )
        if posted_at is None:
            raise DrupalDumpError(
                f"Integration News nid={nid} is missing its original post date."
            )
        type_label = _one_value(
            integration_type,
            nid,
            "field_intelm_news_type_value",
            f"Integration News nid={nid} type",
            required=True,
        )
        type_code = integration_types.get(type_label)
        if not type_code:
            raise DrupalDumpError(
                f"Integration News nid={nid} has unknown type label {type_label!r}."
            )

        selected_codes: List[str] = []
        selected_targets: List[dict] = []
        for related in affected_integration.get(nid, []):
            target_nid = _positive_int(
                related.get("field_affected_intelm_target_id"),
                f"Integration News nid={nid} affected target",
            )
            target_node = node_by_id.get(target_nid)
            if not target_node or target_node.get("type") != INTEGRATION_ELEMENT_BUNDLE:
                raise DrupalDumpError(
                    f"Integration News nid={nid} references invalid integration "
                    f"element node {target_nid}."
                )
            label = target_node.get("title") or ""
            code = element_code_by_nid.get(target_nid)
            if not code:
                raise DrupalDumpError(
                    f"Integration element node {target_nid} has unmapped label "
                    f"{label!r}."
                )
            if code in selected_codes:
                raise DrupalDumpError(
                    f"Integration News nid={nid} repeats integration element {code!r}."
                )
            selected_codes.append(code)
            selected_targets.append(
                {"target_nid": target_nid, "code": code, "label": label}
            )

        integration_records.append(
            {
                "title": node.get("title") or "Untitled",
                "content": _one_value(
                    content,
                    nid,
                    "field_news_content_value",
                    f"Integration News nid={nid} content",
                    required=True,
                ),
                "news_type": type_code,
                "affected_elements": selected_codes,
                "affected_element": (
                    selected_codes[0] if len(selected_codes) == 1 else ""
                ),
                "effective_date": _validate_date(
                    _one_value(
                        effective_dates,
                        nid,
                        "field_effective_date_value",
                        f"Integration News nid={nid} effective date",
                        required=True,
                    ),
                    f"Integration News nid={nid} effective date",
                ),
                "expiration_date": _validate_date(
                    _one_value(
                        expiration_dates,
                        nid,
                        "field_expiration_date_value",
                        f"Integration News nid={nid} expiration date",
                        required=False,
                    ),
                    f"Integration News nid={nid} expiration date",
                ),
                "is_active": str(node.get("status")) == "1",
                "status": "published" if str(node.get("status")) == "1" else "draft",
                "source_metadata": {
                    "drupal_nid": nid,
                    "drupal_vid": _positive_int(
                        node.get("vid"), f"Integration News nid={nid} vid"
                    ),
                    "drupal_created_at": posted_at,
                    "drupal_author": {
                        "uid": author_uid,
                        "username": usernames_by_uid.get(author_uid, ""),
                    },
                    "affected_integration_elements": selected_targets,
                },
            }
        )

    if any(not record["content"] for record in system_records):
        empty_ids = [
            record["source_metadata"]["drupal_nid"]
            for record in system_records
            if not record["content"]
        ]
        warnings.append(
            "Infrastructure News records with empty content: "
            + ", ".join(str(value) for value in empty_ids)
        )

    return ParsedDump(
        payload={
            "SystemStatusNews": system_records,
            "IntegrationNews": integration_records,
        },
        sha256=sha256_file(path),
        warnings=warnings,
        excluded_system_nids=sorted(excluded_system_nids_found),
        source_corrections=source_corrections,
    )
