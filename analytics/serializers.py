from rest_framework import serializers
from .models import (
    MonthlyTrend, BySector, FySummary, NepalMerged, Forecast,
    GenderBreakdown, LocationBreakdown, AgeBreakdown,
    ChannelBreakdown, SeasonalPattern,
)


class MonthlyTrendSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyTrend
        fields = '__all__'


class BySectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = BySector
        fields = '__all__'


class FySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = FySummary
        fields = '__all__'


class NepalMergedSerializer(serializers.ModelSerializer):
    class Meta:
        model = NepalMerged
        fields = '__all__'


class ForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = Forecast
        fields = '__all__'


class GenderBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenderBreakdown
        fields = '__all__'


class LocationBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationBreakdown
        fields = '__all__'


class AgeBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgeBreakdown
        fields = '__all__'


class ChannelBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelBreakdown
        fields = '__all__'


class SeasonalPatternSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeasonalPattern
        fields = '__all__'


class KPISummarySerializer(serializers.Serializer):
    """Executive KPI summary (computed, not a model)."""
    total_applications = serializers.IntegerField()
    total_granted      = serializers.IntegerField()
    total_refused      = serializers.IntegerField()
    grant_rate         = serializers.FloatField()
    refusal_rate       = serializers.FloatField()
    period_start       = serializers.CharField()
    period_end         = serializers.CharField()
    total_financial_years = serializers.IntegerField()
    top_sector         = serializers.CharField()
    top_sector_volume  = serializers.IntegerField()


class UniversityRankingSerializer(serializers.Serializer):
    """Provider/university rankings (computed from NepalMerged)."""
    provider_state = serializers.CharField()
    total_lodged   = serializers.IntegerField()
    total_granted  = serializers.IntegerField()
    total_refused  = serializers.IntegerField()
    grant_rate     = serializers.FloatField()
