"""
Backtest the exact method used in build_forecast.py: pretend "today" is
12 months before the real latest month, run the identical linear-trend +
seasonal-adjustment method to "forecast" that already-known 12-month
window, then compare against what actually happened.

This is a single honest out-of-sample check using the production method
itself -- not a fabricated confidence score. It answers one question:
"When this method has been used before, how far off was it, on average?"

Usage:
    python backtest_forecast.py
"""
import pandas as pd
import numpy as np

OUT_DIR = 'data sources'
HOLDOUT_MONTHS = 12
RECENT_WINDOW = 24

mt = pd.read_csv(f'{OUT_DIR}/monthly_trend.csv').sort_values('year_month').reset_index(drop=True)
seasonal = pd.read_csv(f'{OUT_DIR}/seasonal_pattern.csv')

if len(mt) < HOLDOUT_MONTHS + RECENT_WINDOW:
    raise SystemExit(f"Not enough history: need at least {HOLDOUT_MONTHS + RECENT_WINDOW} months, have {len(mt)}")

# Split: train on everything except the last 12 real months, which become
# the held-out "actual" values we compare the replayed forecast against.
train = mt.iloc[:-HOLDOUT_MONTHS].copy()
actual_holdout = mt.iloc[-HOLDOUT_MONTHS:].copy().reset_index(drop=True)

recent = train.tail(RECENT_WINDOW).copy()
recent['t'] = range(len(recent))

lodged_coef = np.polyfit(recent['t'], recent['lodged'], 1)
lodged_trend_fn = np.poly1d(lodged_coef)

seasonal_avg_overall = seasonal['avg_lodged'].mean()
seasonal['multiplier'] = seasonal['avg_lodged'] / seasonal_avg_overall

rate_coef = np.polyfit(recent['t'], recent['grant_rate'], 1)
rate_trend_fn = np.poly1d(rate_coef)
rate_std = recent['grant_rate'].std()

rows = []
t = len(recent)
for i in range(HOLDOUT_MONTHS):
    actual_row = actual_holdout.iloc[i]
    cal_month = int(actual_row['cal_month'])

    lodged_base = max(lodged_trend_fn(t), 0)
    seas_mult = seasonal.loc[seasonal['cal_month'] == cal_month, 'multiplier'].values
    seas_mult = seas_mult[0] if len(seas_mult) else 1.0
    lodged_forecast = round(lodged_base * seas_mult)

    rate_forecast = min(max(rate_trend_fn(t), 0), 100)
    band_width = rate_std * (1 + i * 0.08)
    lower_bound = round(min(max(rate_forecast - band_width, 0), 100), 1)
    upper_bound = round(min(max(rate_forecast + band_width, 0), 100), 1)

    actual_lodged = actual_row['lodged']
    actual_rate = actual_row['grant_rate']

    lodged_error = abs(lodged_forecast - actual_lodged)
    rate_error = abs(round(rate_forecast, 1) - actual_rate)
    within_band = lower_bound <= actual_rate <= upper_bound

    rows.append({
        'year_month': actual_row['year_month'],
        'forecast_lodged': lodged_forecast,
        'actual_lodged': actual_lodged,
        'lodged_abs_error': lodged_error,
        'forecast_rate': round(rate_forecast, 1),
        'actual_rate': actual_rate,
        'rate_abs_error_pp': round(rate_error, 1),
        'predicted_range': f"{lower_bound}-{upper_bound}",
        'actual_within_range': within_band,
    })
    t += 1

result = pd.DataFrame(rows)
print("─── Backtest: replaying build_forecast.py's method against the real last 12 months ───\n")
print(result.to_string(index=False))

mae_lodged = result['lodged_abs_error'].mean()
mae_rate = result['rate_abs_error_pp'].mean()
coverage = result['actual_within_range'].sum()

print(f"\n─── Summary ───")
print(f"Mean absolute error (lodged volume): {mae_lodged:.0f} applications/month")
print(f"Mean absolute error (grant rate): {mae_rate:.1f} percentage points/month")
print(f"Months where actual grant rate fell within the predicted range: {coverage} of {HOLDOUT_MONTHS}")
