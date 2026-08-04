# Operations Portal CMS Work in Progress

ACCESS Operations Portal Django CMS application for managing & publishing infrastructure, integration, and system status information.

See [dev_documentation/CURRENT_STATE.md](dev_documentation/CURRENT_STATE.md) for the current operational state, setup commands, permissions reference, and security notes.

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
├── operations_portalcms_django/      # Django project root (manage.py here)
│   ├── operations_portalcms_django/  # Settings package (settings.py, urls.py, wsgi.py)
│   ├── portal/                       # Core app: views, toolbars, CMS workflow, utils
│   ├── infrastructure_news/          # System Status News models, views, admin
│   ├── integration_news/             # Integration News models, views, admin
│   ├── resources/                    # CIDER models and public resource views
│   ├── templates/                    # HTML templates (base.html, portal/, web/, etc.)
│   ├── static/                       # Static files (CSS, JS, images)
│   ├── media/                        # User-uploaded files
│   ├── tests/                        # Standalone integration/check scripts
│   └── manage.py
├── database/                         # Backup, restore, clone, and DB verification scripts
├── dev_documentation/                # Operational docs and local dev config example (see CURRENT_STATE.md) (these files can be copied into the root dir to run locally for development or, preferreed, one should use the [Operations_Django_Development](https://github.com/access-ci-org/Operations_Django_Development) repo)
├── manage.py                     # Django management script
└── pyproject.toml                # Python dependencies
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

## Deployment readiness contract

`GET /healthz/` returns the configured `APP_VERSION` and performs a lightweight
query against the default database. It returns HTTP 200 with `status: ok` only
when the database is usable, otherwise HTTP 503 without exposing exception
details. Production infrastructure restricts this route to loopback and uses it
after activating a prepared release.

For non-debug deployments, startup validates the required database, hostname,
static/media, API, OAuth, version, and secret-bearing configuration keys and
their JSON types. Deployment configuration remains owned by
`Operations_CMS_Infrastructure`.


---

Original Django server produced by Claude 4.5 & Claude 4.6, Sonnet with assistance from ChatGPT Codex 5.2 & 5.3.
