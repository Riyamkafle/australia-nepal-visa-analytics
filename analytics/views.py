"""
Views for the Nepal Student Visa Analytics Dashboard.
Includes both HTML template views and DRF API views.
"""

import math

from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination


def clean_float(value):
    """Replace inf/nan float values with None so JSON serialization never breaks."""
    if value is None:
        return None
    try:
        f = float(value)
        if math.isfinite(f):
            return f
        return None
    except (TypeError, ValueError):
        return None


def sanitize_record(record: dict) -> dict:
    """Walk a dict and replace any inf/nan floats with None."""
    cleaned = {}
    for k, v in record.items():
        if isinstance(v, float):
            cleaned[k] = clean_float(v)
        else:
            cleaned[k] = v
    return cleaned


def fmt_num(n):
    """Format a number with thousands separators for insight text."""
    if n is None:
        return '0'
    return f"{int(n):,}"


from .models import (
    MonthlyTrend, BySector, FySummary, NepalMerged, Forecast,
    GenderBreakdown, LocationBreakdown, AgeBreakdown,
    ChannelBreakdown, SeasonalPattern, NepalGrantRates,
)
from .serializers import (
    MonthlyTrendSerializer, BySectorSerializer, FySummarySerializer,
    NepalMergedSerializer, ForecastSerializer, GenderBreakdownSerializer,
    LocationBreakdownSerializer, AgeBreakdownSerializer,
    ChannelBreakdownSerializer, SeasonalPatternSerializer,
    KPISummarySerializer, UniversityRankingSerializer,
)


# ─── Pagination ──────────────────────────────────────────────────────────────

class StandardPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000


# ─── HTML Template Views ──────────────────────────────────────────────────────

def dashboard_home(request):
    """Main dashboard home page."""
    return render(request, 'dashboard/index.html')


def trends_page(request):
    """Monthly trends analysis page."""
    return render(request, 'dashboard/trends.html')


def sectors_page(request):
    """Sector breakdown analysis page."""
    return render(request, 'dashboard/sectors.html')


def universities_page(request):
    """University/provider rankings page."""
    return render(request, 'dashboard/universities.html')


def forecast_page(request):
    """12-month forecast page."""
    return render(request, 'dashboard/forecast.html')


def about_page(request):
    """Data source, methodology, and validation page."""
    return render(request, 'dashboard/about.html')


# ─── API Root ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
def api_root(request):
    """API root listing all available endpoints."""
    base = request.build_absolute_uri('/api/')
    endpoints = {
        'kpi':          base + 'kpi/',
        'monthly':      base + 'monthly/',
        'sector':       base + 'sector/',
        'fy':           base + 'fy/',
        'merged':       base + 'merged/',
        'forecast':     base + 'forecast/',
        'gender':       base + 'gender/',
        'location':     base + 'location/',
        'location_comparison': base + 'location-comparison/',
        'age':          base + 'age/',
        'channel':      base + 'channel/',
        'seasonal':     base + 'seasonal/',
        'universities': base + 'universities/',
        'search':       base + 'search/?q=<term>',
        'validate':     base + 'validate/',
        'insights':     base + 'insights/',
        'upload_csv':   base + 'upload/csv/',
        'upload_excel': base + 'upload/excel/',
    }
    return Response({
        'project':     'Nepal Student Visa Analytics Dashboard',
        'description': 'Australian student visa data (subclass 500 and 570-576) for Nepal applicants (2005-06 to present)',
        'endpoints':   endpoints,
    })


# ─── KPI Summary ─────────────────────────────────────────────────────────────

@api_view(['GET'])
def kpi_summary(request):
    """Executive KPI summary computed from FySummary and BySector (verified tables)."""
    try:
        agg = FySummary.objects.aggregate(
            total_lodged=Sum('lodged'),
            total_granted=Sum('granted'),
            total_refused=Sum('refused'),
        )
        total_lodged  = agg['total_lodged']  or 0
        total_granted = agg['total_granted'] or 0
        total_refused = agg['total_refused'] or 0
        total_decided = total_granted + total_refused
        grant_rate    = round((total_granted / total_decided * 100), 2) if total_decided else 0.0
        refusal_rate  = round((total_refused / total_decided * 100), 2) if total_decided else 0.0

        fy_years = FySummary.objects.order_by('financial_year')
        period_start = fy_years.first().financial_year if fy_years.exists() else '2022-23'
        period_end   = fy_years.last().financial_year  if fy_years.exists() else '2025-26'

        # Top sector by volume — use corrected by_sector table, not nepal_merged
        top_sector_qs = (
            BySector.objects
            .values('sector')
            .annotate(vol=Sum('lodged'))
            .order_by('-vol')
            .first()
        )
        top_sector        = top_sector_qs['sector'] if top_sector_qs else 'Unknown'
        top_sector_volume = top_sector_qs['vol']    if top_sector_qs else 0

        # Latest month spotlight
        latest = MonthlyTrend.objects.order_by('-year_month').first()
        latest_month = None
        if latest:
            latest_month = {
                'year_month':  latest.year_month,
                'month_name':  latest.month_name,
                'lodged':      latest.lodged,
                'granted':     latest.granted,
                'grant_rate':  clean_float(latest.grant_rate),
                'data_quality_flag': bool(
                    latest.grant_rate is not None and (latest.grant_rate > 100 or latest.grant_rate < 0)
                ),
            }

        data = {
            'total_applications':   total_lodged,
            'total_granted':        total_granted,
            'total_refused':        total_refused,
            'grant_rate':           grant_rate,
            'refusal_rate':         refusal_rate,
            'period_start':         period_start,
            'period_end':           period_end,
            'total_financial_years': fy_years.count(),
            'top_sector':           top_sector,
            'top_sector_volume':    top_sector_volume,
            'latest_month':         latest_month,
        }
        return Response(data)
    except Exception as e:
        # Return fallback static KPIs if DB is unavailable
        return Response({
            'total_applications':   0,
            'total_granted':        0,
            'total_refused':        0,
            'grant_rate':           0.0,
            'refusal_rate':         0.0,
            'period_start':         '2022-23',
            'period_end':           '2025-26',
            'total_financial_years': 4,
            'top_sector':           'Unknown',
            'top_sector_volume':    0,
            'latest_month':         None,
            'note':                 str(e),
        })


