"""
Django models for Nepal Student Visa Analytics Dashboard.
All existing PostgreSQL tables are declared as unmanaged (managed=False).

Fixes applied:
- BySector: id as IntegerField (not AutoField) for unmanaged table safety
- NepalMerged: id as IntegerField
- ChannelBreakdown: added missing 'refused' field
- AgeBreakdown: added missing 'refused' field
- All FloatField columns use null=True, blank=True for safety
"""

from django.db import models


class MonthlyTrend(models.Model):
    """
    Monthly grant/refusal trend with rolling averages.
    Source table: monthly_trend (46 rows)
    """
    year_month   = models.CharField(max_length=20, primary_key=True)
    lodged       = models.IntegerField(default=0)
    granted      = models.IntegerField(default=0)
    grant_rate   = models.FloatField(null=True, blank=True)
    refusal_rate = models.FloatField(null=True, blank=True)
    rolling_3m   = models.FloatField(null=True, blank=True)
    cal_month    = models.IntegerField(null=True, blank=True)
    month_name   = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'monthly_trend'
        ordering = ['year_month']

    def __str__(self):
        return f"MonthlyTrend({self.year_month})"


class BySector(models.Model):
    """
    Applications by sector per month.
    Source table: by_sector (291 rows)
    FIX: id is IntegerField not AutoField — safer for unmanaged tables.
    If your table has no id column run:
        ALTER TABLE by_sector ADD COLUMN id SERIAL PRIMARY KEY;
    """
    id         = models.IntegerField(primary_key=True)
    year_month = models.CharField(max_length=20)
    sector     = models.CharField(max_length=200)
    lodged     = models.IntegerField(default=0)
    granted    = models.IntegerField(default=0)
    grant_rate = models.FloatField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'by_sector'
        ordering = ['year_month', 'sector']

    def __str__(self):
        return f"BySector({self.year_month}, {self.sector})"


class FySummary(models.Model):
    """
    Financial year rollup summary.
    Source table: fy_summary (4 rows)
    """
    financial_year = models.CharField(max_length=20, primary_key=True)
    lodged         = models.IntegerField(default=0)
    granted        = models.IntegerField(default=0)
    refused        = models.IntegerField(default=0)
    grant_rate     = models.FloatField(null=True, blank=True)
    refusal_rate   = models.FloatField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'fy_summary'
        ordering = ['financial_year']

    def __str__(self):
        return f"FySummary({self.financial_year})"


class NepalMerged(models.Model):
    """
    Full granular Nepal applicant dataset.
    Source table: nepal_merged (25,939 rows)
    This is a cross-tabulation table — not deduplicated.
    Used for dimension-level breakdowns only, not for total KPIs.
    """
    id                = models.IntegerField(primary_key=True)
    financial_year    = models.CharField(max_length=20,  null=True, blank=True)
    fy_quarter        = models.CharField(max_length=10,  null=True, blank=True)
    month             = models.CharField(max_length=20,  null=True, blank=True)
    client_location   = models.CharField(max_length=20,  null=True, blank=True)
    lodgement_channel = models.CharField(max_length=50,  null=True, blank=True)
    sector            = models.CharField(max_length=200, null=True, blank=True)
    applicant_type    = models.CharField(max_length=50,  null=True, blank=True)
    provider_state    = models.CharField(max_length=50,  null=True, blank=True)
    gender            = models.CharField(max_length=20,  null=True, blank=True)
    country           = models.CharField(max_length=50,  null=True, blank=True)
    age_group         = models.CharField(max_length=20,  null=True, blank=True)
    lodged_count      = models.IntegerField(default=0)
    date              = models.DateField(null=True, blank=True)
    year_month        = models.CharField(max_length=20,  null=True, blank=True)
    granted_count     = models.IntegerField(default=0)
    grant_rates_count = models.IntegerField(default=0)
    refused_count     = models.IntegerField(default=0)
    grant_rate_calc   = models.FloatField(null=True, blank=True)
    refusal_rate_calc = models.FloatField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'nepal_merged'
        ordering = ['date']

    def __str__(self):
        return f"NepalMerged({self.financial_year}, {self.sector})"


class Forecast(models.Model):
    """
    12-month forward forecast with confidence bands.
    Source table: forecast (12 rows)
    """
    year_month          = models.CharField(max_length=20, primary_key=True)
    month_label         = models.CharField(max_length=30, null=True, blank=True)
    lodged_forecast     = models.FloatField(null=True, blank=True)
    granted_forecast    = models.FloatField(null=True, blank=True)
    refused_forecast    = models.FloatField(null=True, blank=True)
    grant_rate_forecast = models.FloatField(null=True, blank=True)
    upper_bound         = models.FloatField(null=True, blank=True)
    lower_bound         = models.FloatField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'forecast'
        ordering = ['year_month']

    def __str__(self):
        return f"Forecast({self.year_month})"


class GenderBreakdown(models.Model):
    """
    Applications by gender.
    Source table: gender_breakdown (3 rows: Male, Female, Unknown)
    """
    gender     = models.CharField(max_length=20, primary_key=True)
    lodged     = models.IntegerField(default=0)
    granted    = models.IntegerField(default=0)
    refused    = models.IntegerField(default=0)
    grant_rate = models.FloatField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'gender_breakdown'

    def __str__(self):
        return f"GenderBreakdown({self.gender})"


class LocationBreakdown(models.Model):
    """
    Onshore vs Offshore breakdown.
    Source table: location_breakdown (2 rows)
    """
    client_location = models.CharField(max_length=20, primary_key=True)
    lodged          = models.IntegerField(default=0)
    granted         = models.IntegerField(default=0)
    refused         = models.IntegerField(default=0)
    grant_rate      = models.FloatField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'location_breakdown'

    def __str__(self):
        return f"LocationBreakdown({self.client_location})"


class AgeBreakdown(models.Model):
    id         = models.IntegerField(primary_key=True)
    age_group  = models.CharField(max_length=30, null=True, blank=True)
    lodged     = models.IntegerField(default=0)
    granted    = models.IntegerField(default=0)
    refused    = models.IntegerField(default=0)
    grant_rate = models.FloatField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'age_breakdown'
        ordering = ['age_group']

    def __str__(self):
        return f"AgeBreakdown({self.age_group})"


class ChannelBreakdown(models.Model):
    """
    Applications by lodgement channel (Paper vs Electronic).
    Source table: channel_breakdown (2 rows)
    FIX: Added missing 'refused' field.
    """
    lodgement_channel = models.CharField(max_length=50, primary_key=True)
    lodged            = models.IntegerField(default=0)
    granted           = models.IntegerField(default=0)
    refused           = models.IntegerField(default=0)
    grant_rate        = models.FloatField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'channel_breakdown'

    def __str__(self):
        return f"ChannelBreakdown({self.lodgement_channel})"


class SeasonalPattern(models.Model):
    """
    Average grant/lodged/refused by calendar month across all years.
    Source table: seasonal_pattern (12 rows)
    Primary key: cal_month (1=Jan ... 12=Dec)
    """
    cal_month   = models.IntegerField(primary_key=True)
    month_name  = models.CharField(max_length=20)
    avg_grant   = models.FloatField(null=True, blank=True)
    avg_lodged  = models.FloatField(null=True, blank=True)
    avg_refused = models.FloatField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'seasonal_pattern'
        ordering = ['cal_month']

    def __str__(self):
        return f"SeasonalPattern({self.month_name})"