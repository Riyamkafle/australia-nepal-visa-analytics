from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # REST API only — the React frontend (aus-visa-insight) is the sole
    # production UI now. The legacy Django-template dashboard routes that
    # used to live here (/, /trends/, /sectors/, /universities/, /forecast/,
    # /about/, /upload/) have been removed per architecture decision; the
    # view functions and templates/dashboard/*.html files are left in the
    # repo as legacy reference, not deleted.
    path('api/', include('analytics.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
