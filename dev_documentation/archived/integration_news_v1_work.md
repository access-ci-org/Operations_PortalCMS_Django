# Integration News API + Importer — In-Progress Work

Status as of 2026-08-31. Nothing in this doc is committed to git yet — see
"Current repo state" below. If you're a fresh session picking this up, read
this whole file before touching code.

## Working protocol for this task

This work runs under an orchestrator-as-architect / agent-as-executor split:

- Before any new edit, call `mcp__orchestrator__ask_orchestrator` with the
  exact task, `repo_root=/Users/jelambeadmin/Documents/access-sysops/Operations_PortalCMS_Django`,
  and this `effective_constraints` block:

  ```
  Treat effective AGENTS.md guidance as authoritative.
  Preserve all pre-existing tracked, untracked, submodule, and nested-repository work.
  Do not commit, push, merge, tag, release, deploy, access secrets, run infrastructure
  plans or playbooks, perform migrations, or restart services without separate explicit
  authorization. Report files changed, checks run and results, checks not run, failures,
  assumptions, and unresolved deployment or security risks.
  ```

- Evaluate its advice, don't apply it blindly — it has suggested DRF patterns
  this codebase doesn't use, and a deprecation-redirect shim for a route that
  was never deployed. It's useful as a second opinion, not ground truth.
- No commits, pushes, migrations, or live DB/infra actions without separate
  explicit authorization from the user.
- No `manage.py check`/`test` in this sandbox — both require live `APP_CONFIG`
  pointing at Postgres (no sqlite fallback in `settings.py`), and no
  credentials are available here. `py_compile` is the only check that's been
  run.

## Goal

Two related pieces of work:

1. **Build a public JSON API** at `/api/integration_news` on the Django side,
   matching the structure of the legacy Drupal `/api/integration_news`
   endpoint (an external system may consume it), following the same pattern
   already used for `/api/infrastructure_news_v1`.
2. **Build an importer** that gets real Drupal integration-news data into the
   Django/Postgres `IntegrationNews` table so that API has real data to serve.

## Part 1: API endpoint — DONE, uncommitted

Files changed (mirrors the existing `infrastructure_news` API pattern — plain
Django `JsonResponse` view + a `services.py` helper, **not** DRF):

- `operations_portalcms_django/integration_news/services.py` (new) — builds
  the JSON payload from `IntegrationNews` queryset.
- `operations_portalcms_django/integration_news/views.py` — added
  `api_integration_news` view (`@require_safe`, `@cache_page(60*15)`).
- `operations_portalcms_django/integration_news/urls.py` — added the route.
- `operations_portalcms_django/integration_news/tests.py` — added
  `ApiIntegrationNewsTests`.

**Route:** `/api/integration_news` — deliberately **unversioned** (unlike
`/api/infrastructure_news_v1`, which stays versioned). This was an explicit
user decision: an external consumer already polls Drupal's unversioned
`/api/integration_news` today and needs that exact path to keep working
through the cutover to Django. Do not rename this back to `_v1`.

**Field structure**, verified against the live Drupal API by curling
`https://operations.access-ci.org/api/integration_news` directly:

| Field | Source | Notes |
|---|---|---|
| `subject` | `IntegrationNews.title` | |
| `type` | `get_news_type_label()` | Django's `INTEGRATION_NEWS_TYPES` choice labels already match Drupal's display strings exactly |
| `content` | `IntegrationNews.content` | |
| `effective_date` | `IntegrationNews.effective_date.isoformat()` | |
| `web_url` | always `reverse('integration_news:integration_news')` | **Known gap**: Drupal gives a real per-node permalink (`/node/602`); Django has no per-item detail view, so every item gets the same listing-page URL. Same simplification the existing infra endpoint already makes. |
| `integration_news_id` | `str(IntegrationNews.integration_news_id)` or `null` | The stable ID. **Currently NULL for every row in the DB — see Part 2.** |
| `distribution_options` | always `""` | Drupal has real per-node values (`"Email only subscribers"`, etc.) via `field_news_distribution_options`, but `IntegrationNews` has no field to store it. User confirmed: not worried about this, skip it. |
| `affected_integration_element` | `[{"title": label} for label in get_affected_element_labels()]` | Drupal's raw objects also have `id`/`url`/`uid`/`created` (Drupal-CMS-specific); dropped, same simplification as infra's `affected_infrastructure`. |

## Part 2: Importer — IMPLEMENTED, UNCOMMITTED

The canonical existing command remains
`infrastructure_news/management/commands/import_drupal_news.py`, so both
`SystemStatusNews` and `IntegrationNews` continue to be replaced and verified
inside one PostgreSQL transaction. It now accepts `--mysql-dump` and parses a
raw plain-SQL or gzip-compressed MySQL dump directly through the new pure-Python
`infrastructure_news/drupal_mysql.py` module. This removes the dependency on the
missing `analyze_news_migration.py` and `normalize_news_for_django.py` scripts.

### Decisions locked in (do not re-litigate without new info)

