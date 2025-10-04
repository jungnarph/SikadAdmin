"""
Main URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from config import views

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Apps
    path('bikes/', include('apps.bikes.urls')),
    path('geofencing/', include('apps.geofencing.urls')),
    path('accounts/', include('apps.accounts.urls')),
    
    # Root redirect to dashboard
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "Sikad Bike Sharing Admin"
admin.site.site_title = "Sikad Admin Portal"
admin.site.index_title = "Welcome to Sikad Admin"