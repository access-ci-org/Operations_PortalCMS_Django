# Django Structure Analysis — Current State

**Projects compared:**
- `Operations_PortalCMS_Django` (this repo) — Django 5.2 + django-CMS 5
- `Operations_ServiceIndex_Django` — Django 5.0, internal service catalog

**Status date:** May 8, 2026 (app split completed)

**Note on `access_django_user_admin`:** This package appears embedded as a development clone in the ServiceIndex repo (has its own `.git/`, `LICENSE`, `requirements.txt`). That is intentional for local dev iteration. PortalCMS installs it correctly as a versioned dependency (`access-django-user-admin==1.5.3` in `pyproject.toml`); ServiceIndex should eventually do the same for production releases.

---

## Executive Summary

PortalCMS has been fully restructured to match the vanilla `djangocms <project>` convention, incorporating manager feedback from May 2026, and subsequently split into 4 Django apps (May 8, 2026):

1. Level 2 Django project directory renamed: `portal/` → `operations_portalcms_django/`.
2. Level 3 config package renamed: `config/` → `operations_portalcms_django/` (matching Level 2 per Django CMS default).
3. App package renamed: `operations_portalcms_django/` → `portal/` (freed the name for Level 3, short and unambiguous).
4. All runtime entry points updated: `DJANGO_SETTINGS_MODULE = 'operations_portalcms_django.settings'`, `ROOT_URLCONF = 'operations_portalcms_django.urls'`, `WSGI_APPLICATION = 'operations_portalcms_django.wsgi.application'`.
5. Deployment templates updated: `manage.prod.sh.j2`, `portal.service.j2`, and `nginx-portal.conf` all point to `operations_portalcms_django/`.
6. `django manage.py check` passes clean (0 issues) after restructure.
7. **App split (May 8, 2026):** All 9 models and their supporting code were moved out of `portal` into 3 new feature apps: `resources`, `infrastructure_news`, `integration_news`. No DDL was required (all models retained their original `db_table` values). The `portal` app is now the core app: unprivileged view, CMS versioning workflow views, shared utils, and CMS toolbars.

**DB migration note:** The production `django_migrations` table was updated on May 4, 2026 (`UPDATE django_migrations SET app = 'portal' WHERE app = 'operations_portalcms_django';`). When restoring a **pre-May 4, 2026 backup** to a new environment, run this SQL after restore and before `migrate`.

---

## Manager Feedback — Resolved for PortalCMS

A May 2026 manager review (Slack) identified that the structure did not yet match the vanilla `djangocms <project>` convention:

> "You could/should have level 2 AND level 3 as `operations_portalcms_django/` instead of level 2 `portal/` and level 3 `operations_portalcms_django/`. What you have in `config/` is by default when creating a django project under the level 3 `operations_portalcms_django/` (project name)."

The vanilla `djangocms myproject` output places Level 2 and Level 3 under the same name:

```
myproject/              ← Level 2: Django project directory
    manage.py
    myproject/          ← Level 3: config package (same name as Level 2)
        __init__.py
        settings.py
        urls.py
        wsgi.py
        asgi.py
        static/
        templates/
    requirements.in
```

All three issues (Level 2 name, Level 3 name, app package naming conflict) are now resolved.

---

## 1. Top-Level Directory Layout

### Django CMS Convention (vanilla `djangocms <project>`)

