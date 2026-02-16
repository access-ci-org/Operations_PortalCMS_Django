""" URL configuration for operations_portalcms_django application views
Separate from main urls.py to keep CMS urls clean
"""
from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'operations_portalcms_django'

urlpatterns = [
    # Main navigation pages
    path('', views.index, name='index'),  # Homepage at root
    path('unprivileged/', views.unprivileged, name='unprivileged'),  # Permission error page
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
]
