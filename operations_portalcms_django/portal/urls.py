""" URL configuration for portal application views
Separate from main urls.py to keep CMS urls clean
"""
from django.urls import path
from django.views.generic import RedirectView
from . import views
from . import workflow

app_name = 'portal'

urlpatterns = [
    # Main navigation pages
    # path('', views.index, name='index'),  # Homepage now handled by CMS
    path('unprivileged/', views.unprivileged, name='unprivileged'),  # Permission error page
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
    path('infrastructure-news/', views.system_status_news, name='system_status_news'),
    path('integration-news/', views.integration_news, name='integration_news'),
    path('resources/access-allocated/', views.access_allocated_resources, name='access_allocated'),
    path('resources/access-online-services/', views.access_online_services, name='access_online_services'),
    path('resources/software-discovery/', views.software_discovery, name='software_discovery'),
    path('resources/software/<path:software_id>/', views.software_detail, name='software_detail'),
    
    # Resource detail page
    path('node/<int:node_id>/', views.resource_detail, name='resource_detail'),
    
    # Infrastructure News (System and Infrastructure Status) management
    path('infrastructure-news/add/', views.add_system_status_news, name='add_system_status_news'),
    path('infrastructure-news/update/<int:pk>/', views.update_system_status_news, name='update_system_status_news'),
    
    # Integration News management
    path('integration-news/add/', views.add_integration_news, name='add_integration_news'),
    path('integration-news/update/<int:pk>/', views.update_integration_news, name='update_integration_news'),
    
    # System Status News workflow actions
    path('infrastructure-news/<int:pk>/submit/', workflow.submit_systemstatus_for_review, name='submit_systemstatus_for_review'),
    path('infrastructure-news/<int:pk>/approve/', workflow.approve_systemstatus_news, name='approve_systemstatus_news'),
    path('infrastructure-news/<int:pk>/reject/', workflow.reject_systemstatus_news, name='reject_systemstatus_news'),
    path('infrastructure-news/<int:pk>/publish/', workflow.publish_systemstatus_news, name='publish_systemstatus_news'),
    path('infrastructure-news/<int:pk>/unpublish/', workflow.unpublish_systemstatus_news, name='unpublish_systemstatus_news'),
    
    # Integration News workflow actions
    path('integration-news/<int:pk>/submit/', workflow.submit_integration_for_review, name='submit_integration_for_review'),
    path('integration-news/<int:pk>/approve/', workflow.approve_integration_news, name='approve_integration_news'),
    path('integration-news/<int:pk>/reject/', workflow.reject_integration_news, name='reject_integration_news'),
    path('integration-news/<int:pk>/publish/', workflow.publish_integration_news, name='publish_integration_news'),
    path('integration-news/<int:pk>/unpublish/', workflow.unpublish_integration_news, name='unpublish_integration_news'),
]
