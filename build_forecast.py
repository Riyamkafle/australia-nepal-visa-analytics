"""
Build a real 12-month forecast from the rebuilt monthly_trend.csv
(21 years of real data), replacing the old synthetic forecast.csv.

Method (simple, transparent, not a black box):
  - Lodged volume: linear trend fit on the last 24 months, adjusted by
    the seasonal_pattern.csv calendar-month multiplier (so December's
    forecast reflects December's typical seasonal shape, not just the
    raw trend line).
  - Grant rate: linear trend fit on the last 24 months of grant_rate,
    clipped to 0-100%.
  - Confidence bounds: +/- 1 standard deviation of the last 24 months'
    grant_rate, clipped to 0-100%, widening slightly further out.

This is intentionally simple and explainable rather than a opaque ML
model, since the audience for this dashboard needs to trust and
understand the forecast, not just consume a number.

Usage:
    python build_forecast.py
"""
import pandas as pd
import numpy as np

OUT_DIR = 'data sources'

mt = pd.read_csv(f'{OUT_DIR}/monthly_trend.csv').sort_values('year_month').reset_index(drop=True)
seasonal = pd.read_csv(f'{OUT_DIR}/seasonal_pattern.csv')

RECENT_WINDOW = 24
recent = mt.tail(RECENT_WINDOW).copy()
recent['t'] = range(len(recent))

# ── Lodged trend (linear regression) ────────────────────────────────────
lodged_coef = np.polyfit(recent['t'], recent['lodged'], 1)
lodged_trend_fn = np.poly1d(lodged_coef)

# Seasonal multiplier per calendar month, relative to the recent average
seasonal_avg_overall = seasonal['avg_lodged'].mean()
seasonal['multiplier'] = seasonal['avg_lodged'] / seasonal_avg_overall

# ── Grant rate trend (linear regression) ────────────────────────────────
rate_coef = np.polyfit(recent['t'], recent['grant_rate'], 1)
rate_trend_fn = np.poly1d(rate_coef)
rate_std = recent['grant_rate'].std()

print(f"Lodged trend: {lodged_coef[0]:+.1f} per month (recent {RECENT_WINDOW}-month slope)")
print(f"Grant rate trend: {rate_coef[0]:+.2f} pp per month (recent {RECENT_WINDOW}-month slope)")
print(f"Grant rate volatility (std dev): {rate_std:.2f} pp")

# ── Generate next 12 months ──────────────────────────────────────────────
last_year, last_month = map(int, mt.iloc[-1]['year_month'].split('-'))
MONTH_NAMES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
    7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December',
}

rows = []
t = len(recent)  # continue the trend line from where 'recent' left off
year, month = last_year, last_month
for i in range(12):
    month += 1
    if month > 12:
        month = 1
        year += 1
    year_month = f"{year:04d}-{month:02d}"
    month_label = f"{MONTH_NAMES[month]} {year}"

    lodged_base = max(lodged_trend_fn(t), 0)
    seas_mult = seasonal.loc[seasonal['cal_month'] == month, 'multiplier'].values
    seas_mult = seas_mult[0] if len(seas_mult) else 1.0
    lodged_forecast = round(lodged_base * seas_mult)

    rate_forecast = min(max(rate_trend_fn(t), 0), 100)
    # widen the confidence band slightly the further out we forecast
    band_width = rate_std * (1 + i * 0.08)
    lower_bound = round(min(max(rate_forecast - band_width, 0), 100), 1)
    upper_bound = round(min(max(rate_forecast + band_width, 0), 100), 1)

    granted_forecast = round(lodged_forecast * rate_forecast / 100)
    refused_forecast  = lodged_forecast - granted_forecast

    rows.append({
        'year_month': year_month,
        'month_label': month_label,
        'lodged_forecast': lodged_forecast,
        'granted_forecast': granted_forecast,
        'refused_forecast': refused_forecast,
        'grant_rate_forecast': round(rate_forecast, 1),
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'model_note': (
            f'Linear trend on last {RECENT_WINDOW} months of real BP0015 data, '
            f'seasonally adjusted by calendar month; band = +/-1 std dev, widening with horizon.'
        ),
    })
    t += 1

forecast = pd.DataFrame(rows)
print("\n─── Forecast preview ───")
print(forecast[['year_month', 'lodged_forecast', 'granted_forecast', 'grant_rate_forecast', 'lower_bound', 'upper_bound']].to_string())

forecast.to_csv(f'{OUT_DIR}/forecast.csv', index=False)
print(f"\nSaved to {OUT_DIR}/forecast.csv ({len(forecast)} rows)")