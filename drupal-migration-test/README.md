# Drupal to Django CMS Validation Script

This Python script validates migrated web infrastructure by cross-checking old and new servers.
It ensures that all original pages, URL paths, and redirect directives are fully intact and functional post-migration.

### Create and Activate a Virtual Environment (if needed)

```shell
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

```shell
pip install playwright
playwright install
```

### Change the urls as needed

[test-url-paths-and-redirects.py](test-url-paths-and-redirects.py)
```python
## CHANGE the server urls here
operations_portal_old_server = "https://operations.access-ci.org"
operations_portal_new_server = "https://beta-operations.access-ci.org"
```

## Running the Validation Tests

```shell
python test-url-paths-and-redirects.py
```
