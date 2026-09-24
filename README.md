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
├── operations_portalcms_django/      # Django project root
│   ├── manage.py                      # Django management entry point
│   ├── operations_portalcms_django/  # Settings, root URLs, ASGI, and WSGI
│   ├── portal/                       # Core CMS, authentication, permissions, and health checks
│   ├── infrastructure_news/          # System Status News and Drupal import workflow
│   ├── integration_news/             # Integration News models and publishing workflow
│   ├── resources/                    # CIDER-backed resource models and views
│   ├── templates/                    # Site, account, admin, portal, and web templates
│   ├── static/                       # Source CSS, JavaScript, and images
│   ├── media/                        # django-filer media used by the application
│   └── tests/                        # Cross-app integration and configuration tests
├── database/                     # Database/media backup, restore, retrieval, and verification tools
├── dev_documentation/            # Current-state and development documentation
├── media_documentation/          # django CMS media documentation
├── .github/                      # CI and deployment workflow definitions
├── AGENTS.md                     # Repository-specific agent guidance
├── CHANGELOG                     # Project change history
└── README.md                     # This project overview
```

For the supported local development environment, use the
[Operations_Django_Development](https://github.com/access-ci-org/Operations_Django_Development)
repository. Runtime and deployment configuration is maintained separately and is not
part of this source tree.

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
