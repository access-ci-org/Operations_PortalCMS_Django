import gzip
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from .drupal_mysql import DrupalDumpError, parse_drupal_news_dump

INFRASTRUCTURE_TYPES = [
    ("outage_full", "Outage Full"),
]
INTEGRATION_TYPES = [
    ("software_release", "Software Release"),
]
INTEGRATION_ELEMENTS = [
    (
        "compute_roadmap",
        "ACCESS Allocated Production Compute - Integration Roadmap",
    ),
    ("accessusage", "accessusage - command line allocation usage lookup"),
]

FIELD_PREFIX = ["bundle", "deleted", "entity_id", "revision_id", "langcode", "delta"]

TABLE_COLUMNS = {
    "node_field_data": [
        "nid",
        "vid",
        "type",
        "langcode",
        "status",
        "uid",
        "title",
        "created",
        "changed",
        "promote",
        "sticky",
        "default_langcode",
        "revision_translation_affected",
    ],
    "node__field_affected_infrastructure": FIELD_PREFIX
    + ["field_affected_infrastructure_target_id"],
    "node__field_affected_intelm": FIELD_PREFIX + ["field_affected_intelm_target_id"],
    "node__field_effective_date": FIELD_PREFIX + ["field_effective_date_value"],
    "node__field_end_date": FIELD_PREFIX + ["field_end_date_value"],
    "node__field_expiration_date": FIELD_PREFIX + ["field_expiration_date_value"],
    "node__field_infra_resourceid": FIELD_PREFIX + ["field_infra_resourceid_value"],
    "node__field_infrastructure_news_type": FIELD_PREFIX
    + ["field_infrastructure_news_type_value"],
    "node__field_intelm_news_type": FIELD_PREFIX + ["field_intelm_news_type_value"],
    "node__field_news_content": FIELD_PREFIX
    + ["field_news_content_value", "field_news_content_format"],
    "node__field_news_distribution_options": FIELD_PREFIX
    + ["field_news_distribution_options_value"],
    "node__field_start_date": FIELD_PREFIX + ["field_start_date_value"],
    # The parser must project only uid/name and never retain mail/pass.
    "users_field_data": ["uid", "name", "mail", "pass"],
}