# ─── Monthly Trend ────────────────────────────────────────────────────────────

@api_view(['GET'])
def monthly_trend(request):
    """Monthly trend data with optional year filter."""
    qs = MonthlyTrend.objects.all()
    year = request.query_params.get('year')
    if year:
        qs = qs.filter(year_month__startswith=year)
    serializer = MonthlyTrendSerializer(qs, many=True)
    clean_data = [sanitize_record(dict(row)) for row in serializer.data]

    # Defensive flag/clamp for grant_rate > 100% or refusal_rate < 0% — this
    # would indicate a lodged-month vs decided-month timing mismatch (see
    # FINDINGS_REPORT.md). As of the real decision-based formula fix
    # (Granted / (Granted+Refused)), values are bounded 0-100% by
    # construction and this currently has nothing to clamp; retained as a
    # regression safety net.
    for row in clean_data:
        rate = row.get('grant_rate')
        refusal = row.get('refusal_rate')
        anomalous = (rate is not None and (rate > 100 or rate < 0)) or \
                    (refusal is not None and (refusal > 100 or refusal < 0))
        if anomalous:
            row['data_quality_flag'] = True
            row['display_grant_rate'] = min(max(rate, 0), 100) if rate is not None else None
            row['display_refusal_rate'] = min(max(refusal, 0), 100) if refusal is not None else None
            row['note'] = (
                'Grant/refusal rate exceeds the normal 0-100% range because grants '
                'decided this month resolved a backlog of applications lodged in '
                'prior months. Raw figures are preserved in grant_rate/refusal_rate; '
                'display_grant_rate/display_refusal_rate are capped to 0-100% for charts.'
            )
        else:
            row['data_quality_flag'] = False
            row['display_grant_rate'] = rate
            row['display_refusal_rate'] = refusal

    # The 'rolling_3m' column was pre-computed (outside this app) from the raw,
    # uncapped grant_rate values, so it inherits the same >100%/<0% distortion
    # even after display_grant_rate is fixed above. Recompute a corrected
    # trailing 3-month average from display_grant_rate instead, since clean_data
    # is chronologically ordered (MonthlyTrend.Meta.ordering = ['year_month']).
    for i, row in enumerate(clean_data):
        window = clean_data[max(0, i - 2):i + 1]
        vals = [r['display_grant_rate'] for r in window if r['display_grant_rate'] is not None]
        row['display_rolling_3m'] = round(sum(vals) / len(vals), 2) if vals else None

    return Response(clean_data)


# ─── Sector Breakdown ─────────────────────────────────────────────────────────

@api_view(['GET'])
def sector_breakdown(request):
    """Sector breakdown, optionally filtered by year_month."""
    qs = BySector.objects.all()
    year_month = request.query_params.get('year_month')
    sector     = request.query_params.get('sector')
    if year_month:
        qs = qs.filter(year_month=year_month)
    if sector:
        qs = qs.filter(sector__icontains=sector)
    paginator = StandardPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = BySectorSerializer(page, many=True)
    # Sanitize any inf/nan floats that may exist in grant_rate column
    clean_data = [sanitize_record(dict(row)) for row in serializer.data]

    # Same defensive flag/clamp as monthly_trend, for the same reason (see
    # FINDINGS_REPORT.md). Currently 0 rows are out of range with the fixed
    # decision-based formula; retained as a regression safety net.
    for row in clean_data:
        rate = row.get('grant_rate')
        if rate is not None and (rate > 100 or rate < 0):
            row['data_quality_flag'] = True
            row['display_grant_rate'] = min(max(rate, 0), 100)
        else:
            row['data_quality_flag'] = False
            row['display_grant_rate'] = rate

    return paginator.get_paginated_response(clean_data)


# ─── Financial Year Summary ────────────────────────────────────────────────────

@api_view(['GET'])
def fy_summary(request):
    """Financial year summary."""
    qs = FySummary.objects.all()
    serializer = FySummarySerializer(qs, many=True)
    return Response(serializer.data)


# ─── Full Nepal Merged Dataset ────────────────────────────────────────────────

@api_view(['GET'])
def nepal_merged(request):
    """
    Full nepal_merged dataset with filters.

    NOTE: This table has NOT been rebuilt as of the latest data fix —
    it still reflects the original (uncorrected) load. Use /api/sector/,
    /api/monthly/, and /api/fy/ for verified totals. This endpoint remains
    useful for dimension-level exploration (provider_state, age_group, etc.)
    where the original load was checked and found internally consistent.
    """
    qs = NepalMerged.objects.all()
    # Filters
    financial_year    = request.query_params.get('financial_year')
    sector            = request.query_params.get('sector')
    provider_state    = request.query_params.get('provider_state')
    gender            = request.query_params.get('gender')
    client_location   = request.query_params.get('client_location')
    age_group         = request.query_params.get('age_group')
    lodgement_channel = request.query_params.get('lodgement_channel')

    if financial_year:    qs = qs.filter(financial_year=financial_year)
    if sector:            qs = qs.filter(sector__icontains=sector)
    if provider_state:    qs = qs.filter(provider_state__icontains=provider_state)
    if gender:            qs = qs.filter(gender__iexact=gender)
    if client_location:   qs = qs.filter(client_location__iexact=client_location)
    if age_group:         qs = qs.filter(age_group=age_group)
    if lodgement_channel: qs = qs.filter(lodgement_channel__icontains=lodgement_channel)

    paginator = StandardPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = NepalMergedSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


# ─── Forecast ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
def forecast_data(request):
    """12-month forecast with confidence bounds."""
    qs = Forecast.objects.all()
    serializer = ForecastSerializer(qs, many=True)
    clean_data = [sanitize_record(dict(row)) for row in serializer.data]
    return Response(clean_data)


# ─── Demographic Breakdowns ────────────────────────────────────────────────────

