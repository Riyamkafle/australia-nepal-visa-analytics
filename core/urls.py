from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from analytics import views as analytics_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # HTML dashboard pages
    path('', analytics_views.dashboard_home, name='home'),
    path('trends/', analytics_views.trends_page, name='trends'),
    path('sectors/', analytics_views.sectors_page, name='sectors'),
    path('universities/', analytics_views.universities_page, name='universities'),
    path('forecast/', analytics_views.forecast_page, name='forecast'),
    path('about/', analytics_views.about_page, name='about'),
    path('upload/', include('upload.urls')),

    # REST API
    path('api/', include('analytics.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
