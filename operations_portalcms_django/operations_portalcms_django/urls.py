"""
URL configuration for Operations Portal CMS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('filer/', include('filer.urls')),
    path('accounts/', include('allauth.urls')),  # Allauth (login/logout/social auth/CILogon)
    path('access_django_user_admin/', include('access_django_user_admin.urls', namespace="access_django_user_admin")),
    path('', include('resources.urls', namespace='resources')),  # Resources (CIDER) views
    path('', include('infrastructure_news.urls', namespace='infrastructure_news')),  # Infrastructure/system status news
    path('', include('integration_news.urls', namespace='integration_news')),  # Integration news
    path('', include('portal.urls')),  # Application views (portal core, etc.)
    path('', include('cms.urls')),  # CMS pages - keep this last as catch-all
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
