from django.urls import path
from . import views

app_name = 'resources'

urlpatterns = [
    path('resources/access-allocated/', views.access_allocated_resources, name='access_allocated'),
    path('resources/access-online-services/', views.access_online_services, name='access_online_services'),
    path('resources/software-discovery/', views.software_discovery, name='software_discovery'),
    path('resources/software/<path:software_id>/', views.software_detail, name='software_detail'),
    path('node/<int:node_id>/', views.resource_detail, name='resource_detail'),
]
