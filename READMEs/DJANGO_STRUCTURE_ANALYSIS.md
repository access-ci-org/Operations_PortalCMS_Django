# Django Structure Analysis — Side-by-Side

**Projects compared:**
- `Operations_PortalCMS_Django` (this repo) — Django 5.2 + django-CMS 5
- `Operations_ServiceIndex_Django` — Django 5.0, internal service catalog

**Note on `access_django_user_admin`:** This package appears embedded as a development clone in the ServiceIndex repo (has its own `.git/`, `LICENSE`, `requirements.txt`). That is intentional for local dev iteration. PortalCMS installs it correctly as a versioned dependency (`access-django-user-admin==1.5.3` in `pyproject.toml`); ServiceIndex should eventually do the same for production releases.

---

## Manager Feedback — Correction of Prior Analysis

A manager review identified two structural issues with PortalCMS. Both are valid and correct a mistake in the initial analysis:

> "manage.py isn't working because you moved the script from the default/convention in the Django project directory to the parent directory. The Django convention is that manage.py is inside the Django project directory. Another, perhaps more fundamental issue is that the Django project directory doesn't follow the normal Django convention for base directories with module sub-directories."

**On `manage.py` location:** The [Django 5.2 tutorial](https://docs.djangoproject.com/en/5.2/intro/tutorial01/) explicitly scaffolds:
```
$ django-admin startproject mysite djangotutorial
```
producing:
```
djangotutorial/     ← project container (repo root equivalent)
    manage.py       ← INSIDE the project directory
    mysite/         ← config package
        settings.py
        urls.py
        ...
```
The outer directory is the *project container*; `manage.py` lives *inside* it. PortalCMS was created with `django-admin startproject operations_portalcms_django .` (using `.`), which places `manage.py` at the directory where the command was run — making the git repo root both the container and the project directory with no separation. This is why the manager says manage.py was "moved to the parent directory": from Django's convention, `manage.py` belongs one level down, not at the outermost level. The prior analysis gave PortalCMS a ✅ on `manage.py` location — **that was wrong**.

**On ServiceIndex's triple nesting:** The prior analysis called ServiceIndex's three same-name levels a mistake. In fact, the structure is:
```
Operations_ServiceIndex_Django/    ← git repo root / container
└── Operations_ServiceIndex_Django/ ← Django project directory (manage.py lives here ✅)
    ├── manage.py
    └── Operations_ServiceIndex_Django/  ← config package
```
This correctly matches Django's convention. The *only* real issue is that all three levels share the same name, creating cognitive overhead. But the structural convention — manage.py inside the project directory, inside the repo container — is correct.

**On project package structure (second manager point):** The Django tutorial produces a project directory containing `manage.py` + separate module subdirectories for the config package and each app. PortalCMS has one package (`operations_portalcms_django/`) that serves as both the config package (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`) and the app (`models.py`, `views.py`, etc.). There are no separate module subdirectories. The original analysis correctly identified this conflation; the manager independently flagged the same issue.

---

## 1. Top-Level Directory Layout

### Django Convention
```
repo-root/
├── manage.py                  ← project entry point, at repo root
├── pyproject.toml             ← single dependency file
├── config/                    ← project config package (settings, urls, wsgi, asgi)
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── myapp/                     ← one directory per reusable app
│   ├── models.py
│   ├── views.py
│   └── ...
├── templates/                 ← project-wide base templates
├── static/                    ← project-wide static assets
└── tests/                     ← or inside each app
```

Key principle: the **project config package** (settings, urls, wsgi, asgi) is separate from **application packages** (models, views, forms). `manage.py` lives at repo root.

---

### PortalCMS Actual Layout

```
Operations_PortalCMS_Django/           ← repo root (also Django project dir — no outer container ❌)
├── manage.py                          ← ❌ should be one level deeper, inside a project subdir
├── pyproject.toml                     ← single dependency file ✅
├── operations_portalcms_django/       ← ❌ BOTH project config AND app (no module subdirectory separation)
│   ├── settings.py                    ← project config
│   ├── urls.py                        ← project config
│   ├── wsgi.py                        ← project config
│   ├── asgi.py                        ← project config
│   ├── models.py                      ← app code — in same package
│   ├── views.py                       ← app code — in same package
│   ├── forms.py                       ← app code — in same package
│   ├── admin.py                       ← app code — in same package
│   ├── signals.py                     ← app code — in same package
│   ├── workflow.py                    ← app code — in same package
│   ├── utils.py                       ← app code — in same package
│   ├── app_urls.py                    ← workaround for the conflation
│   ├── apps.py
│   ├── cms_plugins.py
│   ├── cms_toolbars.py
│   ├── management/commands/           ← ✅ correct location
│   ├── migrations/                    ← ✅ correct location
│   └── templatetags/                  ← ✅ correct location
├── templates/                         ← ✅ project-wide templates
├── static/                            ← ✅
└── tests/                             ← ⚠️ outside the app package
```

**Primary findings:**
1. `manage.py` is at the repo root with no outer project container. Django's convention (including the tutorial) places `manage.py` *inside* a project directory, which itself sits inside the repo/container. This was created using the `.` form of `startproject`, collapsing the two levels into one.
2. `operations_portalcms_django` conflates the project config package and the application package into one directory. There are no separate module subdirectories. The `app_urls.py` file is a pragmatic workaround for the URL conflict this creates, but does not resolve the conflation.

---

### ServiceIndex Actual Layout

```
service-index-uv-sand/
└── Operations_ServiceIndex_Django/    ← repo root
    └── Operations_ServiceIndex_Django/ ← ❌ extra nesting (startproject run inside named dir)
        ├── manage.py                  ← ✅ correct relative to Django project root
        ├── Operations_ServiceIndex_Django/  ← project config package
        │   ├── settings.py
        │   ├── urls.py
        │   ├── wsgi.py
        │   ├── asgi.py
        │   └── views.py               ← ❌ favicon view in project config package
        ├── services/                  ← ✅ proper app package
        │   ├── models.py
        │   ├── views.py
        │   ├── forms.py (missing)
        │   ├── admin.py
        │   ├── signals.py
        │   ├── serializers.py         ← ✅ good separation
        │   ├── context_processors.py  ← ✅ good separation
        │   ├── urls.py
        │   ├── templatetags/
        │   ├── static/
        │   ├── migrations/
        │   └── tests.py               ← stub only
        ├── access_django_user_admin/  ← dev clone (has own .git/)
        └── templates/
```

**Primary finding:** The triple same-name nesting is cognitively confusing but structurally correct: the outer folder is the repo container, the middle folder is the Django project directory (where `manage.py` belongs), and the innermost folder is the config package. This is exactly the layout Django's tutorial produces — the issue is purely naming. The `services` app is properly separated from the project config, which is better than PortalCMS on both dimensions (manage.py placement and config/app separation).

---

## 2. `manage.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | Inside project directory, which is inside repo container | ❌ At repo root — no outer project container; created with `startproject .` | ✅ Inside middle `Operations_ServiceIndex_Django/` (the Django project dir) |
| `DJANGO_SETTINGS_MODULE` | Points to config package | `operations_portalcms_django.settings` — points into conflated package | `Operations_ServiceIndex_Django.settings` — correct relative to its root |
| Boilerplate | Standard Django scaffold | ✅ Clean | ✅ Clean |

---

## 3. `settings.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | Config package | ⚠️ In conflated app/config package | ✅ In dedicated config package |
| Secret key | Never hardcoded; from env/secrets | ✅ From `APP_CONFIG` JSON | ✅ From `APP_CONFIG` JSON |
| `DEBUG` default | `False` for safety | ⚠️ `_bool_value(CONF.get('DEBUG'), True)` — defaults **True** if key absent | ❌ `CONF["DEBUG"]` — `KeyError` if key absent, no default |
| `ALLOWED_HOSTS` | Explicit list; never `['*']` in prod | ⚠️ Falls back to `[]` (rejects all) if env var absent after config load | ❌ `CONF["ALLOWED_HOSTS"]` — `KeyError` if key absent |
| Required key validation | Explicit contract | ✅ `required_config_keys` list with clear error messages | ❌ No validation; runtime `KeyError` on first access |
| Type coercion | Validated booleans/lists | ✅ `_bool_value()` and `_env_bool()` helpers | ❌ Raw dict access; `DEBUG` must be an actual bool in JSON |
| `INSTALLED_APPS` order | Third-party before local; admin style first if used | ✅ Correct; `djangocms_admin_style` first | ✅ Correct |
| Database config | All credentials from env/secrets | ✅ Via env vars populated from `APP_CONFIG` | ⚠️ Direct `CONF[]` dict access; read/write DB split is a nice addition |
| SSL/DB options | Configurable | ✅ `DB_SSLMODE`, `DB_SSLROOTCERT`, etc. | ❌ Not present |
| `SECRET_KEY` | From config, not hardcoded | ✅ | ✅ |
| `CONN_MAX_AGE` | Should be set for persistent connections | ❌ Not set | ✅ `600` |

---

## 4. `urls.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | Config package | `operations_portalcms_django/urls.py` — conflated | `Operations_ServiceIndex_Django/urls.py` — ✅ config package |
| App URL separation | `include()` with namespaced app `urls.py` | ✅ `include('operations_portalcms_django.app_urls')` for app routes | ✅ `include('services.urls', namespace='services')` |
| Catch-all last | CMS/wildcard routes at end | ✅ `cms.urls` is last | ✅ `RedirectView` is last |
| Dead imports | No unused imports | — | ❌ `from access_django_user_admin import views` then immediately shadowed by `from . import views` |
| `re_path` vs `path` | Prefer `path()` with converters | — | ⚠️ Several `re_path(r'^edit/(?P<id>\d+)$')` that could be `path('edit/<int:id>')` |

---

## 5. `models.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| `default_auto_field` | Set in `AppConfig` or `settings.py` | ✅ `BigAutoField` in `apps.py` | ✅ `BigAutoField` in `apps.py` (services) |
| `__str__` methods | All models should define one | ✅ Consistent | ✅ All have `__str__` (and legacy `__unicode__`) |
| Explicit `verbose_name` | Recommended for readability | ✅ Thorough | ⚠️ Not used; relies on Django's auto-generated names |
| `Meta` class | Order, verbose names, permissions | ✅ Custom `permissions` for workflow | ⚠️ Minimal or absent |
| Choices as class attributes or `TextChoices` | Prefer `TextChoices` or `IntegerChoices` (Django 3.0+) | ⚠️ Uses plain list-of-tuples | ⚠️ Uses plain list-of-tuples |
| Wildcard import in views | `from .models import *` is discouraged | ✅ Explicit imports | ❌ `from services.models import *` in `views.py` and `admin.py` |
| Business logic separation | Heavy logic → service layer or signals; not in models | ✅ Workflow in `workflow.py` | ⚠️ Some logic in views directly |

---

## 6. `views.py`

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Auth enforcement | `@login_required` or `LoginRequiredMixin` | ✅ Consistently applied | ❌ Decorators commented out on `index` and `add_service` |
| Permission checks | `has_perm()` or `permission_required` | ✅ `has_perm()` | ❌ `editors_check(user)` group check only; `is_privileged()` hardcodes `username == 'navarro'` |
| Import hygiene | Explicit imports only | ✅ | ❌ `from services.models import *` |
| Function-based vs class-based | Either fine; CBVs preferred for CRUD | ✅ FBVs consistent | ✅ FBVs consistent |
| Views in config package | Views belong in apps only | ✅ All in app | ❌ `favicon` view in `Operations_ServiceIndex_Django/views.py` (config package) |
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
| Location | Config package | ⚠️ In conflated app/config package | ✅ In dedicated config package |
| `DJANGO_SETTINGS_MODULE` | Must match config package path | ✅ Matches | ✅ Matches |
| Module docstrings | Reference correct project name | ⚠️ Both reference `djangocmsjoy` (stale copy-paste) | ✅ |

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
| Location | `app/migrations/` | ✅ | ✅ |
| Squashing | Periodic squashing keeps history manageable | — | ✅ `0001_squashed_0004_...` present |
| Committed to version control | Yes | ✅ | ✅ |

---

## 12. Templates

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Project-wide base templates | `templates/` at repo root | ✅ `templates/base.html`, `page.html`, etc. | ✅ `templates/` present |
| App templates | `appname/templates/appname/` namespacing | ✅ `templates/operations_portalcms_django/` | ✅ `templates/services/` |
| `APP_DIRS = True` | Lets Django find `app/templates/` | ✅ | ✅ |

---

## 13. Static Files

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| App static | `appname/static/appname/` namespacing | ✅ `static/operations_portalcms_django/` | ✅ `services/static/` |
| `STATICFILES_DIRS` vs `STATIC_ROOT` | Separate source dirs from collected output | ✅ | ✅ |
| Serving in development | `urlpatterns += static(...)` in DEBUG | ✅ | ✅ |

---

## 14. Dependency Management

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Single dependency file at repo root | `pyproject.toml` (modern) or `requirements.txt` | ✅ `pyproject.toml` with pinned ranges | ❌ No project-level file; `access_django_user_admin/requirements.txt` only |
| Version pinning | Use ranges (`>=x,<y`) not exact pins for flexibility | ✅ | N/A |
| Virtual environment | `.venv` at repo root | ✅ `.venv/` | ✅ `.venv/` (in outer repo) |

---

## 15. Tests

| Aspect | Convention | PortalCMS | ServiceIndex |
|---|---|---|---|
| Location | `app/tests/` or `tests/` inside app | ⚠️ `tests/` at repo root, not inside app | ❌ `services/tests.py` is an empty stub |
| Test isolation | Each app's tests in its own directory | ⚠️ All tests in one top-level folder | ❌ No real tests |
| Test runner config | `pyproject.toml` or `setup.cfg` | ❌ Not configured | ❌ Not configured |

---

## Summary Scorecard

| Category | PortalCMS | ServiceIndex |
|---|---|---|
| Directory layout / project vs app separation | ❌ No outer container; `manage.py` at repo root; config+app conflated | ⚠️ Correct layout (container→project dir→config pkg); naming confusing |
| `manage.py` | ❌ At repo root (no outer container) | ✅ Inside project directory |
| `settings.py` (config safety) | ✅ Strong | ❌ Fragile (raw dict, no defaults) |
| `urls.py` | ✅ | ⚠️ Dead import, `re_path` overuse |
| `models.py` | ✅ | ⚠️ Wildcard imports, no `verbose_name` |
| `views.py` | ✅ | ❌ Auth decorators disabled, hardcoded authz, wildcard imports |
| `admin.py` | ✅ | ⚠️ Old registration style, wildcard imports |
| `signals.py` connection | ✅ via `ready()` | ❌ via view import |
| `wsgi.py` / `asgi.py` | ⚠️ Stale docstrings | ✅ |
| `apps.py` | ✅ | ⚠️ No `ready()`, no `verbose_name` |
| Migrations | ✅ | ✅ |
| Templates | ✅ | ✅ |
| Dependency management | ✅ | ❌ No project-level file |
| Tests | ⚠️ Outside app | ❌ Stub only |

---

## Priority Recommendations

### PortalCMS (structural debt — two issues flagged by manager)

1. **Add project directory container** — The repo root should contain a subdirectory (e.g. `portal/`) that holds `manage.py`, the config package, and app packages. Currently `manage.py` is at the repo root with no outer container, contrary to Django convention. This requires updating `DJANGO_SETTINGS_MODULE`, `ROOT_URLCONF`, `WSGI_APPLICATION`, `ASGI_APPLICATION`, and the deployment service files.
2. **Split config from app** — Create a separate config package (e.g. `config/`) inside that project directory for `settings.py`, `urls.py`, `wsgi.py`, `asgi.py`. Keep `operations_portalcms_django/` as the app-only package. Rename `app_urls.py` back to `urls.py`. This resolves both manager-raised issues together.
2. **`DEBUG` default** — Change `_bool_value(CONF.get('DEBUG'), True)` to default `False`.
3. **Fix stale docstrings** — `wsgi.py` and `asgi.py` reference `djangocmsjoy`.
4. **Move `tests/`** — Place inside `operations_portalcms_django/tests/` for proper app encapsulation.

### ServiceIndex (higher urgency — active security/reliability concerns)

1. **Re-enable auth decorators** — `@login_required` and `@user_passes_test` are commented out on `index` and `add_service`.
2. **Remove hardcoded authorization** — `is_privileged()` checking `username == 'navarro'` must go; use group membership or `is_staff`.
3. **Fix `settings.py`** — Add required key validation, default for `DEBUG`, type coercion for booleans.
4. **Fix `urls.py`** — Remove the shadowed `access_django_user_admin` import.
5. **Add `pyproject.toml`** at project root with proper dependencies.
6. **Connect signals via `ready()`** — Move `import services.signals` from `views.py` into `ServicesConfig.ready()`.
7. **Replace wildcard imports** — `from services.models import *` → explicit imports in `views.py` and `admin.py`.
8. **Rename triple-nested directories** — Rename the same-name levels so the structure is self-explanatory; the convention is already correct, only the naming is confusing.

---

## PortalCMS Restructure Plan

### Target layout

```
Operations_PortalCMS_Django/        ← git repo root (outer container only)
├── pyproject.toml                  ← stays here
├── .venv/                          ← stays here
├── .gitignore                      ← stays here
├── portal.conf.dev.json            ← stays here (APP_CONFIG points to absolute path)
├── portal.local.example.json       ← stays here
├── nginx-portal.conf               ← stays here
├── manage.prod.sh.j2               ← stays here (update paths inside)
├── portal.service.j2               ← stays here (update paths inside)
├── database/                       ← stays here
├── READMEs/                        ← stays here
└── portal/                         ← NEW: Django project directory
    ├── manage.py                   ← moved from repo root
    ├── config/                     ← NEW: project config package only
    │   ├── __init__.py
    │   ├── settings.py             ← moved from operations_portalcms_django/
    │   ├── urls.py                 ← moved from operations_portalcms_django/
    │   ├── wsgi.py                 ← moved from operations_portalcms_django/
    │   └── asgi.py                 ← moved from operations_portalcms_django/
    ├── operations_portalcms_django/ ← app only (internal files unchanged)
    │   ├── urls.py                 ← renamed from app_urls.py
    │   └── ... (models, views, forms, admin, signals, etc. — all unchanged)
    ├── templates/                  ← moved from repo root
    ├── static/                     ← moved from repo root
    ├── staticfiles/                ← moved from repo root
    ├── media/                      ← moved from repo root
    └── tests/                      ← moved from repo root
```

### Step-by-step

**1. Create the new directory structure**
```bash
mkdir portal portal/config
touch portal/config/__init__.py
```

**2. Move files into place**
```bash
# manage.py moves down into the project directory
mv manage.py portal/

# Config files move into config/
mv operations_portalcms_django/settings.py portal/config/
mv operations_portalcms_django/urls.py portal/config/
mv operations_portalcms_django/wsgi.py portal/config/
mv operations_portalcms_django/asgi.py portal/config/

# Rename app_urls.py → urls.py now that the project urls.py is gone
mv operations_portalcms_django/app_urls.py operations_portalcms_django/urls.py

# Move the app and project-scoped directories
mv operations_portalcms_django/ portal/
mv templates/ portal/
mv static/ portal/
mv staticfiles/ portal/
mv media/ portal/
mv tests/ portal/
```

**3. Update `portal/manage.py`**
```python
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
```

**4. Update `portal/config/wsgi.py` and `portal/config/asgi.py`**
```python
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
```
Also fix the stale docstrings — both still reference `djangocmsjoy`.

**5. Update `portal/config/settings.py`**

`BASE_DIR` resolves from `config/settings.py` → `config/` → `portal/`, so the value is unchanged if you keep `parent.parent`. Verify:
```python
BASE_DIR = Path(__file__).resolve().parent.parent  # → portal/ ✅

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'  # if wired
```
Check that `TEMPLATES[DIRS]`, `STATIC_ROOT`, `MEDIA_ROOT`, and `STATICFILES_DIRS` all resolve from `BASE_DIR` and are not hardcoded.

**6. Update `portal/config/urls.py`**
```python
# Change the app include from:
path('', include('operations_portalcms_django.app_urls')),
# to:
path('', include('operations_portalcms_django.urls')),
```

**7. Update `portal/operations_portalcms_django/urls.py`** (was `app_urls.py`)

The `app_name`, `app_name = 'operations_portalcms_django'`, and all `urlpatterns` entries stay exactly the same. Remove the comment referencing `app_urls.py` in the docstring.

**8. Update deployment files at repo root**

These reference the old `manage.py` path and `DJANGO_SETTINGS_MODULE`:
- `manage.prod.sh.j2` — update path to `portal/manage.py` and `DJANGO_SETTINGS_MODULE=config.settings`
- `portal.service.j2` — `WorkingDirectory` should point to `portal/`; `ExecStart` path for gunicorn/manage.py needs updating
- `portal.conf.dev.json` — check for any path references to project files

**9. Verify `APP_CONFIG` and startup scripts**

`APP_CONFIG` uses an absolute path to the JSON config file — no change needed. Any script that does `cd <repo-root> && python manage.py ...` must become `cd portal && python manage.py ...` or use an absolute path.

### Key gotchas

- **`BASE_DIR`** — After the move, `config/settings.py` is at `portal/config/settings.py`, so `Path(__file__).resolve().parent.parent` = `portal/`. All paths built from `BASE_DIR` (`STATIC_ROOT`, `MEDIA_ROOT`, `TEMPLATES DIRS`) resolve correctly as long as they weren't hardcoded.
- **Migrations** — The app label `operations_portalcms_django` is unchanged; existing migration history is fine. Run `python manage.py migrate --check` to confirm.
- **`.venv` stays at repo root** — Activate it from wherever, but run `manage.py` from inside `portal/`.
- **`pyproject.toml` stays at repo root** — `uv`/pip installs are unaffected.
- **`portal.conf.dev.json` and `portal.local.example.json` stay at repo root** — `APP_CONFIG` references them by absolute path; no change needed.
- **Post-move verification** — Run `python manage.py check` immediately after restructuring. Then `python manage.py check --deploy` before deploying.
