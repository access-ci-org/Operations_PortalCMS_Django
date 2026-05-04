# Django Structure Analysis — Current State

**Projects compared:**
- `Operations_PortalCMS_Django` (this repo) — Django 5.2 + django-CMS 5
- `Operations_ServiceIndex_Django` — Django 5.0, internal service catalog

**Status date:** May 4, 2026

**Note on `access_django_user_admin`:** This package appears embedded as a development clone in the ServiceIndex repo (has its own `.git/`, `LICENSE`, `requirements.txt`). That is intentional for local dev iteration. PortalCMS installs it correctly as a versioned dependency (`access-django-user-admin==1.5.3` in `pyproject.toml`); ServiceIndex should eventually do the same for production releases.

---

## Executive Summary

PortalCMS has now been restructured to match the manager feedback captured in the prior analysis:

1. `manage.py` now lives inside the Django project directory at `portal/manage.py`.
2. The project config package is now separate at `portal/config/`.
3. The application package is now app-only at `portal/operations_portalcms_django/`.
4. App routes now live in `portal/operations_portalcms_django/urls.py`; the old `app_urls.py` workaround is gone.
5. Runtime entry points now point to `config.settings`, `config.urls`, and `config.wsgi`.

The main structural issue is now cleanup, not application layout: there are legacy root-level artifact directories left from the previous layout (`operations_portalcms_django/` containing only `__pycache__` trees, plus root-level `static/`, `templates/`, and `staticfiles/` artifacts). They are not part of the active Django import path when running from `portal/`, but they create visual noise and should be removed or ignored after confirming they are not needed.

---

## Manager Feedback — Resolved for PortalCMS

A manager review previously identified two structural issues with PortalCMS:

> "manage.py isn't working because you moved the script from the default/convention in the Django project directory to the parent directory. The Django convention is that manage.py is inside the Django project directory. Another, perhaps more fundamental issue is that the Django project directory doesn't follow the normal Django convention for base directories with module sub-directories."

Both issues are now addressed.