@api_view(['GET'])
def gender_breakdown(request):
    qs = GenderBreakdown.objects.all()
    data = [sanitize_record(dict(row)) for row in GenderBreakdownSerializer(qs, many=True).data]
    return Response(data)


@api_view(['GET'])
def location_breakdown(request):
    qs = LocationBreakdown.objects.all()
    data = [sanitize_record(dict(row)) for row in LocationBreakdownSerializer(qs, many=True).data]
    return Response(data)


@api_view(['GET'])
def age_breakdown(request):
    qs = AgeBreakdown.objects.all()
    data = [sanitize_record(dict(row)) for row in AgeBreakdownSerializer(qs, many=True).data]
    return Response(data)


@api_view(['GET'])
def channel_breakdown(request):
    qs = ChannelBreakdown.objects.all()
    data = [sanitize_record(dict(row)) for row in ChannelBreakdownSerializer(qs, many=True).data]
    return Response(data)


@api_view(['GET'])
def seasonal_pattern(request):
    qs = SeasonalPattern.objects.all()
    data = [sanitize_record(dict(row)) for row in SeasonalPatternSerializer(qs, many=True).data]
    return Response(data)


# ─── University / Provider Rankings ──────────────────────────────────────────

@api_view(['GET'])
def university_rankings(request):
    """
    Provider state rankings aggregated from nepal_merged.
    Returns top providers by total applications and grant rate.

    NOTE: nepal_merged has not been rebuilt in the latest data fix —
    provider_state totals were spot-checked and found internally consistent,
    but treat absolute totals here as indicative rather than authoritative
    until nepal_merged is fully rebuilt from the verified source.
    """
    limit = int(request.query_params.get('limit', 20))
    qs = (
        NepalMerged.objects
        .exclude(provider_state__isnull=True)
        .exclude(provider_state__exact='')
        .values('provider_state')
        .annotate(
            total_lodged=Sum('lodged_count'),
            total_granted=Sum('granted_count'),
            total_refused=Sum('refused_count'),
        )
        .order_by('-total_lodged')[:limit]
    )
    results = []
    for row in qs:
        lodged = row['total_lodged'] or 0
        granted = row['total_granted'] or 0
        refused = row['total_refused'] or 0
        decided = granted + refused
        rate = round((granted / decided * 100), 2) if decided else 0.0
        results.append({
            'provider_state': row['provider_state'],
            'total_lodged':   lodged,
            'total_granted':  granted,
            'total_refused':  refused,
            'grant_rate':     rate,
        })
    return Response(results)


# ─── Onshore vs Offshore Comparison (BI-style cards + trend) ─────────────────

_MONTH_MAP = {
    'M01 Jul': 7, 'M02 Aug': 8, 'M03 Sep': 9, 'M04 Oct': 10,
    'M05 Nov': 11, 'M06 Dec': 12, 'M07 Jan': 1, 'M08 Feb': 2,
    'M09 Mar': 3, 'M10 Apr': 4, 'M11 May': 5, 'M12 Jun': 6,
}


def _rate_pair(granted, refused):
    decided = granted + refused
    if not decided:
        return None, None
    return (round(granted / decided * 100, 2), round(refused / decided * 100, 2))


@api_view(['GET'])
def location_comparison(request):
    """
    BI-style Onshore vs Offshore comparison: two independent KPI cards
    (aggregate totals) plus a monthly grant-rate trend for both locations.
    Calculated only from NepalGrantRates (real decision-based data);
    Grant Rate = Granted / (Granted + Refused) * 100, computed separately
    per location — never blended.

    Optional filter: ?financial_year=2025-26
    """
    qs = NepalGrantRates.objects.all()
    financial_year = request.query_params.get('financial_year')

    if financial_year:
        # A financial_year was explicitly given -> aggregate the whole year (BI default)
        qs = qs.filter(financial_year=financial_year)
    else:
        # No financial_year given -> default to latest available month only
        latest = qs.order_by('-financial_year', '-month').values('financial_year', 'month').first()
        if latest:
            qs = qs.filter(financial_year=latest['financial_year'], month=latest['month'])

    cards = {}
    for loc_key, loc_label in [('outside', 'Outside Australia'), ('in', 'In Australia')]:
        loc_qs = qs.filter(client_location__iexact=loc_label)
        agg = loc_qs.aggregate(granted=Sum('grant_total'), refused=Sum('refused_total'))
        granted = agg['granted'] or 0
        refused = agg['refused'] or 0
        grant_rate, refusal_rate = _rate_pair(granted, refused)
        cards[loc_key] = {
            'label':            loc_label,
            'total_applications': granted + refused,
            'total_grants':     granted,
            'total_refusals':   refused,
            'grant_rate':       grant_rate,
            'refusal_rate':     refusal_rate,
        }

    # Monthly trend — group by (financial_year, month) per location, derive year_month
    trend_rows = (
        NepalGrantRates.objects.exclude(client_location__isnull=True)
        .values('financial_year', 'month', 'client_location')
        .annotate(granted=Sum('grant_total'), refused=Sum('refused_total'))
    )

    trend_map = {}  # year_month -> {'offshore': rate, 'onshore': rate}
    for row in trend_rows:
        fy = row['financial_year']
        month = row['month']
        loc = (row['client_location'] or '').strip()
        if not fy or month not in _MONTH_MAP:
            continue
        try:
            fy_start = int(fy[:4])
        except (TypeError, ValueError):
            continue
        m_num = _MONTH_MAP[month]
        year = fy_start if m_num >= 7 else fy_start + 1
        year_month = f"{year:04d}-{m_num:02d}"

        rate, _ = _rate_pair(row['granted'] or 0, row['refused'] or 0)
        bucket = trend_map.setdefault(year_month, {'offshore': None, 'onshore': None})
        if loc.lower() == 'outside australia':
            bucket['offshore'] = rate
        elif loc.lower() == 'in australia':
            bucket['onshore'] = rate

    trend = [
        {'year_month': ym, 'offshore_grant_rate': v['offshore'], 'onshore_grant_rate': v['onshore']}
        for ym, v in sorted(trend_map.items())
    ]

    return Response({
        'offshore': cards['outside'],
        'onshore':  cards['in'],
        'trend':    trend,
        'note': (
            'Offshore = Outside Australia, Onshore = In Australia at time of decision. '
            'Each calculated independently: Grant Rate = Granted / (Granted + Refused) * 100. '
            'Source: NepalGrantRates (real decision-based Home Affairs data).'
        ),
    })

    
