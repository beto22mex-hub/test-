"""manufacturing_system URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', include('analytics.urls')),  # Updated from statistics.urls to analytics.urls
    path('operators/', include('operators.urls')),
    path('serials/', include('serials.urls')),
    path('operations/', include('operations.urls')),
    path('defects/', include('defects.urls')),
    
    # Keep manufacturing URLs for backward compatibility during transition
    path('manufacturing/', include('manufacturing.urls')),
    path('api/', include('manufacturing.api_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
