# Operations Portal CMS

ACCESS Operations Portal Django CMS application for managing & publishing infrastructure, integration, and system status information.

Current state is tracked in [READMEs/CURRENT_STATE.md](READMEs/CURRENT_STATE.md). As of the latest verification pass on 2026-04-24 13:30 UTC, the database of record is Amazon RDS `portal1`, reached through `/soft/django-cms-01/conf/portal.conf.dev.json`.

## Features

- Django CMS 5 with Bootstrap 5
- django CMS page versioning for focus-area draft/publish workflow
- CILogon OAuth2 authentication with automatic group sync
- **Resource Provider Permissions** - Fine-grained access control based on COmanage groups
- Integration News & System Status News management
- CIDER integration for infrastructure, organizations, and RP groups
- Resource allocation information
- Focus area pages (Cybersecurity, Networking, Operational Support, STEP)
- FAQ pages with accordion UI
- Responsive design with ACCESS branding

## Project Structure

```
Operations_PortalCMS_Django/
├── operations_portalcms_django/  # Main Django application
│   ├── settings.py               # Django settings
│   ├── urls.py                   # URL routing
│   ├── views.py                  # View controllers
│   ├── models.py                 # Database models
│   └── management/               # Custom management commands
├── templates/                    # HTML templates
│   ├── base.html                 # Base template
│   ├── operations_portalcms_django/  # App templates
│   └── ...
├── static/                       # Static files (CSS, JS, images)
├── media/                        # User-uploaded files
├── database/                     # Backup, restore, clone, and DB verification scripts
├── READMEs/                      # Operational and workflow documentation
├── tests/                        # Standalone integration/check scripts
├── manage.py                     # Django management script
├── pyproject.toml                # Python dependencies
├── portal.service.j2             # Systemd service template
├── manage.prod.sh.j2             # Manual manage.py wrapper template
└── nginx-portal.conf             # Nginx configuration example
```

## Technology Stack

- **Python:** >=3.12,<3.13
- **Framework:** Django >=5.2,<5.3
- **CMS:** django CMS >=5.0,<5.1 with djangocms-versioning
- **Frontend:** Bootstrap 5.3, ACCESS UI Components
- **Database:** PostgreSQL on Amazon RDS (`portal1`)
- **Authentication:** django-allauth with CILogon
- **WSGI Server:** Gunicorn
- **Web Server:** nginx
- **Package Manager:** uv
- **Runtime Config:** required `APP_CONFIG` JSON file

## Documentation

**Current State:**
- **[CURRENT_STATE.md](READMEs/CURRENT_STATE.md)** - Latest verified runtime, database, content, permission, and check results
- **[APP_CONFIG_CONTRACT.md](READMEs/APP_CONFIG_CONTRACT.md)** - Runtime config contract
- **[database_migration_plan.md](READMEs/database_migration_plan.md)** - RDS cutover status and rollback notes

**Getting Started:**
- **[developer_Steps.md](developer_Steps.md)** - Local developer setup with `uv` and a restored `portal1` backup
- **[SETUP_GUIDE.md](READMEs/SETUP_GUIDE.md)** - Complete setup guide for all workflows
- **[WORKFLOW_TESTING.md](READMEs/WORKFLOW_TESTING.md)** - Testing guide for all workflows (automated + manual)

**Workflow Systems:**
- **[NEWS_PERMISSIONS.md](READMEs/NEWS_PERMISSIONS.md)** - News workflow (draft/review/publish)
- **[FOCUS_AREA_WORKFLOW.md](READMEs/FOCUS_AREA_WORKFLOW.md)** - Focus area page workflow
- **[CMS_VERSIONING_CLONE_CHECKLIST.md](READMEs/CMS_VERSIONING_CLONE_CHECKLIST.md)** - Command-by-command clone-first versioning rollout
- **[CMS_VERSIONING_ROLLOUT_PLAN.md](READMEs/CMS_VERSIONING_ROLLOUT_PLAN.md)** - Current rollout status, clone findings, and next steps
- **[FOCUS_AREA_WORKFLOW_IMPLEMENTATION_NOTES.md](READMEs/FOCUS_AREA_WORKFLOW_IMPLEMENTATION_NOTES.md)** - Implementation context and decisions
- **[PERMISSIONS_SUMMARY.md](READMEs/PERMISSIONS_SUMMARY.md)** - Overview of all permission systems

**Technical Details:**
- **[CMS_PAGE_PERMISSIONS.md](READMEs/CMS_PAGE_PERMISSIONS.md)** - Django CMS page permissions
- **[QUICKSTART_PERMISSIONS.md](READMEs/QUICKSTART_PERMISSIONS.md)** - RP permissions setup
- **[PERMISSIONS.md](READMEs/PERMISSIONS.md)** - Implementation details
- **[SECURITY_HARDENING.md](READMEs/SECURITY_HARDENING.md)** - Future production/staging security hardening notes

**Database:**
- **[database/README.md](database/README.md)** - Database verification, backup, restore, and clone helper scripts
- **[database/dumps/README.md](database/dumps/README.md)** - Historical committed dump notes and current dump policy

## Common Verification

Use the deployed config when checking the database of record:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
APP_LOG=/tmp/portal-check.log \
APP_ERROR_LOG=/tmp/portal-check.error.log \
uv run python manage.py check
```

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/verify_db.sh
```

## Development Guidelines

- Python code style: Follow Django conventions
- Templates: Use Bootstrap 5 classes
- CSS: Extend `static/operations_portalcms_django/style-portal.css`
- Avoid running the standalone scripts in `tests/` against RDS `portal1` unless you intend to create or modify test users/groups/content there.

---

Original Django server produced by Claude 4.5 Sonnet with assistance from ChatGPT Codex 5.2 & 5.3.
