"""
Rebuild data sources/*.csv from the verified real extracted data:
  - nepal_lodged_extracted.csv      (real lodged counts, by lodged-month)
  - nepal_grant_rates_extracted.csv (real grant_total/refused_total, by DECISION-month)

Using grant_total/(grant_total+refused_total) means grant_rate is
mathematically bounded to 0-100% by construction — no capping needed,
because it's finally computed from actual decision outcomes instead of
naively dividing granted-this-month by lodged-this-month.

Produces: monthly_trend.csv, by_sector.csv, fy_summary.csv,
gender_breakdown.csv, location_breakdown.csv, age_breakdown.csv,
channel_breakdown.csv, seasonal_pattern.csv

NOTE: forecast.csv is NOT rebuilt here — that requires a forecasting
model over the new real trend, which is a separate follow-up step.

Usage:
    python rebuild_data_sources.py
"""
import pandas as pd
import os

OUT_DIR = 'data sources'
os.makedirs(OUT_DIR, exist_ok=True)

MONTH_MAP = {
    'M01 Jul': 7, 'M02 Aug': 8, 'M03 Sep': 9, 'M04 Oct': 10,
    'M05 Nov': 11, 'M06 Dec': 12, 'M07 Jan': 1, 'M08 Feb': 2,
    'M09 Mar': 3, 'M10 Apr': 4, 'M11 May': 5, 'M12 Jun': 6,
}
MONTH_NAMES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
    7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December',
}

def add_year_month(df):
    def compute(row):
        fy_start = int(row['financial_year'][:4])
        m_num = MONTH_MAP.get(row['month'])
        if m_num is None:
            return None
        year = fy_start if m_num >= 7 else fy_start + 1
        return f"{year:04d}-{m_num:02d}"
    df['year_month'] = df.apply(compute, axis=1)
    df['cal_month']  = df['year_month'].apply(lambda ym: int(ym.split('-')[1]) if ym else None)
    df['month_name'] = df['cal_month'].map(MONTH_NAMES)
    return df

print("Loading extracted files...")
lodged = pd.read_csv('nepal_lodged_extracted.csv')
rates  = pd.read_csv('nepal_grant_rates_extracted.csv')

lodged = add_year_month(lodged)
rates  = add_year_month(rates)

print(f"Lodged: {len(lodged):,} rows | Grant rates: {len(rates):,} rows\n")


# ── 1. monthly_trend.csv ────────────────────────────────────────────────
print("Building monthly_trend.csv...")
lodged_by_month = lodged.groupby('year_month', as_index=False)['lodged_count'].sum()
rates_by_month  = rates.groupby('year_month', as_index=False)[['grant_total', 'refused_total']].sum()

mt = pd.merge(lodged_by_month, rates_by_month, on='year_month', how='outer').sort_values('year_month')
mt['lodged_count']  = mt['lodged_count'].fillna(0).astype(int)
mt['grant_total']   = mt['grant_total'].fillna(0).astype(int)
mt['refused_total'] = mt['refused_total'].fillna(0).astype(int)
mt = mt.rename(columns={'lodged_count': 'lodged', 'grant_total': 'granted'})
decided = mt['granted'] + mt['refused_total']
mt['grant_rate']   = (mt['granted'] / decided * 100).round(2).where(decided > 0)
mt['refusal_rate'] = (mt['refused_total'] / decided * 100).round(2).where(decided > 0)
mt['cal_month']  = mt['year_month'].apply(lambda ym: int(ym.split('-')[1]))
mt['month_name'] = mt['cal_month'].map(MONTH_NAMES)
mt['rolling_3m'] = mt['grant_rate'].rolling(window=3, min_periods=1).mean().round(2)
mt_final = mt[['year_month', 'lodged', 'granted', 'grant_rate', 'refusal_rate', 'cal_month', 'month_name', 'rolling_3m']]
mt_final.to_csv(f'{OUT_DIR}/monthly_trend.csv', index=False)
print(f"  -> {len(mt_final)} rows. Grant rate range: {mt_final['grant_rate'].min():.1f}% to {mt_final['grant_rate'].max():.1f}% (should be within 0-100)")


# ── 2. by_sector.csv ────────────────────────────────────────────────────
print("\nBuilding by_sector.csv...")
lodged_by_sector = lodged.groupby(['year_month', 'sector'], as_index=False)['lodged_count'].sum()
rates_by_sector  = rates.groupby(['year_month', 'sector'], as_index=False)[['grant_total', 'refused_total']].sum()
bs = pd.merge(lodged_by_sector, rates_by_sector, on=['year_month', 'sector'], how='outer')
bs['lodged_count']  = bs['lodged_count'].fillna(0).astype(int)
bs['grant_total']   = bs['grant_total'].fillna(0).astype(int)
bs['refused_total'] = bs['refused_total'].fillna(0).astype(int)
bs = bs.rename(columns={'lodged_count': 'lodged', 'grant_total': 'granted'})
decided = bs['granted'] + bs['refused_total']
bs['grant_rate'] = (bs['granted'] / decided * 100).round(2).where(decided > 0)
bs = bs.sort_values(['year_month', 'sector']).reset_index(drop=True)
bs.insert(0, 'id', range(1, len(bs) + 1))
bs_final = bs[['id', 'year_month', 'sector', 'lodged', 'granted', 'grant_rate']]
bs_final.to_csv(f'{OUT_DIR}/by_sector.csv', index=False)
print(f"  -> {len(bs_final)} rows. Grant rate range: {bs_final['grant_rate'].min():.1f}% to {bs_final['grant_rate'].max():.1f}%")