```
repo-root/                     ← Level 1: repo / outer container
├── pyproject.toml             ← dependency file
├── .venv/
└── operations_portalcms_django/    ← Level 2: Django project directory
    ├── manage.py              ← project entry point
    ├── operations_portalcms_django/ ← Level 3: config package (SAME name as Level 2)
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
Operations_PortalCMS_Django/                   ← Level 1: repo root / outer container ✅
├── pyproject.toml                             ← single dependency file ✅
├── uv.lock                                    ← locked environment ✅
├── portal.conf.dev.json                       ← local runtime config / dev config
├── portal.local.example.json                  ← example runtime config
├── manage.prod.sh.j2                          ← deployment helper ✅
├── portal.service.j2                          ← systemd unit ✅
├── nginx-portal.conf                          ← nginx deployment config
├── database/                                  ← database scripts and media backups
├── dev_documentation/                         ← project documentation
├── operations_portalcms_django/               ← Level 2: Django project directory ✅
│   ├── manage.py                              ← correct location ✅
│   ├── operations_portalcms_django/           ← Level 3: config package (matches Level 2) ✅
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── portal/                                ← core app: CMS workflow, unprivileged, utils ✅
│   │   ├── models.py                          ← re-export shim only (no model definitions)
│   │   ├── views.py                           ← unprivileged + CMS versioning views only
│   │   ├── forms.py                           ← empty (forms moved to feature apps)
│   │   ├── admin.py                           ← empty (admin moved to feature apps)
│   │   ├── signals.py
│   │   ├── workflow.py                        ← dead code (portal/urls.py no longer imports it)
│   │   ├── utils.py                           ← shared helpers (can_manage_news, is_rp_user)
│   │   ├── urls.py                            ← 3 routes: unprivileged + versioning (app_name='portal') ✅
│   │   ├── apps.py                            ← name = 'portal' ✅
│   │   ├── cms_plugins.py                     ← empty (plugins moved to feature apps)
│   │   ├── cms_toolbars.py
│   │   ├── management/commands/               ← setup_groups, setup_focus_area_page_permissions ✅
│   │   ├── migrations/                        ← 0001–0018; 0018 removes models via SeparateDatabaseAndState ✅
│   │   └── templatetags/                      ← correct app tag location ✅
│   ├── resources/                             ← CIDER data + public resource/software views ✅
│   │   ├── models.py                          ← CiderInfrastructure, CiderOrganizations, CiderFeatures, CiderGroups
│   │   ├── views.py                           ← access_allocated_resources, access_online_services, software_discovery, software_detail, resource_detail
│   │   ├── forms.py
│   │   ├── admin.py
│   │   ├── urls.py                            ← app_name = 'resources'
│   │   ├── apps.py
│   │   ├── management/commands/               ← sync_cider_from_api, load_test_cider_data, setup_rp_permissions
│   │   └── migrations/                        ← 0001 SeparateDatabaseAndState (no DDL)
│   ├── infrastructure_news/                   ← system status news ✅
│   │   ├── models.py                          ← SystemStatusNews, SystemStatusNewsItemPlugin
│   │   ├── views.py                           ← system_status_news, add/update views
│   │   ├── forms.py                           ← SystemStatusNewsForm
│   │   ├── admin.py                           ← SystemStatusNewsAdmin
│   │   ├── cms_plugins.py                     ← SystemStatusNewsItemPluginPublisher, SystemStatusNewsFeedPlugin
│   │   ├── urls.py                            ← app_name = 'infrastructure_news'
│   │   ├── workflow.py
│   │   ├── apps.py
│   │   ├── management/commands/               ← import_drupal_news
│   │   └── migrations/                        ← 0001 SeparateDatabaseAndState (no DDL)
│   ├── integration_news/                      ← integration news ✅
│   │   ├── models.py                          ← IntegrationElement, IntegrationNews, IntegrationNewsItemPlugin
│   │   ├── views.py                           ← integration_news, add/update views
│   │   ├── forms.py                           ← IntegrationNewsForm
│   │   ├── admin.py                           ← IntegrationNewsAdmin
│   │   ├── cms_plugins.py                     ← IntegrationNewsItemPluginPublisher, IntegrationNewsFeedPlugin
│   │   ├── urls.py                            ← app_name = 'integration_news'
│   │   ├── workflow.py
│   │   ├── apps.py
│   │   └── migrations/                        ← 0001 SeparateDatabaseAndState (no DDL)
│   ├── templates/                             ← project-wide templates ✅
│   │   └── portal/                            ← app-namespaced templates ✅
│   ├── static/                                ← project-wide source static assets ✅
│   │   └── portal/                            ← app-namespaced static assets ✅
│   ├── media/                                 ← uploaded media root ✅
│   └── tests/                                 ← project test suite ✅
```

**Primary findings:**
1. Level 2 (`operations_portalcms_django/`) and Level 3 (`operations_portalcms_django/operations_portalcms_django/`) match the vanilla `djangocms <project>` convention.
2. The project now has **4 app packages**: `portal` (core), `resources` (CIDER + resource views), `infrastructure_news` (system status news), `integration_news` (integration news).
3. All 9 models were moved out of `portal` into the 3 feature apps using `SeparateDatabaseAndState` migrations — no DDL was required because `db_table` values were preserved.
4. `DJANGO_SETTINGS_MODULE = 'operations_portalcms_django.settings'`, `ROOT_URLCONF = 'operations_portalcms_django.urls'`, `WSGI_APPLICATION = 'operations_portalcms_django.wsgi.application'`.
5. Deployment helpers updated: `manage.prod.sh.j2` uses `$APP_DJANGO/operations_portalcms_django`; `portal.service.j2` uses `WorkingDirectory={{ app_home }}/tags/Operations_PortalCMS_Django/operations_portalcms_django`; gunicorn starts `operations_portalcms_django.wsgi:application`.
6. `django manage.py check` passes clean (0 issues) after app split.

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
| Location | Inside Django project directory | ✅ `operations_portalcms_django/manage.py` | ✅ Inside middle `Operations_ServiceIndex_Django/` |
| `DJANGO_SETTINGS_MODULE` | Points to config package | ✅ `operations_portalcms_django.settings` | ✅ `Operations_ServiceIndex_Django.settings` |
| Boilerplate | Standard Django scaffold | ✅ Clean | ✅ Clean |

---

## 3. `settings.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | Config package | ✅ `operations_portalcms_django/operations_portalcms_django/settings.py` | ✅ Dedicated config package |
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
| Paths | Resolve from project directory | ✅ `BASE_DIR = operations_portalcms_django/`; templates/static/media resolve under it | ✅ |

---