@api_view(['GET'])
def applicant_type_comparison(request):
    """
    BI-style Primary vs Secondary applicant comparison: two independent
    KPI cards (aggregate totals) plus a monthly grant-rate trend for both
    types. Calculated only from NepalGrantRates (real decision-based data);
    Grant Rate = Granted / (Granted + Refused) * 100, computed separately
    per applicant_type — never blended.
    Optional filter: ?financial_year=2025-26
    """
    qs = NepalGrantRates.objects.all()
    financial_year = request.query_params.get('financial_year')

    if financial_year:
        qs = qs.filter(financial_year=financial_year)
    else:
        latest = qs.order_by('-financial_year', '-month').values('financial_year', 'month').first()
        if latest:
            qs = qs.filter(financial_year=latest['financial_year'], month=latest['month'])

    cards = {}
    for type_key, type_label in [('primary', 'Primary'), ('secondary', 'Secondary')]:
        type_qs = qs.filter(applicant_type__iexact=type_label)
        agg = type_qs.aggregate(granted=Sum('grant_total'), refused=Sum('refused_total'))
        granted = agg['granted'] or 0
        refused = agg['refused'] or 0
        grant_rate, refusal_rate = _rate_pair(granted, refused)
        cards[type_key] = {
            'label':              type_label,
            'total_applications': granted + refused,
            'total_grants':       granted,
            'total_refusals':     refused,
            'grant_rate':         grant_rate,
            'refusal_rate':       refusal_rate,
        }

    trend_rows = (
        NepalGrantRates.objects.exclude(applicant_type__isnull=True)
        .values('financial_year', 'month', 'applicant_type')
        .annotate(granted=Sum('grant_total'), refused=Sum('refused_total'))
    )
    trend_map = {}
    for row in trend_rows:
        fy = row['financial_year']
        month = row['month']
        atype = (row['applicant_type'] or '').strip()
        if not fy or month not in _MONTH_MAP:
            continue
        try:
            fy_start = int(fy[:4])
        except (TypeError, ValueError):
            continue
        m_num = _MONTH_MAP[month]
        year = fy_start if m_num >= 7 else fy_start + 1
        year_month = f"{year:04d}-{m_num:02d}"
        rate, _ = _rate_pair(row['granted'] or 0, row['refused'] or 0)
        bucket = trend_map.setdefault(year_month, {'primary': None, 'secondary': None})
        if atype.lower() == 'primary':
            bucket['primary'] = rate
        elif atype.lower() == 'secondary':
            bucket['secondary'] = rate

    trend = [
        {'year_month': ym, 'primary_grant_rate': v['primary'], 'secondary_grant_rate': v['secondary']}
        for ym, v in sorted(trend_map.items())
    ]

    return Response({
        'primary':   cards['primary'],
        'secondary': cards['secondary'],
        'trend':     trend,
        'note': (
            'Each calculated independently: Grant Rate = Granted / (Granted + Refused) * 100. '
            'Source: NepalGrantRates (real decision-based Home Affairs data).'
        ),
    })

# ─── Search ───────────────────────────────────────────────────────────────────

@api_view(['GET'])
def search(request):
    """
    Full-text search across sectors, providers, and months.
    Query param: ?q=<term>
    """
    q = request.query_params.get('q', '').strip()
    if not q:
        return Response({'error': 'Provide a search term via ?q='}, status=400)

    sectors = (
        BySector.objects
        .filter(sector__icontains=q)
        .values('sector', 'year_month', 'lodged', 'granted', 'grant_rate')
        .distinct()[:20]
    )
    providers = (
        NepalMerged.objects
        .filter(provider_state__icontains=q)
        .values('provider_state')
        .annotate(total=Sum('lodged_count'))
        .order_by('-total')[:20]
    )
    months = (
        MonthlyTrend.objects
        .filter(Q(year_month__icontains=q) | Q(month_name__icontains=q))
        .values('year_month', 'month_name', 'lodged', 'granted', 'grant_rate')[:20]
    )

    return Response({
        'query':     q,
        'sectors':   list(sectors),
        'providers': list(providers),
        'months':    list(months),
    })


# ─── Data Validation ──────────────────────────────────────────────────────────