**On `manage.py` location:** The [Django 5.2 tutorial](https://docs.djangoproject.com/en/5.2/intro/tutorial01/) scaffolds a project container containing a Django project directory, and `manage.py` lives inside that project directory:

```
djangotutorial/     ← project container / repo root equivalent
    manage.py       ← inside the Django project directory
    mysite/         ← config package
        settings.py
        urls.py
        ...
```

PortalCMS now mirrors that pattern with `Operations_PortalCMS_Django/` as the repo container and `portal/` as the Django project directory.

**On project package structure:** The project config package (`config/`) is now separate from the app package (`operations_portalcms_django/`). That resolves the previous conflation where one package held both config files (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`) and app files (`models.py`, `views.py`, `forms.py`, `admin.py`, etc.).

---

## 1. Top-Level Directory Layout

### Django Convention

```
repo-root/
├── pyproject.toml             ← dependency file
├── .venv/                     ← virtual environment, if kept in repo root
└── project-dir/               ← Django project directory
    ├── manage.py              ← project entry point
    ├── config/                ← project config package
    │   ├── __init__.py
    │   ├── settings.py
    │   ├── urls.py
    │   ├── wsgi.py
    │   └── asgi.py
    ├── myapp/                 ← reusable/local app package
    │   ├── models.py
    │   ├── views.py
    │   └── ...
    ├── templates/             ← project-wide templates
    ├── static/                ← project-wide source static assets
    ├── media/                 ← uploaded media
    └── tests/                 ← project tests, or tests can live inside each app
```

Key principle: the **project config package** (settings, urls, wsgi, asgi) is separate from **application packages** (models, views, forms). `manage.py` lives in the Django project directory, not in the config package.

### PortalCMS Actual Layout

```
Operations_PortalCMS_Django/           ← repo root / outer container ✅
├── pyproject.toml                     ← single dependency file ✅
├── uv.lock                            ← locked environment ✅
├── portal.conf.dev.json               ← local runtime config sample/dev config
├── portal.local.example.json          ← example runtime config
├── manage.prod.sh.j2                  ← deployment helper, points into portal/ ✅
├── portal.service.j2                  ← systemd unit, WorkingDirectory is portal/ ✅
├── nginx-portal.conf                  ← nginx deployment config
├── database/                          ← database scripts and media backups
├── READMEs/                           ← project documentation
├── portal/                            ← Django project directory ✅
│   ├── manage.py                      ← correct location ✅
│   ├── config/                        ← project config package only ✅
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── operations_portalcms_django/   ← app package only ✅
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── forms.py
│   │   ├── admin.py
│   │   ├── signals.py
│   │   ├── workflow.py
│   │   ├── utils.py
│   │   ├── urls.py                    ← app routes ✅
│   │   ├── apps.py
│   │   ├── cms_plugins.py
│   │   ├── cms_toolbars.py
│   │   ├── management/commands/       ← correct app command location ✅
│   │   ├── migrations/                ← correct app migration location ✅
│   │   └── templatetags/              ← correct app tag location ✅
│   ├── templates/                     ← active project templates ✅
│   ├── static/                        ← active source static assets ✅
│   ├── media/                         ← active media root ✅
│   └── tests/                         ← project test suite ⚠️ acceptable, but app-local tests would be tighter
├── operations_portalcms_django/       ← stale bytecode-only artifact directory ⚠️ cleanup candidate
├── static/                            ← stale/root artifact directory ⚠️ cleanup candidate
├── staticfiles/                       ← stale/root collected static artifacts ⚠️ cleanup candidate
└── templates/                         ← stale/root artifact directory ⚠️ cleanup candidate
```

**Primary findings:**
1. The prior structural debt has been resolved: `portal/` is now the Django project directory, `portal/config/` is config-only, and `portal/operations_portalcms_django/` is app-only.
2. Deployment helpers have been updated to the new structure: `manage.prod.sh.j2` runs from `portal/`, and `portal.service.j2` uses `WorkingDirectory={{ app_home }}/PROD/portal` with `gunicorn config.wsgi:application`.
3. Cleanup remains: root-level artifact directories from the old layout should be removed once confirmed unnecessary. The root `operations_portalcms_django/` currently contains only `__pycache__` files and empty support directories.

### ServiceIndex Actual Layout

```
service-index-uv-sand/
└── Operations_ServiceIndex_Django/    ← repo root
    └── Operations_ServiceIndex_Django/ ← Django project directory
        ├── manage.py                  ← correct relative to Django project root ✅
        ├── Operations_ServiceIndex_Django/  ← project config package
        │   ├── settings.py
        │   ├── urls.py
        │   ├── wsgi.py
        │   ├── asgi.py
        │   └── views.py               ← favicon view in project config package ❌
        ├── services/                  ← proper app package ✅
        │   ├── models.py
        │   ├── views.py
        │   ├── forms.py (missing)
        │   ├── admin.py
        │   ├── signals.py
        │   ├── serializers.py         ← good separation ✅
        │   ├── context_processors.py  ← good separation ✅
        │   ├── urls.py
        │   ├── templatetags/
        │   ├── static/
        │   ├── migrations/
        │   └── tests.py               ← stub only
        ├── access_django_user_admin/  ← dev clone (has own .git/)
        └── templates/
```

**Primary finding:** The triple same-name nesting is cognitively confusing but structurally valid: the outer folder is the repo container, the middle folder is the Django project directory, and the innermost folder is the config package. The issue is naming clarity, not Django structure.

---

## 2. `manage.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | Inside Django project directory | ✅ `portal/manage.py` | ✅ Inside middle `Operations_ServiceIndex_Django/` |
| `DJANGO_SETTINGS_MODULE` | Points to config package | ✅ `config.settings` | ✅ `Operations_ServiceIndex_Django.settings` |
| Boilerplate | Standard Django scaffold | ✅ Clean | ✅ Clean |

---

## 3. `settings.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | Config package | ✅ `portal/config/settings.py` | ✅ Dedicated config package |
| Secret key | Never hardcoded; from env/secrets | ✅ From `APP_CONFIG` JSON | ✅ From `APP_CONFIG` JSON |
| `DEBUG` default | `False` for safety | ✅ `_bool_value(CONF.get('DEBUG'), False)` | ❌ `CONF["DEBUG"]` — `KeyError` if key absent, no default |
| `ALLOWED_HOSTS` | Explicit list; never `['*']` in prod | ⚠️ Falls back to `[]` if env var absent after config load | ❌ `CONF["ALLOWED_HOSTS"]` — `KeyError` if key absent |
| Required key validation | Explicit contract | ✅ `required_config_keys` list with clear error messages | ❌ No validation; runtime `KeyError` on first access |
| Type coercion | Validated booleans/lists | ✅ `_bool_value()` and `_env_bool()` helpers | ❌ Raw dict access; `DEBUG` must be an actual bool in JSON |
| `INSTALLED_APPS` order | Third-party before local; admin style first if used | ✅ Correct; `djangocms_admin_style` first | ✅ Correct |
| Database config | All credentials from env/secrets | ✅ Via env vars populated from `APP_CONFIG` | ⚠️ Direct `CONF[]` dict access; read/write DB split is a nice addition |
| SSL/DB options | Configurable | ✅ `DB_SSLMODE`, `DB_SSLROOTCERT`, etc. | ❌ Not present |
| `SECRET_KEY` | From config, not hardcoded | ✅ | ✅ |
| `CONN_MAX_AGE` | Should be set for persistent connections | ⚠️ Not currently set | ✅ `600` |
| Paths | Resolve from project directory | ✅ `BASE_DIR = portal/`; templates/static/media resolve under `portal/` | ✅ |

---

## 4. `urls.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | Config package | ✅ `portal/config/urls.py` | ✅ `Operations_ServiceIndex_Django/urls.py` |
| App URL separation | `include()` with namespaced app `urls.py` | ✅ `include('operations_portalcms_django.urls')` | ✅ `include('services.urls', namespace='services')` |
| Catch-all last | CMS/wildcard routes at end | ✅ `cms.urls` is last | ✅ `RedirectView` is last |
| Dead imports | No unused imports | ✅ Clean | ❌ `from access_django_user_admin import views` then immediately shadowed by `from . import views` |
| `re_path` vs `path` | Prefer `path()` with converters | ✅ Uses `path()` | ⚠️ Several `re_path(r'^edit/(?P<id>\d+)$')` that could be `path('edit/<int:id>')` |

---

## 5. `models.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| `default_auto_field` | Set in `AppConfig` or `settings.py` | ✅ `BigAutoField` in `apps.py` and `settings.py` | ✅ `BigAutoField` in `apps.py` (services) |
| `__str__` methods | All models should define one | ✅ Consistent | ✅ All have `__str__` (and legacy `__unicode__`) |
| Explicit `verbose_name` | Recommended for readability | ✅ Thorough | ⚠️ Not used; relies on Django's auto-generated names |
| `Meta` class | Order, verbose names, permissions | ✅ Custom permissions for workflow | ⚠️ Minimal or absent |
| Choices as class attributes or `TextChoices` | Prefer `TextChoices` or `IntegerChoices` | ⚠️ Uses plain list-of-tuples | ⚠️ Uses plain list-of-tuples |
| Wildcard import in views | `from .models import *` is discouraged | ✅ Explicit imports | ❌ `from services.models import *` in `views.py` and `admin.py` |
| Business logic separation | Heavy logic → service layer or signals; not in models | ✅ Workflow in `workflow.py` | ⚠️ Some logic in views directly |

---

## 6. `views.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Auth enforcement | `@login_required` or `LoginRequiredMixin` | ✅ Consistently applied | ❌ Decorators commented out on `index` and `add_service` |
| Permission checks | `has_perm()` or `permission_required` | ✅ `has_perm()` and workflow checks | ❌ `editors_check(user)` group check only; `is_privileged()` hardcodes `username == 'navarro'` |
| Import hygiene | Explicit imports only | ✅ | ❌ `from services.models import *` |
| Function-based vs class-based | Either fine; CBVs preferred for CRUD | ✅ FBVs consistent | ✅ FBVs consistent |
| Views in config package | Views belong in apps only | ✅ App views live in `portal/operations_portalcms_django/views.py` | ❌ `favicon` view in `Operations_ServiceIndex_Django/views.py` |
| Query optimization | `select_related`, `prefetch_related` | ✅ Used consistently | ⚠️ `Service.objects.order_by('name')` in loop with `s.host_set.all()` — N+1 risk |

---

## 7. `admin.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Registration style | `@admin.register()` decorator preferred | ✅ Uses `@admin.register()` | ❌ Uses `admin.site.register()` (older style) |
| Wildcard import | Explicit model imports | ✅ | ❌ `from services.models import *` |
| `list_display`, `search_fields` | Should be defined | ✅ Thorough fieldsets | ✅ Present but minimal |
| `readonly_fields` for auto fields | `auto_now_add` fields should be readonly | ✅ `created_at`, `updated_at` readonly | ⚠️ Not set |
| Custom `save_model` | Attach request.user on create | ✅ | ❌ Not present |

---

## 8. `signals.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | In app; connected via `apps.py ready()` | ✅ Connected in `apps.py.ready()` | ⚠️ Imported directly in `views.py` (`import services.signals`) — fragile |
| `@receiver` decorator | Preferred over manual `connect()` | ✅ | ✅ |
| Bare `except:` | Should catch specific exceptions | — | ❌ `except:` with no type in `set_username` |

---

## 9. `wsgi.py` / `asgi.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | Config package | ✅ `portal/config/wsgi.py`, `portal/config/asgi.py` | ✅ Dedicated config package |
| `DJANGO_SETTINGS_MODULE` | Must match config package path | ✅ `config.settings` | ✅ Matches |
| Module docstrings | Reference correct project name | ✅ `Operations Portal CMS` | ✅ |

---

## 10. `apps.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| `default_auto_field` | Set here or in `settings.py`; avoids warnings | ✅ `BigAutoField` | ✅ `BigAutoField` (services) |
| `ready()` for signal/toolbar init | Use `ready()` to import signals | ✅ Imports signals and CMS toolbars | ❌ `ServicesConfig` has no `ready()`; signals connected via view import |
| `verbose_name` | Human-readable name for admin | ✅ `'Operations Portal CMS'` | ❌ Not set |

---

## 11. Migrations

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | `app/migrations/` | ✅ `portal/operations_portalcms_django/migrations/` | ✅ |
| Squashing | Periodic squashing keeps history manageable | ⚠️ 17 migrations, not yet squashed | ✅ `0001_squashed_0004_...` present |
| Committed to version control | Yes | ✅ | ✅ |

---

## 12. Templates

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Project-wide base templates | `project-dir/templates/` | ✅ `portal/templates/base.html`, `page.html`, etc. | ✅ `templates/` present |
| App templates | `templates/appname/` namespacing | ✅ `portal/templates/operations_portalcms_django/` | ✅ `templates/services/` |
| `APP_DIRS = True` | Lets Django find app templates | ✅ | ✅ |
| Root leftovers | Avoid duplicate inactive template roots | ⚠️ Root `templates/` appears to contain only `.DS_Store` artifacts | — |

---

## 13. Static Files

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Source static | `project-dir/static/appname/` namespacing | ✅ `portal/static/operations_portalcms_django/` | ✅ `services/static/` |
| `STATICFILES_DIRS` vs `STATIC_ROOT` | Separate source dirs from collected output | ✅ `STATICFILES_DIRS = [BASE_DIR / 'static']`; `STATIC_ROOT = BASE_DIR / 'staticfiles'` by default | ✅ |
| Serving in development | `urlpatterns += static(...)` in DEBUG | ✅ | ✅ |
| Root leftovers | Avoid duplicate inactive static roots | ⚠️ Root `static/` and `staticfiles/` remain from the old layout | — |

---

## 14. Dependency Management

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Single dependency file at repo root | `pyproject.toml` (modern) or `requirements.txt` | ✅ `pyproject.toml` with pinned ranges | ❌ No project-level file; `access_django_user_admin/requirements.txt` only |
| Lockfile | Commit lockfile for reproducible app deploys | ✅ `uv.lock` | — |
| Version pinning | Use ranges (`>=x,<y`) where practical | ✅ | N/A |
| Virtual environment | `.venv` at repo root | ✅ `.venv/` | ✅ `.venv/` (in outer repo) |

---

## 15. Tests

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | `app/tests/` or project-level `tests/` inside project dir | ✅ `portal/tests/` | ❌ `services/tests.py` is an empty stub |
| Test isolation | Each app's tests in its own directory for reusable apps | ⚠️ Project-level tests are acceptable, but app-local tests would better encapsulate app behavior | ❌ No real tests |
| Test runner config | `pyproject.toml` or `setup.cfg` | ❌ Not configured | ❌ Not configured |

---

## Summary Scorecard

| Category | PortalCMS | ServiceIndex |
|---|---|---|
| Directory layout / project vs app separation | ✅ `portal/` project dir, `config/` config package, app package separated | ⚠️ Correct layout, but triple same-name nesting is confusing |
| `manage.py` | ✅ `portal/manage.py` | ✅ Inside project directory |
| `settings.py` (config safety) | ✅ Strong | ❌ Fragile (raw dict, no defaults) |
| `urls.py` | ✅ Config/app URLs separated cleanly | ⚠️ Dead import, `re_path` overuse |
| `models.py` | ✅ | ⚠️ Wildcard imports, no `verbose_name` |
| `views.py` | ✅ | ❌ Auth decorators disabled, hardcoded authz, wildcard imports |
| `admin.py` | ✅ | ⚠️ Old registration style, wildcard imports |
| `signals.py` connection | ✅ via `ready()` | ❌ via view import |
| `wsgi.py` / `asgi.py` | ✅ Current docstrings and `config.settings` | ✅ |
| `apps.py` | ✅ | ⚠️ No `ready()`, no `verbose_name` |
| Migrations | ✅ | ✅ |
| Templates | ✅ Active templates under `portal/`; root leftovers need cleanup | ✅ |
| Static files | ✅ Active static under `portal/`; root leftovers need cleanup | ✅ |
| Dependency management | ✅ | ❌ No project-level file |
| Tests | ⚠️ Present under `portal/tests/`; no runner config | ❌ Stub only |

---

## Priority Recommendations

### PortalCMS

1. **Clean up old root artifacts** — Remove stale root-level `operations_portalcms_django/` bytecode directories and inactive root `static/`, `templates/`, and `staticfiles/` artifacts after confirming no deployment process still depends on them.
2. **Add test runner config** — Add a `pytest`/Django test configuration or document the canonical `uv run python portal/manage.py test` command.
3. **Consider app-local tests** — `portal/tests/` is valid for project integration tests, but app behavior would be better encapsulated in `portal/operations_portalcms_django/tests/` if this app is expected to stay reusable.
4. **Set `CONN_MAX_AGE`** — Add persistent DB connection tuning if this deployment benefits from it.
5. **Consider migration squashing later** — The app currently has 17 migrations. That is not urgent, but squashing can reduce setup noise once the schema stabilizes.

### ServiceIndex

1. **Re-enable auth decorators** — `@login_required` and `@user_passes_test` are commented out on `index` and `add_service`.
2. **Remove hardcoded authorization** — `is_privileged()` checking `username == 'navarro'` must go; use group membership, permissions, or `is_staff`.
3. **Fix `settings.py`** — Add required key validation, default for `DEBUG`, and type coercion for booleans.
4. **Fix `urls.py`** — Remove the shadowed `access_django_user_admin` import.
5. **Add `pyproject.toml`** at project root with proper dependencies.
6. **Connect signals via `ready()`** — Move `import services.signals` from `views.py` into `ServicesConfig.ready()`.
7. **Replace wildcard imports** — `from services.models import *` → explicit imports in `views.py` and `admin.py`.
8. **Rename triple-nested directories if feasible** — The structure is valid, but the identical names make path discussion and operational work harder than necessary.

---

## PortalCMS Current Runtime Contract

Run Django management commands from the Django project directory:

```bash
cd portal
uv run python manage.py check
uv run python manage.py test
```

Runtime settings:

```python
DJANGO_SETTINGS_MODULE = "config.settings"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
BASE_DIR = Path(__file__).resolve().parent.parent  # portal/
```

Deployment templates match this structure:

- `manage.prod.sh.j2` changes into `$APP_DJANGO/portal` and runs `uv run python manage.py`.
- `portal.service.j2` uses `WorkingDirectory={{ app_home }}/PROD/portal`.
- Gunicorn starts `config.wsgi:application`.

