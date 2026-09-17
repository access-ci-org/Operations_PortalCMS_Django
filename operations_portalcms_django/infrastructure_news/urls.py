from django.urls import path
from . import views
from . import workflow

app_name = 'infrastructure_news'

urlpatterns = [
    path('infrastructure_news_view', views.system_status_news, name='system_status_news'),
    path('infrastructure-news/add/', views.add_system_status_news, name='add_system_status_news'),
    path('infrastructure-news/update/<int:pk>/', views.update_system_status_news, name='update_system_status_news'),
    path('infrastructure-news/<int:pk>/publish/', workflow.publish_systemstatus_news, name='publish_systemstatus_news'),
    path('infrastructure-news/<int:pk>/unpublish/', workflow.unpublish_systemstatus_news, name='unpublish_systemstatus_news'),
    path('api/infrastructure_news_v1', views.api_infrastructure_news, name='api_infrastructure_news'),
]