1. **Multi-element fidelity**: resolve *all* `field_affected_intelm` targets
   per node into the `affected_elements` M2M — not the existing importer's
   single-primary-pick-plus-N/A-fallback behavior. Drupal data is genuinely
   multi-valued (e.g. node 692 references 5 elements); collapsing to one is
   real, avoidable data loss and works against the "match Drupal's structure"
   goal. `IntegrationNews.get_affected_element_labels()` already prefers the
   M2M over the legacy single `affected_element` field, so no model change
   needed beyond item 2 below.
2. **Add 2 missing `AFFECTED_ELEMENTS` entries** to
   `integration_news/models.py` (`IntegrationNews.AFFECTED_ELEMENTS`) — not a
   migration, just a Python choices-list edit:
   - `"accessusage - command line allocation usage lookup"`
   - `"access-oauth-mapfile - ACCESS OAuth identity to local account mapping"`
   Needed because Drupal nodes 949 and 950 (the two newest integration items,
   not yet imported) reference these two `integration_element` nodes
   (947, 948), and today's `AFFECTED_ELEMENTS` list only has 9 of Drupal's 11.
3. **Skip `distribution_options`** entirely — not persisted, matches Part 1.
4. **Must backfill `integration_news_id` on existing rows, not just insert
   new ones.** See "Critical finding" below — this is the most important
   thing a new session needs to know before writing any import code.
5. **`--replace` (atomic wipe-and-reload) scope**: implemented
   (see "Critical finding" #2 below — the only rows at risk are 10 known
   local test records, not real Drupal history), same guardrails as the
   existing command's `--replace` (`--confirm-database`/`--confirm-host`,
   requires `--apply`). Raw-dump mode refuses additive imports and requires
   target confirmation, notification suppression, strict validation, a
   reviewed source SHA-256, and operator-confirmed feed counts before apply.
6. **Data source and lifecycle are decided.** Rehearsals use recent MySQL
   dumps; final cutover uses the final frozen MySQL dump. This is a one-time
   replacement workflow rehearsed repeatedly, not a live API sync.
7. **Two explicit source adjustments are approved.** Every rehearsal and apply
   excludes Infrastructure News nid 404 with `--exclude-system-nid 404` and
   applies the named exact-match nid 928 year correction with
   `--source-correction infrastructure-928-start-year`. The dump remains
   unchanged, and both adjustments appear in the run report.

### Critical findings from analyzing real dump data this session

**Finding 1 — `field_news_content` is the real content field, not
`field_content`.** Early analysis this session incorrectly concluded body
content was missing entirely from the MySQL dumps, because it checked
`node__field_content` (a decoy table with only 4 rows, used solely by an old
deprecated `infrastructure_news` bundle) and `node__body` (unrelated
content types). The actual field is **`node__field_news_content`**, fully
populated for 17/17 `integration_news_v1` nodes and 243/244
`infrastructure_news_v2` nodes. Nid 404 has no current content-field row;
nids 840 and 859 do have nonempty content in the August 28 dump. This was a real analysis mistake,
corrected mid-session — don't re-introduce it.

**Finding 2 — `integration_news_id` is NULL on every current Postgres row.**
Verified precisely against `database/dumps/django.portal1.dump.1788136201.gz`
(a plain-SQL Postgres dump, not custom-format — decompress with `gunzip` and
grep/regex-parse the `COPY portal_django.portal_integrationnews (...) FROM
stdin;` block directly, no live DB connection needed). All 25 current rows
have `integration_news_id = NULL`, **including the 15 rows that do have a
`[drupal_nid:NNN;drupal_vid:MMM]` provenance tag recorded in their
`review_comments` field.** The stable ID was captured as a text comment
during the original import but never written into the real
`integration_news_id` column. Direct consequence: if Part 1's API were
deployed against this database today, every item would return
`"integration_news_id": null`. **The importer's first job is backfilling
this column on the 15 existing rows** (match by extracting the nid from
`review_comments`, same lookup strategy `import_drupal_news.py`'s
`_find_existing_integration()` already uses as its legacy-compatibility
fallback), not just inserting new records.

