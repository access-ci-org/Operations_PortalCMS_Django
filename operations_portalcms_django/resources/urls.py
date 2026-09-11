from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'resources'

urlpatterns = [
    path('resources/access-allocated/', views.access_allocated_resources, name='access_allocated'),
    path('resources/access-online-services/', views.access_online_services, name='access_online_services'),
    path('software_discovery/', views.software_discovery, name='software_discovery'),
    # Legacy path retained as a permanent redirect so existing external links keep working.
    path('resources/software-discovery/', RedirectView.as_view(url='/software_discovery/', permanent=True)),
    path('resources/software/<path:software_id>/', views.software_detail, name='software_detail'),
    path('node/<int:node_id>/', views.resource_detail, name='resource_detail'),
]
