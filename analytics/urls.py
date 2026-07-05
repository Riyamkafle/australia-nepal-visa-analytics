from django.urls import path
from . import views
from upload.views import upload_csv_api, upload_excel_api

urlpatterns = [
    path('',              views.api_root,          name='api-root'),
    path('kpi/',          views.kpi_summary,        name='api-kpi'),
    path('monthly/',      views.monthly_trend,      name='api-monthly'),
    path('sector/',       views.sector_breakdown,   name='api-sector'),
    path('fy/',           views.fy_summary,         name='api-fy'),
    path('merged/',       views.nepal_merged,        name='api-merged'),
    path('forecast/',     views.forecast_data,       name='api-forecast'),
    path('gender/',       views.gender_breakdown,    name='api-gender'),
    path('location/',     views.location_breakdown,  name='api-location'),
    path('age/',          views.age_breakdown,       name='api-age'),
    path('channel/',      views.channel_breakdown,   name='api-channel'),
    path('seasonal/',     views.seasonal_pattern,    name='api-seasonal'),
    path('universities/', views.university_rankings, name='api-universities'),
    path('search/',       views.search,              name='api-search'),
    path('validate/',     views.validate_data,       name='api-validate'),
    path('insights/',     views.insights,            name='api-insights'),
    path('upload/csv/',   upload_csv_api,            name='api-upload-csv'),
    path('upload/excel/', upload_excel_api,          name='api-upload-excel'),
]
