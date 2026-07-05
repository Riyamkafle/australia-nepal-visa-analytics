from django.contrib import admin
from .models import (
    MonthlyTrend, BySector, FySummary, NepalMerged, Forecast,
    GenderBreakdown, LocationBreakdown, AgeBreakdown,
    ChannelBreakdown, SeasonalPattern,
)


@admin.register(MonthlyTrend)
class MonthlyTrendAdmin(admin.ModelAdmin):
    list_display  = ('year_month', 'lodged', 'granted', 'grant_rate', 'refusal_rate', 'rolling_3m')
    search_fields = ('year_month', 'month_name')
    ordering      = ('year_month',)


@admin.register(BySector)
class BySectorAdmin(admin.ModelAdmin):
    list_display  = ('year_month', 'sector', 'lodged', 'granted', 'grant_rate')
    search_fields = ('sector', 'year_month')
    list_filter   = ('year_month',)


@admin.register(FySummary)
class FySummaryAdmin(admin.ModelAdmin):
    list_display = ('financial_year', 'lodged', 'granted', 'refused', 'grant_rate', 'refusal_rate')


@admin.register(NepalMerged)
class NepalMergedAdmin(admin.ModelAdmin):
    list_display  = ('financial_year', 'sector', 'provider_state', 'gender', 'lodged_count', 'granted_count', 'grant_rate_calc')
    search_fields = ('sector', 'provider_state', 'financial_year', 'gender', 'age_group')
    list_filter   = ('financial_year', 'client_location', 'lodgement_channel', 'gender')


@admin.register(Forecast)
class ForecastAdmin(admin.ModelAdmin):
    list_display = ('year_month', 'month_label', 'lodged_forecast', 'granted_forecast', 'grant_rate_forecast', 'upper_bound', 'lower_bound')


@admin.register(GenderBreakdown)
class GenderBreakdownAdmin(admin.ModelAdmin):
    list_display = ('gender', 'lodged', 'granted', 'refused', 'grant_rate')


@admin.register(LocationBreakdown)
class LocationBreakdownAdmin(admin.ModelAdmin):
    list_display = ('client_location', 'lodged', 'granted', 'refused', 'grant_rate')


@admin.register(AgeBreakdown)
class AgeBreakdownAdmin(admin.ModelAdmin):
    list_display = ('age_group', 'lodged', 'granted', 'grant_rate')


@admin.register(ChannelBreakdown)
class ChannelBreakdownAdmin(admin.ModelAdmin):
    list_display = ('lodgement_channel', 'lodged', 'granted', 'grant_rate')


@admin.register(SeasonalPattern)
class SeasonalPatternAdmin(admin.ModelAdmin):
    list_display = ('cal_month', 'month_name', 'avg_lodged', 'avg_grant', 'avg_refused')
    ordering     = ('cal_month',)
