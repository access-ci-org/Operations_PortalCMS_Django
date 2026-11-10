# Future Code Cleanup Plan

## Purpose

Use this plan to identify small, safe improvements that make the Django codebase
easier to read and maintain. The goal is behavior-preserving cleanup, not a broad
rewrite. Each recommendation should explain what would change, why it is clearer,
what behavior must remain the same, and how that behavior can be checked.

This is a planning note only. It does not authorize code changes, deletion or
archival of commands, migrations, dependency changes, or deployment work.

## Scope boundary

The public news APIs and their payloads, routes, caching, and external consumers
are out of scope for this cleanup review. The external script that consumes the
news API needs attention first. Do not inspect or propose cleanup to those API
areas in this pass. Revisit them only after that work is complete and the API
contract has been reviewed with its consumer.

Keep authentication, authorization, CMS publishing/versioning, database schema,
and CIDER data contracts unchanged during any future readability work. Treat a
proposed change in one of those areas as a separate, explicitly reviewed task.

## Candidate areas for a later read-only review

These are review areas, not findings that code must change:

1. **Infrastructure and integration news workflows**
   - Compare their non-API forms, create/edit views, admin behavior, and
     publish/unpublish workflows.
   - Identify repeated code that can be made clearer without hiding
     feed-specific rules or permission checks.
   - Keep the different fields, permissions, and user-visible messages explicit.
     Do not introduce a shared abstraction solely to reduce line count.

2. **Drupal import tooling lifecycle**
   - Map the canonical `import_drupal_news` command, its parser, tests, docs,
     and the portal compatibility entry point.
   - Establish whether the one-time cutover is complete and whether operators,
     recovery procedures, CI, or other repositories still depend on the command.
   - Preserve the importer's validation and replacement safeguards while it is
     supported. Decide later whether to retain it, deprecate it, archive its
     source outside runtime command discovery, or remove it in a separately
     approved change.
   - Do not delete it based only on the fact that the initial import completed.

3. **CIDER and other management commands**
   - Review command argument names, dry-run and write behavior, error messages,
     and separation between development-only data loaders and operational syncs.
   - Preserve destructive-action safeguards and make operator expectations easy
     to find in the command help and documentation.

4. **Shared portal and resource code**
   - Look for confusing names, stale comments, duplicated transformations, and
     functions with multiple responsibilities.
   - Confirm ownership and data-source boundaries before suggesting simplification.

5. **Documentation and tests**
   - Find places where docs no longer match command behavior or the current
     application structure.
   - Identify tests that protect important non-API behavior and note gaps before
     proposing refactors. Do not weaken or remove tests merely to simplify code.

## Review and implementation sequence

1. Confirm the branch, commit, and complete working-tree state; preserve all
   existing user work.
2. Build a behavior map for the selected area and identify its owners and
   dependencies. For importer retirement, include a human check of operational
   procedures and any dependent repositories before making a recommendation.
3. Record candidates with file paths, current behavior, proposed simplification,
   risk, and the smallest relevant validation.
4. Rank candidates as low, medium, or high risk. Start with isolated readability
   changes; keep authorization, CMS versioning, persistence, and data replacement
   changes out of ordinary cleanup patches.
5. After separate approval, make one focused change at a time and review the full
   diff. Run only permitted checks with a deliberately nonproduction config.
6. Report files changed, checks and results, skipped checks, assumptions, and
   unresolved risks. Do not commit, push, merge, tag, release, or deploy without
   separate authorization.

## Importer retirement decision gates

Before archiving or removing the Drupal importer, establish all of the following:

- The production cutover is complete and verified by the responsible humans.
- No current workflow, operator runbook, recovery procedure, CI job, or dependent
  repository invokes the command or imports its parser.
- Required source dumps, normalized data, reviewed plans, reports, and recovery
  records are retained under the organization's data-handling rules.
- The compatibility command entry point is understood and no longer needed.
- The proposed archive or removal has an owner and an approved recovery path.

If any item is uncertain, leave the command in place and document the uncertainty.

## Explicitly deferred

- Public news API routes, response fields, serialization, caching, and compatibility
  behavior.
- The external script that consumes the news API.
- API-related tests or cleanup proposals until the consumer work is addressed.
- Any code edits, command removal, archive operation, migration, production data
  access, or deployment as part of this planning note.