def _sql_literal(value):
    if value is None:
        return "NULL"
    text = str(value)
    text = (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f"'{text}'"


def _field_row(bundle, entity_id, value, *, delta=0, revision_id=None):
    return [
        bundle,
        0,
        entity_id,
        revision_id or entity_id + 1000,
        "en",
        delta,
        value,
    ]


def _node_row(nid, vid, bundle, title, timestamp, *, uid=1):
    return [nid, vid, bundle, "en", 1, uid, title, timestamp, timestamp, 0, 0, 1, 1]


def _base_rows():
    return {
        "node_field_data": [
            _node_row(
                101, 1101, "infrastructure_news_v2", "System title", 1700000000
            ),
            _node_row(
                201, 1201, "integration_news_v1", "Integration title", 1700000100
            ),
            _node_row(301, 1301, "infrastructure", "Resource", 1700000200),
            _node_row(
                401,
                1401,
                "integration_element",
                "ACCESS Allocated Production Compute - Integration Roadmap",
                1700000300,
            ),
            _node_row(
                402,
                1402,
                "integration_element",
                "accessusage - command line allocation usage lookup",
                1700000400,
            ),
        ],
        "node__field_affected_infrastructure": [
            _field_row("infrastructure_news_v2", 101, 301),
        ],
        "node__field_affected_intelm": [
            _field_row("integration_news_v1", 201, 401, delta=0),
            _field_row("integration_news_v1", 201, 402, delta=1),
        ],
        "node__field_effective_date": [
            _field_row("integration_news_v1", 201, "2026-08-01"),
        ],
        "node__field_end_date": [
            _field_row("infrastructure_news_v2", 101, "2026-08-01T13:00:00"),
        ],
        "node__field_expiration_date": [],
        "node__field_infra_resourceid": [
            _field_row("infrastructure", 301, "resource.example"),
        ],
        "node__field_infrastructure_news_type": [
            _field_row("infrastructure_news_v2", 101, "Outage Full"),
        ],
        "node__field_intelm_news_type": [
            _field_row("integration_news_v1", 201, "Software Release"),
        ],
        "node__field_news_content": [
            _field_row(
                "infrastructure_news_v2",
                101,
                "System's first line, with (parentheses) — and Unicode\nsecond line",
            )
            + ["full_html"],
            _field_row("integration_news_v1", 201, "Integration content")
            + ["full_html"],
        ],
        "node__field_news_distribution_options": [
            _field_row("infrastructure_news_v2", 101, "Post to Slack"),
        ],
        "node__field_start_date": [
            _field_row("infrastructure_news_v2", 101, "2026-08-01T12:00:00"),
        ],
        "users_field_data": [
            [1, "drupal_author", "not-retained@example.test", "not-retained-hash"],
        ],
    }


def _dump_text(rows=None, *, omit_table=None, multiline_definitions=False):
    rows = rows or _base_rows()
    statements = []
    for table, columns in TABLE_COLUMNS.items():
        if table == omit_table:
            continue
        separator = ",\n  " if multiline_definitions else ", "
        definitions = separator.join(f"`{column}` text" for column in columns)
        statements.append(f"CREATE TABLE `{table}` ({definitions}) ENGINE=InnoDB;")
        table_rows = rows.get(table, [])
        if table_rows:
            values = ",".join(
                "(" + ",".join(_sql_literal(value) for value in row) + ")"
                for row in table_rows
            )
            statements.append(f"INSERT INTO `{table}` VALUES {values};")
    return "\n".join(statements) + "\n"


class DrupalMysqlParserTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def _write(self, text, *, compressed=False):
        suffix = ".mysql.gz" if compressed else ".mysql"
        path = Path(self.temp_dir.name) / f"source{suffix}"
        if compressed:
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                handle.write(text)
        else:
            path.write_text(text, encoding="utf-8")
        return path

    def _parse(self, path):
        return parse_drupal_news_dump(
            path,
            infrastructure_type_choices=INFRASTRUCTURE_TYPES,
            integration_type_choices=INTEGRATION_TYPES,
            integration_element_choices=INTEGRATION_ELEMENTS,
        )

    def test_parses_both_feeds_and_preserves_all_relationships(self):
        path = self._write(_dump_text(), compressed=True)

        parsed = self._parse(path)

        self.assertEqual(parsed.sha256, hashlib.sha256(path.read_bytes()).hexdigest())
        system = parsed.payload["SystemStatusNews"][0]
        self.assertEqual(
            system["content"],
            "System's first line, with (parentheses) — and Unicode\nsecond line",
        )
        self.assertEqual(system["affected_infrastructure"], "resource.example")
        self.assertTrue(system["post_to_slack"])
        self.assertEqual(
            system["source_metadata"]["drupal_author"],
            {"uid": 1, "username": "drupal_author"},
        )
        self.assertEqual(
            system["source_metadata"]["drupal_created_at"],
            "2023-11-14T22:13:20+00:00",
        )
        self.assertNotIn("mail", system["source_metadata"]["drupal_author"])
        self.assertNotIn("pass", system["source_metadata"]["drupal_author"])

        integration = parsed.payload["IntegrationNews"][0]
        self.assertEqual(
            integration["affected_elements"], ["compute_roadmap", "accessusage"]
        )
        self.assertEqual(
            integration["source_metadata"]["drupal_author"],
            {"uid": 1, "username": "drupal_author"},
        )
        self.assertEqual(
            integration["source_metadata"]["drupal_created_at"],
            "2023-11-14T22:15:00+00:00",
        )
        self.assertEqual(integration["affected_element"], "")
        self.assertEqual(
            [
                item["target_nid"]
                for item in integration["source_metadata"][
                    "affected_integration_elements"
                ]
            ],
            [401, 402],
        )

    def test_rejects_implausible_source_date_without_guessing(self):
        rows = _base_rows()
        rows["node__field_start_date"][0][-1] = "0026-08-01T12:00:00"
        path = self._write(_dump_text(rows))

        with self.assertRaisesRegex(DrupalDumpError, "implausible year 26"):
            self._parse(path)

    def test_applies_requested_exact_match_start_date_correction(self):
        rows = _base_rows()
        rows["node__field_start_date"][0][-1] = "0026-08-01T12:00:00"
        path = self._write(_dump_text(rows))

        parsed = parse_drupal_news_dump(
            path,
            infrastructure_type_choices=INFRASTRUCTURE_TYPES,
            integration_type_choices=INTEGRATION_TYPES,
            integration_element_choices=INTEGRATION_ELEMENTS,
            system_start_datetime_corrections={
                101: ("0026-08-01T12:00:00", "2026-08-01T12:00:00")
            },
        )

        self.assertEqual(
            parsed.payload["SystemStatusNews"][0]["start_datetime"],
            "2026-08-01T12:00:00",
        )
        self.assertEqual(len(parsed.source_corrections), 1)

    def test_rejects_correction_when_source_does_not_match(self):
        path = self._write(_dump_text())

        with self.assertRaisesRegex(DrupalDumpError, "expected .* found"):
            parse_drupal_news_dump(
                path,
                infrastructure_type_choices=INFRASTRUCTURE_TYPES,
                integration_type_choices=INTEGRATION_TYPES,
                integration_element_choices=INTEGRATION_ELEMENTS,
                system_start_datetime_corrections={
                    101: ("0026-08-01T12:00:00", "2026-08-01T12:00:00")
                },
            )

    def test_excludes_only_requested_existing_system_nid(self):
        rows = _base_rows()
        rows["node__field_news_content"][0][-2] = ""
        path = self._write(_dump_text(rows))

        parsed = parse_drupal_news_dump(
            path,
            infrastructure_type_choices=INFRASTRUCTURE_TYPES,
            integration_type_choices=INTEGRATION_TYPES,
            integration_element_choices=INTEGRATION_ELEMENTS,
            excluded_system_nids=[101],
        )

        self.assertEqual(parsed.payload["SystemStatusNews"], [])
        self.assertEqual(parsed.excluded_system_nids, [101])
        self.assertEqual(parsed.warnings, [])

    def test_rejects_requested_exclusion_missing_from_source(self):
        path = self._write(_dump_text())

        with self.assertRaisesRegex(DrupalDumpError, "exclusions were not present"):
            parse_drupal_news_dump(
                path,
                infrastructure_type_choices=INFRASTRUCTURE_TYPES,
                integration_type_choices=INTEGRATION_TYPES,
                integration_element_choices=INTEGRATION_ELEMENTS,
                excluded_system_nids=[404],
            )

    def test_accepts_standard_multiline_create_table_statements(self):
        path = self._write(_dump_text(multiline_definitions=True))

        parsed = self._parse(path)

        self.assertEqual(len(parsed.payload["SystemStatusNews"]), 1)
        self.assertEqual(len(parsed.payload["IntegrationNews"]), 1)

    def test_rejects_missing_required_table_definition(self):
        path = self._write(_dump_text(omit_table="node__field_affected_intelm"))

        with self.assertRaisesRegex(
            DrupalDumpError, "node__field_affected_intelm"
        ):
            self._parse(path)

    def test_preserves_uid_but_leaves_username_blank_for_deleted_user(self):
        rows = _base_rows()
        rows["node_field_data"][0][5] = 99
        path = self._write(_dump_text(rows))

        parsed = self._parse(path)

        self.assertEqual(
            parsed.payload["SystemStatusNews"][0]["source_metadata"][
                "drupal_author"
            ],
            {"uid": 99, "username": ""},
        )

    def test_treats_anonymized_null_username_as_blank(self):
        rows = _base_rows()
        rows["users_field_data"][0][1] = None
        path = self._write(_dump_text(rows))

        parsed = self._parse(path)

        self.assertEqual(
            parsed.payload["SystemStatusNews"][0]["source_metadata"]["drupal_author"],
            {"uid": 1, "username": ""},
        )

    def test_rejects_duplicate_multi_value_reference(self):
        rows = _base_rows()
        rows["node__field_affected_intelm"].append(
            _field_row("integration_news_v1", 201, 401, delta=2)
        )
        path = self._write(_dump_text(rows))

        with self.assertRaisesRegex(DrupalDumpError, "repeats integration element"):
            self._parse(path)
