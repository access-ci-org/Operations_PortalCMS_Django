# Operations Django-CMS DEV DEMO code

ACCESS Operations Portal Django CMS application for managing & publishing infrastructure, integration, and system status information.

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
├── manage.py                     # Django management script
├── pyproject.toml                # Python dependencies
├── DEPLOYMENT.md                 # Production deployment guide
├── QUICKREF.md                   # Quick reference for operations
└── nginx-portalcms.conf         # Nginx configuration example
```

## Technology Stack

- **Framework:** Django 5.2
- **CMS:** Django CMS 5.0
- **Frontend:** Bootstrap 5.3, ACCESS UI Components
- **Database:** PostgreSQL 15
- **Authentication:** django-allauth with CILogon
- **WSGI Server:** Gunicorn
- **Web Server:** nginx
- **Package Manager:** uv

## Documentation

**Getting Started:**
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

**Other:**
- DEPLOYMENT.md - Development setup and production deployment (coming soon)
- QUICKREF.md - Quick reference for common operations (coming soon)

## Development Guidelines

- Python code style: Follow Django conventions
- Templates: Use Bootstrap 5 classes
- CSS: Extend `static/operations_portalcms_django/style-portalcms.css`

---

Original Django server produced by Claude 4.5 Sonnet with assistance from ChatCPT Codex 5.2 & 5.3.