**Finding 3 — the "25 vs 17" row-count mismatch is fully explained, not a
data-loss risk.** Of the 25 current `IntegrationNews` rows: **15 are real
Drupal-sourced imports** (identifiable by the `drupal_nid` tag in
`review_comments`) covering nids `602, 604, 606, 615, 648, 677, 679, 682,
692, 704, 732, 794, 843, 855, 880` — missing only **949 and 950**, the two
newest Drupal nodes, not yet imported (see Finding 4). **The other 10 rows
are local test/placeholder data** with no Drupal provenance at all —
obviously fake (candy-themed titles like "TWIZZLERS Candy", "candy cyber
infra codev1", gibberish/pig-latin content), mostly `status='draft'` or
`pending_review`. This means a scoped `--replace` would only ever delete
these 10 known-fake rows, not real Drupal history.

**Separate flag, not part of the importer work but worth telling the user:**
one of those 10 local test rows — id=8, "Integration of Candy corn resource
2.9", gibberish content — has `status='published'` with no Drupal
provenance. It's currently live on the public `/integration-news/` page and
would appear in the new API. Probably wants cleanup independent of this task.

**Finding 4 — nodes 949 and 950 are the missing pair, and they're exactly
the ones needing the 2 new `AFFECTED_ELEMENTS` entries.** Verified via
`node__field_affected_intelm`: node 949 references elements `598, 599, 948`;
node 950 references `598, 599, 947`. Both 947 (`accessusage...`) and 948
(`access-oauth-mapfile...`) are real `integration_element` Drupal nodes not
yet in Django's `AFFECTED_ELEMENTS` choices list. Also confirmed both nodes
949/950 are `status=1` (published) in Drupal, so they should appear in the
live API too if that's the eventual source.

### Verified field mapping reference (Drupal MySQL schema → Django model)

Drupal is a Drupal 8/9/10-family site (entity field-table storage, not
Drupal 7's `field_data_*` convention). Content type (bundle) machine names
were deliberately set to match this migration's naming:
`integration_news_v1` (17 nodes) and `infrastructure_news_v2` (244 nodes),
plus a small deprecated leftover `infrastructure_news` (4 nodes, ignore it).

| Django field | Drupal table.column |
|---|---|
| `integration_news_id` | `node_field_data.nid` — the node's own id. **Not** `field_intelm_id` (a table that exists in the schema but has 0 rows — unused/vestigial, don't use it) |
| `title` | `node_field_data.title` |
| `content` | `node__field_news_content.field_news_content_value` |
| `news_type` | `node__field_intelm_news_type.field_intelm_news_type_value` — a display string (e.g. `"Software Release"`) that needs reverse-mapping to the Django choice key (e.g. `"software_release"`) via `IntegrationNews.INTEGRATION_NEWS_TYPES` |
| `effective_date` | `node__field_effective_date.field_effective_date_value` |
| `expiration_date` | `node__field_expiration_date` — table exists, not yet checked whether any of the 17 populate it |
| `affected_elements` (M2M) | `node__field_affected_intelm.field_affected_intelm_target_id` — **multi-value**, one row per `delta` (0, 1, 2...), resolve each target nid against `node_field_data` where `type='integration_element'`, match/create `IntegrationElement` by label |
| (not imported) | `node__field_news_distribution_options.field_news_distribution_options_value` — real data exists per-node, deliberately not imported |
| `status`/`is_active` | `node_field_data.status` (all 17 current nodes are `1`) — draft/pending/approved mapping not yet worked out since no non-published example has been seen |

All 11 `integration_element` Drupal nodes (title, matching `IntegrationElement.label`):
`598` compute, `599` storage, `600` cloud, `601` IPF, `605` online service,
`678` science gateway, `731` nagios, `795` CiDeR, `925` AWS registry,
`947` accessusage (**missing from Django**), `948` access-oauth-mapfile
(**missing from Django**).

### Local analysis technique that worked (reuse it)

Both MySQL and Postgres dumps in `database/dumps/` (gitignored, must be
manually downloaded — no automated pull path for the MySQL/Drupal side exists
in this repo) can be decompressed with `gunzip` and parsed as plain SQL text
with a Python regex script — no live database connection or credentials
required for analysis:

```python
import re
def all_rows(table, sql_text):
    inserts = re.findall(rf"INSERT INTO `{table}`.*?VALUES\s*(.*?);\n", sql_text, re.S)
    # or for Postgres: re.search(r"COPY schema.table \(cols\) FROM stdin;\n(.*?)\n\\\.\n", ...)
    rows = []
    for block in inserts:
        rows.extend(re.findall(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)", block))
    return rows
```

Watch out: MySQL field-table rows are `(bundle, deleted, entity_id,
revision_id, langcode, delta, value...)` — entity_id is at **index 2**, not
index 0. An earlier mistake this session used index 0 and got false "no data"
results.

## Current repo state (uncommitted)

```
 M operations_portalcms_django/integration_news/tests.py
 M operations_portalcms_django/integration_news/urls.py
 M operations_portalcms_django/integration_news/views.py
?? operations_portalcms_django/integration_news/services.py
 M operations_portalcms_django/integration_news/models.py
 M operations_portalcms_django/infrastructure_news/management/commands/import_drupal_news.py
 M operations_portalcms_django/infrastructure_news/test_import_drupal_news.py
 M database/news_import.md
?? operations_portalcms_django/infrastructure_news/drupal_mysql.py
?? operations_portalcms_django/infrastructure_news/test_drupal_mysql.py
```

(`dev_documentation/prod_dev_content_comparison.md` is unrelated pre-existing
untracked work from before this task — don't touch it.)

## Immediate next steps

1. Use the August 31 raw dump with the explicit nid 404 exclusion and named,
   exact-match nid 928 start-year correction documented in
   `database/news_import.md`. Review both adjustments in every run report.
2. Run the Django importer tests with a deliberately nonproduction
   `APP_CONFIG` and disposable PostgreSQL database. Pure parser tests and
   `py_compile` pass locally; DB-backed tests remain pending.
3. Deploy an approved release to beta and follow `database/news_import.md`
   for at least two strict dry-run/apply/verification rehearsals.
4. Consider (separately, needs explicit user sign-off): cleaning up local
   test row id=8, which is incorrectly `status='published'`.
