"""URL configuration for config (Equipment Reservation System)."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    # App-specific URLconfs
    path('accounts/', include('accounts.urls')),
    path('equipment/', include('equipment.urls')),
    path('reservations/', include('reservations.urls')),
    # REST API
    path('api/', include('reservations.api_urls')),
    # Landing page
    path('', home, name='home'),
]

# In development, serve uploaded media files (equipment images) directly.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
