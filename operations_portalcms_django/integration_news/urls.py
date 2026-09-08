from django.urls import path
from . import views
from . import workflow

app_name = 'integration_news'

urlpatterns = [
    path('integration-news/', views.integration_news, name='integration_news'),
    path('integration-news/add/', views.add_integration_news, name='add_integration_news'),
    path('integration-news/update/<int:pk>/', views.update_integration_news, name='update_integration_news'),
    path('integration-news/<int:pk>/submit/', workflow.submit_integration_for_review, name='submit_integration_for_review'),
    path('integration-news/<int:pk>/approve/', workflow.approve_integration_news, name='approve_integration_news'),
    path('integration-news/<int:pk>/reject/', workflow.reject_integration_news, name='reject_integration_news'),
    path('integration-news/<int:pk>/publish/', workflow.publish_integration_news, name='publish_integration_news'),
    path('integration-news/<int:pk>/unpublish/', workflow.unpublish_integration_news, name='unpublish_integration_news'),
    path('api/integration_news', views.api_integration_news, name='api_integration_news'),
]