## 4. `urls.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | Config package | ✅ `operations_portalcms_django/operations_portalcms_django/urls.py` | ✅ `Operations_ServiceIndex_Django/urls.py` |
| App URL separation | `include()` with namespaced app `urls.py` | ✅ `include('portal.urls')` (app_name = 'portal'), `include('resources.urls', namespace='resources')`, `include('infrastructure_news.urls', namespace='infrastructure_news')`, `include('integration_news.urls', namespace='integration_news')` | ✅ `include('services.urls', namespace='services')` |
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
| Views in config package | Views belong in apps only | ✅ App views live in `operations_portalcms_django/portal/views.py` | ❌ `favicon` view in `Operations_ServiceIndex_Django/views.py` |
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
| Location | Config package | ✅ `operations_portalcms_django/operations_portalcms_django/wsgi.py`, `asgi.py` | ✅ Dedicated config package |
| `DJANGO_SETTINGS_MODULE` | Must match config package path | ✅ `operations_portalcms_django.settings` | ✅ Matches |
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
| Location | `app/migrations/` | ✅ `operations_portalcms_django/portal/migrations/` | ✅ |
| Squashing | Periodic squashing keeps history manageable | ⚠️ 17 migrations, not yet squashed | ✅ `0001_squashed_0004_...` present |
| Committed to version control | Yes | ✅ | ✅ |

---

## 12. Templates

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Project-wide base templates | `project-dir/templates/` | ✅ `operations_portalcms_django/templates/base.html`, `page.html`, etc. | ✅ `templates/` present |
| App templates | `templates/appname/` namespacing | ✅ `operations_portalcms_django/templates/portal/` | ✅ `templates/services/` |
| `APP_DIRS = True` | Lets Django find app templates | ✅ | ✅ |
| Root leftovers | Avoid duplicate inactive template roots | ✅ Clean | — |

---

## 13. Static Files

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Source static | `project-dir/static/appname/` namespacing | ✅ `operations_portalcms_django/static/portal/` | ✅ `services/static/` |
| `STATICFILES_DIRS` vs `STATIC_ROOT` | Separate source dirs from collected output | ✅ `STATICFILES_DIRS = [BASE_DIR / 'static']`; `STATIC_ROOT = BASE_DIR / 'staticfiles'` by default | ✅ |
| Serving in development | `urlpatterns += static(...)` in DEBUG | ✅ | ✅ |
| Root leftovers | Avoid duplicate inactive static roots | ✅ Clean | — |

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
| Directory layout / project vs app separation | ✅ `operations_portalcms_django/` project dir, `operations_portalcms_django/operations_portalcms_django/` config package, `portal/` app package | ⚠️ Correct layout, but triple same-name nesting is confusing |
| `manage.py` | ✅ `operations_portalcms_django/manage.py` | ✅ Inside project directory |
| `settings.py` (config safety) | ✅ Strong | ❌ Fragile (raw dict, no defaults) |
| `urls.py` | ✅ Config/app URLs separated cleanly | ⚠️ Dead import, `re_path` overuse |
| `models.py` | ✅ | ⚠️ Wildcard imports, no `verbose_name` |
| `views.py` | ✅ | ❌ Auth decorators disabled, hardcoded authz, wildcard imports |
| `admin.py` | ✅ | ⚠️ Old registration style, wildcard imports |
| `signals.py` connection | ✅ via `ready()` | ❌ via view import |
| `wsgi.py` / `asgi.py` | ✅ Current `operations_portalcms_django.settings` | ✅ |
| `apps.py` | ✅ | ⚠️ No `ready()`, no `verbose_name` |
| Migrations | ✅ | ✅ |
| Templates | ✅ Active templates under `portal/`; root leftovers need cleanup | ✅ |
| Static files | ✅ Active static under `portal/`; root leftovers need cleanup | ✅ |
| Dependency management | ✅ | ❌ No project-level file |
| Tests | ⚠️ Present under `operations_portalcms_django/tests/`; no runner config | ❌ Stub only |

---

## Priority Recommendations

### PortalCMS

1. **DB migration record update required before deploying to an existing database** — Run `UPDATE django_migrations SET app = 'portal' WHERE app = 'operations_portalcms_django';` against any database that was previously running the old app label. This is the only change that git cannot reverse.
2. **Add test runner config** — Add a `pytest`/Django test configuration or document the canonical `uv run python manage.py test` command.
3. **Consider app-local tests** — `operations_portalcms_django/tests/` is valid for project integration tests, but app behavior would be better encapsulated in `operations_portalcms_django/portal/tests/` if this app is expected to stay reusable.
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
cd operations_portalcms_django
uv run python manage.py check
uv run python manage.py test
```

Runtime settings:

```python
DJANGO_SETTINGS_MODULE = "operations_portalcms_django.settings"
ROOT_URLCONF = "operations_portalcms_django.urls"
WSGI_APPLICATION = "operations_portalcms_django.wsgi.application"
BASE_DIR = Path(__file__).resolve().parent.parent  # operations_portalcms_django/
```

Deployment templates match this structure:

- `manage.prod.sh.j2` changes into `$APP_DJANGO/operations_portalcms_django` and runs `uv run python manage.py`.
- `portal.service.j2` uses `WorkingDirectory={{ app_home }}/PROD/operations_portalcms_django`.
- Gunicorn starts `operations_portalcms_django.wsgi:application`.