# ── 3. fy_summary.csv ───────────────────────────────────────────────────
print("\nBuilding fy_summary.csv...")
lodged_by_fy = lodged.groupby('financial_year', as_index=False)['lodged_count'].sum()
rates_by_fy  = rates.groupby('financial_year', as_index=False)[['grant_total', 'refused_total']].sum()
fy = pd.merge(lodged_by_fy, rates_by_fy, on='financial_year', how='outer').sort_values('financial_year')
fy = fy.rename(columns={'lodged_count': 'lodged', 'grant_total': 'granted', 'refused_total': 'refused'})
decided = fy['granted'] + fy['refused']
fy['grant_rate']   = (fy['granted'] / decided * 100).round(2).where(decided > 0)
fy['refusal_rate'] = (fy['refused'] / decided * 100).round(2).where(decided > 0)
fy.to_csv(f'{OUT_DIR}/fy_summary.csv', index=False)
print(f"  -> {len(fy)} rows")


# ── 4. gender_breakdown.csv ─────────────────────────────────────────────
print("\nBuilding gender_breakdown.csv...")
lodged_by_gender = lodged.groupby('gender', as_index=False)['lodged_count'].sum()
rates_by_gender  = rates.groupby('gender', as_index=False)[['grant_total', 'refused_total']].sum()
gb = pd.merge(lodged_by_gender, rates_by_gender, on='gender', how='outer')
gb = gb.rename(columns={'lodged_count': 'lodged', 'grant_total': 'granted', 'refused_total': 'refused'})
decided = gb['granted'] + gb['refused']
gb['grant_rate'] = (gb['granted'] / decided * 100).round(2).where(decided > 0)
gb.to_csv(f'{OUT_DIR}/gender_breakdown.csv', index=False)
print(f"  -> {len(gb)} rows")


# ── 5. location_breakdown.csv ───────────────────────────────────────────
print("\nBuilding location_breakdown.csv...")
lodged_by_loc = lodged.groupby('client_location', as_index=False)['lodged_count'].sum()
rates_by_loc  = rates.groupby('client_location', as_index=False)[['grant_total', 'refused_total']].sum()
lb = pd.merge(lodged_by_loc, rates_by_loc, on='client_location', how='outer')
lb = lb.rename(columns={'lodged_count': 'lodged', 'grant_total': 'granted', 'refused_total': 'refused'})
decided = lb['granted'] + lb['refused']
lb['grant_rate'] = (lb['granted'] / decided * 100).round(2).where(decided > 0)
lb.to_csv(f'{OUT_DIR}/location_breakdown.csv', index=False)
print(f"  -> {len(lb)} rows")


# ── 6. age_breakdown.csv ────────────────────────────────────────────────
print("\nBuilding age_breakdown.csv...")
lodged_by_age = lodged.groupby('age_group', as_index=False)['lodged_count'].sum()
rates_by_age  = rates.groupby('age_group', as_index=False)[['grant_total', 'refused_total']].sum()
ab = pd.merge(lodged_by_age, rates_by_age, on='age_group', how='outer')
ab = ab.rename(columns={'lodged_count': 'lodged', 'grant_total': 'granted', 'refused_total': 'refused'})
decided = ab['granted'] + ab['refused']
ab['grant_rate'] = (ab['granted'] / decided * 100).round(2).where(decided > 0)
ab.insert(0, 'id', range(1, len(ab) + 1))
ab.to_csv(f'{OUT_DIR}/age_breakdown.csv', index=False)
print(f"  -> {len(ab)} rows")


# ── 7. channel_breakdown.csv ────────────────────────────────────────────
print("\nBuilding channel_breakdown.csv...")
lodged_by_ch = lodged.groupby('lodgement_channel', as_index=False)['lodged_count'].sum()
rates_by_ch  = rates.groupby('lodgement_channel', as_index=False)[['grant_total', 'refused_total']].sum()
cb = pd.merge(lodged_by_ch, rates_by_ch, on='lodgement_channel', how='outer')
cb = cb.rename(columns={'lodged_count': 'lodged', 'grant_total': 'granted', 'refused_total': 'refused'})
decided = cb['granted'] + cb['refused']
cb['grant_rate'] = (cb['granted'] / decided * 100).round(2).where(decided > 0)
cb.to_csv(f'{OUT_DIR}/channel_breakdown.csv', index=False)
print(f"  -> {len(cb)} rows")


# ── 8. seasonal_pattern.csv ─────────────────────────────────────────────
print("\nBuilding seasonal_pattern.csv...")
sp_lodged = lodged.groupby('cal_month', as_index=False)['lodged_count'].mean().rename(columns={'lodged_count': 'avg_lodged'})
sp_rates  = rates.groupby('cal_month', as_index=False)[['grant_total', 'refused_total']].mean().rename(
    columns={'grant_total': 'avg_grant', 'refused_total': 'avg_refused'})
sp = pd.merge(sp_lodged, sp_rates, on='cal_month', how='outer').sort_values('cal_month')
sp['month_name'] = sp['cal_month'].map(MONTH_NAMES)
sp['avg_lodged']  = sp['avg_lodged'].round(1)
sp['avg_grant']   = sp['avg_grant'].round(1)
sp['avg_refused'] = sp['avg_refused'].round(1)
sp_final = sp[['cal_month', 'month_name', 'avg_lodged', 'avg_grant', 'avg_refused']]
sp_final.to_csv(f'{OUT_DIR}/seasonal_pattern.csv', index=False)
print(f"  -> {len(sp_final)} rows")

print("\n✓ All CSVs rebuilt in 'data sources/' with real, verified data.")
print("  (forecast.csv was NOT touched — that needs a forecasting model, separate step)")