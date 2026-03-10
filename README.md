# Operations Django-CMS DEV DEMO code

ACCESS Operations Portal Django CMS application for managing & publishing infrastructure, integration, and system status information.

## Features

- Django CMS 5 with Bootstrap 5
- CILogon OAuth2 authentication
- Integration News & System Status News management
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
- **Database:** PostgreSQL
- **Authentication:** django-allauth with CILogon
- **WSGI Server:** Gunicorn
- **Web Server:** nginx
- **Package Manager:** uv

## Development Guidelines

- Python code style: Follow Django conventions
- Templates: Use Bootstrap 5 classes
- CSS: Extend `static/operations_portalcms_django/style-portalcms.css`

---

Original Django server produced by Claude 4.5 Sonnet
