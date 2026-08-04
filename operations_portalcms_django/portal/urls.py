"""URL configuration for portal application — core views only.
News and resource views are served from their own apps (infrastructure_news, integration_news, resources).
"""
from django.urls import path
from . import health, views

app_name = 'portal'

urlpatterns = [
    path('healthz/', health.readiness, name='healthz'),
    path('unprivileged/', views.unprivileged, name='unprivileged'),
    path(
        'cms-versioning/version/<int:version_id>/submit-for-review/',
        views.submit_page_draft_for_review,
        name='submit_page_draft_for_review',
    ),
    path(
        'cms-versioning/version/<int:version_id>/unlock/',
        views.unlock_cms_page_draft,
        name='unlock_cms_page_draft',
    ),
]