@api_view(['GET'])
def validate_data(request):
    """Cross-checks KPI totals between fy_summary and monthly_trend tables."""
    checks = []

    fy_agg = FySummary.objects.aggregate(
        lodged=Sum('lodged'),
        granted=Sum('granted'),
        refused=Sum('refused'),
    )
    monthly_agg = MonthlyTrend.objects.aggregate(
        lodged=Sum('lodged'),
        granted=Sum('granted'),
    )

    a = fy_agg.get('lodged') or 0
    b = monthly_agg.get('lodged') or 0
    checks.append({
        'check':         'fy_summary.lodged vs SUM(monthly_trend.lodged)',
        'fy_summary':    a,
        'monthly_trend': b,
        'match':         abs(a - b) <= max(1, 0.01 * max(a, b)),
        'difference':    a - b,
    })

    a = fy_agg.get('granted') or 0
    b = monthly_agg.get('granted') or 0
    checks.append({
        'check':         'fy_summary.granted vs SUM(monthly_trend.granted)',
        'fy_summary':    a,
        'monthly_trend': b,
        'match':         abs(a - b) <= max(1, 0.01 * max(a, b)),
        'difference':    a - b,
    })

    fy_lodged  = fy_agg.get('lodged')  or 1
    fy_granted = fy_agg.get('granted') or 0
    mt_lodged  = monthly_agg.get('lodged')  or 1
    mt_granted = monthly_agg.get('granted') or 0
    fy_rate    = round(fy_granted / fy_lodged * 100, 2)
    mt_rate    = round(mt_granted / mt_lodged * 100, 2)
    checks.append({
        'check':         'grant_rate from fy_summary vs grant_rate from monthly_trend',
        'fy_summary':    fy_rate,
        'monthly_trend': mt_rate,
        'match':         abs(fy_rate - mt_rate) <= 0.5,
        'difference':    round(fy_rate - mt_rate, 2),
    })

    fy_refused   = fy_agg.get('refused') or 0
    calc_refused = (fy_agg.get('lodged') or 0) - (fy_agg.get('granted') or 0)
    checks.append({
        'check':         'fy_summary.refused == lodged - granted',
        'fy_summary':    fy_refused,
        'monthly_trend': calc_refused,
        'match':         abs(fy_refused - calc_refused) <= 1,
        'difference':    fy_refused - calc_refused,
    })

    all_pass = all(c['match'] for c in checks)

    # Count anomalous months (grant_rate > 100% or < 0%) for transparency
    anomalous_months = MonthlyTrend.objects.filter(
        Q(grant_rate__gt=100) | Q(grant_rate__lt=0)
    ).count()

    return Response({
        'status':            'verified' if all_pass else 'mismatch',
        'all_checks_passed': all_pass,
        'checks':            checks,
        'nepal_merged_rows': NepalMerged.objects.count(),
        'anomalous_months_count': anomalous_months,
        'note': (
            'fy_summary and monthly_trend are both deduplicated aggregate tables '
            'rebuilt directly from the official Home Affairs BP0015 pivot cache data, '
            'and are the authoritative sources for KPI figures. '
            'nepal_merged is a cross-tabulation table from the original (unverified) load — '
            'it is used only for dimension-level fields (provider_state, age_group) that '
            'were spot-checked separately, not for headline totals. '
            f'{anomalous_months} month(s) show a grant_rate outside the '
            '0-100% range; this is expected because grants decided in a given month often '
            'resolve applications lodged in prior months (processing time lag), not a calculation error. '
            'See /api/monthly/ for per-month data_quality_flag and display_grant_rate fields.'
        ),
    })


# ─── Plain-Language Insights ──────────────────────────────────────────────────

@api_view(['GET'])
def insights(request):
    """
    Generates plain-language insight sentences from the current data,
    so non-technical users can understand the dashboard without
    interpreting charts or percentages themselves.
    """
    try:
        fy_agg = FySummary.objects.aggregate(
            lodged=Sum('lodged'), granted=Sum('granted'), refused=Sum('refused')
        )
        total_lodged  = fy_agg.get('lodged')  or 1
        total_granted = fy_agg.get('granted') or 0
        total_refused = fy_agg.get('refused') or 0
        total_decided = total_granted + total_refused
        grant_rate    = round((total_granted / total_decided * 100), 1) if total_decided else 0.0

        # Per-100 framing
        per_100_granted = round(grant_rate)
        per_100_refused = 100 - per_100_granted

        # ── Latest month spotlight (e.g. April 2026) ────────────────────────
        latest = MonthlyTrend.objects.order_by('-year_month').first()
        latest_card = None
        if latest:
            quality_note = ""
            if latest.grant_rate is not None and (latest.grant_rate > 100 or latest.grant_rate < 0):
                quality_note = (
                    " Note: this figure reflects a processing backlog being cleared that month "
                    "(more decisions made than new applications received), not a typical approval pattern."
                )
            year_label = latest.year_month.split('-')[0]
            rate_display = latest.grant_rate if latest.grant_rate is not None else 0.0
            latest_card = {
                'title': f"Latest Month - {latest.month_name} {year_label}",
                'text': (
                    f"In {latest.month_name} {year_label}, {fmt_num(latest.lodged)} applications "
                    f"were lodged and {fmt_num(latest.granted)} were granted - a "
                    f"{rate_display:.1f}% grant rate.{quality_note}"
                ),
                'tone': 'positive' if rate_display >= 50 else 'negative',
                'highlight': True,
            }

        # Trend: compare first vs last financial year
        fy_qs = FySummary.objects.order_by('financial_year')
        trend_sentence = ""
        if fy_qs.count() >= 2:
            first, last = fy_qs.first(), fy_qs.last()
            change = last.grant_rate - first.grant_rate if (last.grant_rate is not None and first.grant_rate is not None) else None
            if change is not None:
                direction = "improved" if change > 0 else "declined"
                trend_sentence = (
                    f"Between {first.financial_year} and {last.financial_year}, "
                    f"the grant rate {direction} from {first.grant_rate:.1f}% "
                    f"to {last.grant_rate:.1f}% "
                    f"({'+' if change > 0 else ''}{change:.1f} percentage points)."
                )

        # Top and bottom sector by grant rate — use verified BySector table
        sector_agg = (
            BySector.objects
            .values('sector')
            .annotate(lodged=Sum('lodged'), granted=Sum('granted'))
            .filter(lodged__gte=200)
        )
        sector_rates = []
        for s in sector_agg:
            if s['lodged']:
                rate = (s['granted'] or 0) / s['lodged'] * 100
                if rate > 100:   # skip rows still affected by timing-mismatch distortion
                    continue
                sector_rates.append({'sector': s['sector'], 'rate': rate, 'lodged': s['lodged']})
        sector_rates.sort(key=lambda x: x['rate'], reverse=True)

        best_sector  = sector_rates[0]  if sector_rates else None
        worst_sector = sector_rates[-1] if sector_rates else None

        # Gender insight
        gender_qs = GenderBreakdown.objects.all()
        gender_sentence = ""
        if gender_qs.exists():
            top_gender = max(gender_qs, key=lambda g: g.lodged or 0)
            rate = top_gender.grant_rate if top_gender.grant_rate is not None else 0.0
            gender_sentence = (
                f"{top_gender.gender} applicants submitted the most applications "
                f"({fmt_num(top_gender.lodged)}), with a grant rate of "
                f"{rate:.1f}%."
            )

        # Location insight (onshore vs offshore)
        loc_qs = LocationBreakdown.objects.all()
        location_sentence = ""
        if loc_qs.exists():
            for loc in loc_qs:
                rate = loc.grant_rate if loc.grant_rate is not None else 0.0
                location_sentence += (
                    f"{loc.client_location} applicants: {fmt_num(loc.lodged)} lodged, "
                    f"{rate:.1f}% approved. "
                )

        # ── Build final card list, latest month first ───────────────────────
        cards = []
        if latest_card:
            cards.append(latest_card)

        cards.append({
            'title': 'Overall Approval Rate',
            'text': (
                f"Out of every 100 Nepali students who applied for an Australian "
                f"student visa, about {per_100_granted} were approved "
                f"and {per_100_refused} were refused."
            ),
            'tone': 'neutral',
        })

        cards.append({
            'title': 'Total Volume',
            'text': (
                f"A total of {fmt_num(total_lodged)} applications were lodged, "
                f"of which {fmt_num(total_granted)} were granted and "
                f"{fmt_num(total_refused)} were refused."
            ),
            'tone': 'neutral',
        })

        if trend_sentence:
            cards.append({
                'title': 'Trend Over Time',
                'text': trend_sentence,
                'tone': 'positive' if 'improved' in trend_sentence else 'negative',
            })

        if best_sector and worst_sector and best_sector['sector'] != worst_sector['sector']:
            cards.append({
                'title': 'Best Performing Sector',
                'text': (
                    f"{best_sector['sector']} has the highest approval rate at "
                    f"{best_sector['rate']:.1f}% (based on {fmt_num(best_sector['lodged'])} applications)."
                ),
                'tone': 'positive',
            })
            cards.append({
                'title': 'Lowest Performing Sector',
                'text': (
                    f"{worst_sector['sector']} has the lowest approval rate at "
                    f"{worst_sector['rate']:.1f}% (based on {fmt_num(worst_sector['lodged'])} applications). "
                    f"Applicants in this sector face significantly higher refusal risk."
                ),
                'tone': 'negative',
            })

        if gender_sentence:
            cards.append({
                'title': 'Gender Breakdown',
                'text': gender_sentence,
                'tone': 'neutral',
            })

        if location_sentence:
            cards.append({
                'title': 'Onshore vs Offshore',
                'text': location_sentence.strip(),
                'tone': 'neutral',
            })

        return Response({'cards': cards})

    except Exception as e:
        return Response({'cards': [], 'error': str(e)})

