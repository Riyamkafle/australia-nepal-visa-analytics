"""
Views for the Nepal Student Visa Analytics Dashboard.
Includes both HTML template views and DRF API views.
"""

import math

from django.shortcuts import render
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
    ChannelBreakdown, SeasonalPattern,
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
        'description': 'Australian Subclass 500 visa data for Nepal applicants (2022-2026)',
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
        grant_rate    = round((total_granted / total_lodged * 100), 2) if total_lodged else 0.0
        refusal_rate  = round(100 - grant_rate, 2)

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

    # Flag months where grant_rate exceeds 100% — a known artifact of
    # lodged-month vs decided-month timing mismatch in the source data,
    # not a calculation error. See FINDINGS_REPORT.md for full explanation.
    for row in clean_data:
        rate = row.get('grant_rate')
        if rate is not None and (rate > 100 or rate < 0):
            row['data_quality_flag'] = True
            row['display_grant_rate'] = min(max(rate, 0), 100)
            row['note'] = (
                'Grant rate exceeds normal range because grants decided this '
                'month resolved a backlog of applications lodged in prior months. '
                'The raw figure is preserved in grant_rate; display_grant_rate is capped at 100%.'
            )
        else:
            row['data_quality_flag'] = False
            row['display_grant_rate'] = rate

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
        rate = round((granted / lodged * 100), 2) if lodged else 0.0
        results.append({
            'provider_state': row['provider_state'],
            'total_lodged':   lodged,
            'total_granted':  granted,
            'total_refused':  refused,
            'grant_rate':     rate,
        })
    return Response(results)


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
        grant_rate    = round((total_granted / total_lodged * 100), 1)

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
                f"Subclass 500 student visa, about {per_100_granted} were approved "
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