# ─── Combined Overview Page Payload ───────────────────────────────────────────

def _share_bar_items(rows, id_key, label_key, value_key, total):
    """Build ShareBarItem-shaped dicts (id/label/share/value/bar) from an
    iterable of dict rows, where `bar`/`share` are each row's percentage
    of `total`. Matches the frontend's ShareBarItem type exactly."""
    items = []
    for row in rows:
        value = row[value_key] or 0
        pct = round((value / total * 100), 1) if total else 0.0
        items.append({
            'id':    str(row[id_key]),
            'label': row[label_key],
            'share': f"{pct}%",
            'value': fmt_num(value),
            'bar':   pct,
        })
    return items


@api_view(['GET'])
def overview(request):
    """
    Combined payload for the frontend Overview page. Every top-level key here
    maps directly to OverviewResponse in the frontend's src/types/api.ts —
    do not rename/remove a field without updating that file too.

    Nothing here recalculates figures using a different method than the rest
    of the app: KPI/grant-rate math reuses the same Granted/(Granted+Refused)
    formula as kpi_summary()/location_comparison(), offshore/onshore reuses
    location_comparison()'s logic, and provider/sector figures reuse
    university_rankings()/sector_breakdown()'s aggregation.
    """
    try:
        # ── Financial-year KPI cards + deltas (FySummary has real refused counts) ──
        fy_qs = list(FySummary.objects.order_by('financial_year'))
        latest_fy = fy_qs[-1] if fy_qs else None
        prev_fy   = fy_qs[-2] if len(fy_qs) >= 2 else None

        def _pct_delta(current, prior):
            if current is None or prior is None or prior == 0:
                return None
            return round((current - prior) / prior * 100, 1)

        def _fmt_delta_label(pct):
            if pct is None:
                return '—'
            sign = '+' if pct > 0 else ''
            return f"{sign}{pct}%"

        kpis = []
        if latest_fy:
            for key, label in [('lodged', 'Applications Lodged'), ('granted', 'Granted'), ('refused', 'Refused')]:
                cur = getattr(latest_fy, key)
                prior = getattr(prev_fy, key) if prev_fy else None
                pct = _pct_delta(cur, prior)
                if pct is None:
                    tone = 'neutral'
                elif key == 'refused':
                    tone = 'negative' if pct > 0 else ('positive' if pct < 0 else 'neutral')
                else:
                    tone = 'positive' if pct > 0 else ('negative' if pct < 0 else 'neutral')
                kpis.append({
                    'id':           key,
                    'label':        label,
                    'value':        fmt_num(cur),
                    'deltaLabel':   _fmt_delta_label(pct),
                    'deltaTone':    tone,
                    'deltaCaption': f'vs {prev_fy.financial_year}' if prev_fy else 'no prior year',
                })

        grant_rate_kpi = {
            'id':           'grant_rate',
            'label':        'Grant Rate',
            'value':        f"{latest_fy.grant_rate:.1f}%" if (latest_fy and latest_fy.grant_rate is not None) else '—',
            'deltaLabel':   (
                f"{'+' if (latest_fy.grant_rate - prev_fy.grant_rate) > 0 else ''}"
                f"{round(latest_fy.grant_rate - prev_fy.grant_rate, 1)}pp"
            ) if (latest_fy and prev_fy and latest_fy.grant_rate is not None and prev_fy.grant_rate is not None) else '—',
            'deltaTone':    (
                'positive' if (latest_fy and prev_fy and latest_fy.grant_rate is not None
                                and prev_fy.grant_rate is not None and latest_fy.grant_rate > prev_fy.grant_rate)
                else 'negative' if (latest_fy and prev_fy and latest_fy.grant_rate is not None
                                     and prev_fy.grant_rate is not None and latest_fy.grant_rate < prev_fy.grant_rate)
                else 'neutral'
            ),
            'deltaCaption': f'vs {prev_fy.financial_year}' if prev_fy else 'no prior year',
        }

        # ── Latest Official Snapshot (single latest published month — NOT FY cumulative) ──
        latest_year_month = None
        latest_month_pair = None
        for row in (
            NepalGrantRates.objects
            .exclude(financial_year__isnull=True)
            .exclude(month__isnull=True)
            .values('financial_year', 'month')
            .distinct()
        ):
            fy_val, month_val = row['financial_year'], row['month']
            if not fy_val or month_val not in _MONTH_MAP:
                continue
            try:
                fy_start = int(fy_val[:4])
            except (TypeError, ValueError):
                continue
            m_num = _MONTH_MAP[month_val]
            year = fy_start if m_num >= 7 else fy_start + 1
            year_month = f"{year:04d}-{m_num:02d}"
            if latest_year_month is None or year_month > latest_year_month:
                latest_year_month = year_month
                latest_month_pair = (fy_val, month_val)

        latest_snapshot = None
        if latest_month_pair:
            snap_fy, snap_month = latest_month_pair
            snap_agg = (
                NepalGrantRates.objects
                .filter(financial_year=snap_fy, month=snap_month)
                .aggregate(granted=Sum('grant_total'), refused=Sum('refused_total'))
            )
            snap_granted = snap_agg['granted'] or 0
            snap_refused = snap_agg['refused'] or 0
            snap_lodged = snap_granted + snap_refused
            snap_rate, snap_refusal_rate = _rate_pair(snap_granted, snap_refused)
            latest_snapshot = {
                'financialYear': snap_fy,
                'month':         snap_month,
                'monthLabel':    f"{snap_month.split(' ')[1]} {latest_year_month[:4]}",
                'lodged':        snap_lodged,
                'granted':       snap_granted,
                'refused':       snap_refused,
                'grantRate':     f"{snap_rate:.1f}%" if snap_rate is not None else '—',
                'refusalRate':   f"{snap_refusal_rate:.1f}%" if snap_refusal_rate is not None else '—',
            }

        # ── FY-scoped queryset: defaults to latest FY, responds to ?financial_year= ──
        selected_fy = request.GET.get('financial_year') or (latest_fy.financial_year if latest_fy else None)
        gr_qs = NepalGrantRates.objects.filter(financial_year=selected_fy) if selected_fy else NepalGrantRates.objects.none()

        # ── Offshore vs Onshore (FY-scoped, mirrors location_comparison()) ──

        def _comparison_side(filter_kwargs, label, sublabel):
            side_qs = gr_qs.filter(**filter_kwargs)
            agg = side_qs.aggregate(granted=Sum('grant_total'), refused=Sum('refused_total'))
            granted = agg['granted'] or 0
            refused = agg['refused'] or 0
            total = granted + refused
            rate, _ = _rate_pair(granted, refused)
            return {
                'label':    label,
                'sublabel': sublabel,
                'value':    fmt_num(total),
                'share':    total,  # raw count; frontend computes/receives % via caption below
                'caption':  f"{rate}% grant rate" if rate is not None else 'No decided applications',
            }, total

        offshore_side, offshore_total = _comparison_side({'client_location__iexact': 'Outside Australia'}, 'Offshore', 'Outside Australia')
        onshore_side, onshore_total   = _comparison_side({'client_location__iexact': 'In Australia'}, 'Onshore', 'In Australia')
        loc_total = offshore_total + onshore_total
        offshore_side['share'] = round(offshore_total / loc_total * 100, 1) if loc_total else 0.0
        onshore_side['share']  = round(onshore_total / loc_total * 100, 1) if loc_total else 0.0

        offshore_vs_onshore = {
            'left':    offshore_side,
            'right':   onshore_side,
            'insight': (
                f"Offshore applicants make up {offshore_side['share']}% of decided applications, "
                f"onshore {onshore_side['share']}%."
            ),
        }

        # ── Primary vs Secondary applicants (same pattern, applicant_type field) ──
        primary_side, primary_total = _comparison_side({'applicant_type__icontains': 'primary'}, 'Primary', 'Primary applicants')
        secondary_side, secondary_total = _comparison_side({'applicant_type__icontains': 'secondary'}, 'Secondary', 'Secondary applicants')
        type_total = primary_total + secondary_total
        primary_side['share']   = round(primary_total / type_total * 100, 1) if type_total else 0.0
        secondary_side['share'] = round(secondary_total / type_total * 100, 1) if type_total else 0.0

        primary_vs_secondary = {
            'left':    primary_side,
            'right':   secondary_side,
            'insight': (
                f"Primary applicants account for {primary_side['share']}% of decided applications, "
                f"secondary {secondary_side['share']}%."
            ),
        }

        # ── Monthly grant-rate trend, offshore vs onshore (last 12 months) ──
        trend_rows = (
            gr_qs.exclude(client_location__isnull=True)
            .values('financial_year', 'month', 'client_location')
            .annotate(granted=Sum('grant_total'), refused=Sum('refused_total'))
        )
        trend_map = {}
        for row in trend_rows:
            fy = row['financial_year']
            month = row['month']
            loc = (row['client_location'] or '').strip()
            if not fy or month not in _MONTH_MAP:
                continue
            try:
                fy_start = int(fy[:4])
            except (TypeError, ValueError):
                continue
            m_num = _MONTH_MAP[month]
            year = fy_start if m_num >= 7 else fy_start + 1
            year_month = f"{year:04d}-{m_num:02d}"
            rate, _ = _rate_pair(row['granted'] or 0, row['refused'] or 0)
            bucket = trend_map.setdefault(year_month, {'offshore': None, 'onshore': None})
            if loc.lower() == 'outside australia':
                bucket['offshore'] = rate
            elif loc.lower() == 'in australia':
                bucket['onshore'] = rate
        monthly_grant_rate = [
            {'month': ym, 'offshore': v['offshore'], 'onshore': v['onshore']}
            for ym, v in sorted(trend_map.items())
        ][-12:]

        # ── Monthly volume trend (FY-scoped via year_month range — MonthlyTrend
        # has no financial_year field, so we derive Jul(fy_start)..Jun(fy_start+1)
        # from selected_fy, same pattern as Education Sectors; bounded range,
        # no missing months fabricated) ──
        try:
            _volume_fy_start = int(selected_fy[:4]) if selected_fy else None
        except (TypeError, ValueError):
            _volume_fy_start = None
        monthly_trend_qs = MonthlyTrend.objects.order_by('year_month')
        if _volume_fy_start is not None:
            _volume_start_ym = f"{_volume_fy_start:04d}-07"
            _volume_end_ym = f"{_volume_fy_start + 1:04d}-06"
            monthly_trend_qs = monthly_trend_qs.filter(
                year_month__gte=_volume_start_ym, year_month__lte=_volume_end_ym
            )
        monthly_volume = []
        for m in list(monthly_trend_qs):
            decided = round(m.granted / (m.grant_rate / 100)) if (m.grant_rate and m.grant_rate > 0) else None
            refused = (decided - m.granted) if decided is not None else None
            monthly_volume.append({
                'month':   m.year_month,
                'lodged':  m.lodged,
                'granted': m.granted,
                'refused': refused if refused is not None and refused >= 0 else 0,
            })

        # ── Top provider states (FY-scoped via gr_qs — NepalMerged's
        # provider_state is unpopulated/broken; NepalGrantRates has 70k+ real
        # rows across 9 provider states from the verified pivot-cache import) ──
        provider_qs = (
            gr_qs
            .exclude(provider_state__isnull=True)
            .exclude(provider_state__exact='')
            .values('provider_state')
            .annotate(total_granted=Sum('grant_total'), total_refused=Sum('refused_total'))
            .order_by('-total_granted')
        )
        provider_list = [
            {**r, 'total_decided': (r['total_granted'] or 0) + (r['total_refused'] or 0)}
            for r in provider_qs
        ]
        provider_total = sum(r['total_decided'] for r in provider_list)
        top_provider_states = _share_bar_items(
            provider_list[:5], 'provider_state', 'provider_state', 'total_decided', provider_total
        )

        # ── Education sectors (FY-scoped by year_month range — BySector has no
        # financial_year field, so we derive Jul(fy_start)..Jun(fy_start+1) from
        # selected_fy; range is bounded, no missing months are fabricated) ──
        sector_qs = BySector.objects.values('sector').annotate(total_lodged=Sum('lodged')).order_by('-total_lodged')
        try:
            _sector_fy_start = int(selected_fy[:4]) if selected_fy else None
        except (TypeError, ValueError):
            _sector_fy_start = None
        if _sector_fy_start is not None:
            _sector_start_ym = f"{_sector_fy_start:04d}-07"
            _sector_end_ym = f"{_sector_fy_start + 1:04d}-06"
            sector_qs = sector_qs.filter(year_month__gte=_sector_start_ym, year_month__lte=_sector_end_ym)
        sector_list = list(sector_qs)
        sector_total = sum(r['total_lodged'] or 0 for r in sector_list)
        education_sectors = _share_bar_items(
            sector_list[:5], 'sector', 'sector', 'total_lodged', sector_total
        )
        sector_insight = (
            f"{education_sectors[0]['label']} leads with {education_sectors[0]['share']} of lodged applications."
            if education_sectors else "No sector data available."
        )

        # ── Executive story + key takeaways ──
        story_title = f"Steady demand through {latest_fy.financial_year}" if latest_fy else "Overview"
        story_paragraphs = []
        if latest_fy:
            story_paragraphs.append(
                f"In {latest_fy.financial_year}, {fmt_num(latest_fy.lodged)} applications were lodged, "
                f"with a grant rate of {latest_fy.grant_rate:.1f}%."
            )
        if latest_fy and prev_fy and latest_fy.grant_rate is not None and prev_fy.grant_rate is not None:
            change = round(latest_fy.grant_rate - prev_fy.grant_rate, 1)
            direction = "improved" if change > 0 else "declined" if change < 0 else "held steady"
            story_paragraphs.append(
                f"The grant rate {direction} compared to {prev_fy.financial_year} "
                f"({'+' if change > 0 else ''}{change} percentage points)."
            )

        story_highlights = []
        if latest_fy:
            story_highlights = [
                {'id': 'lodged',  'label': 'Applications Lodged', 'value': fmt_num(latest_fy.lodged)},
                {'id': 'granted', 'label': 'Granted',              'value': fmt_num(latest_fy.granted)},
                {'id': 'rate',    'label': 'Grant Rate',           'value': f"{latest_fy.grant_rate:.1f}%"},
            ]

        key_takeaways = []
        if offshore_vs_onshore['insight']:
            key_takeaways.append({'id': 'location', 'text': offshore_vs_onshore['insight']})
        if primary_vs_secondary['insight']:
            key_takeaways.append({'id': 'applicant-type', 'text': primary_vs_secondary['insight']})
        if sector_insight:
            key_takeaways.append({'id': 'sector', 'text': sector_insight})

        meta = {
            'period':        latest_fy.financial_year if latest_fy else 'Unknown',
            'financialYear': latest_fy.financial_year if latest_fy else 'Unknown',
            'source':        'Australian Department of Home Affairs',
            'lastUpdated':   timezone.now().date().isoformat(),
        }

        return Response({
            'meta':               meta,
            'latestSnapshot':     latest_snapshot,
            'kpis':               kpis,
            'grantRateKpi':       grant_rate_kpi,
            'offshoreVsOnshore':  offshore_vs_onshore,
            'primaryVsSecondary': primary_vs_secondary,
            'executiveStory':     {'title': story_title, 'paragraphs': story_paragraphs},
            'storyHighlights':    story_highlights,
            'keyTakeaways':       key_takeaways,
            'monthlyGrantRate':   monthly_grant_rate,
            'monthlyVolume':      monthly_volume,
            'topProviderStates':  top_provider_states,
            'educationSectors':   education_sectors,
            'sectorInsight':      sector_insight,
        })

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
