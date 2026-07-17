"""
Merge nepal_lodged_extracted.csv + nepal_granted_extracted.csv into one
real, verified dataset — matching rows on every shared dimension, summing
counts, and computing grant/refusal rates.

Usage:
    python merge_nepal_data.py
"""
import pandas as pd

DIMENSIONS = [
    'financial_year', 'fy_quarter', 'month', 'client_location',
    'lodgement_channel', 'sector', 'applicant_type', 'provider_state',
    'gender', 'citizenship_country', 'age_group',
]

print("Loading extracted files...")
lodged  = pd.read_csv('nepal_lodged_extracted.csv')
granted = pd.read_csv('nepal_granted_extracted.csv')

print(f"Lodged rows:  {len(lodged):,}  (sum={lodged['lodged_count'].sum():,})")
print(f"Granted rows: {len(granted):,}  (sum={granted['granted_count'].sum():,})")

# Granted file has one extra column (last_visa_category) — drop it for the
# merge since Lodged has no equivalent; group granted by the shared
# dimensions first so multiple visa-category rows collapse into one count.
granted_grouped = (
    granted.groupby(DIMENSIONS, as_index=False)['granted_count'].sum()
)
lodged_grouped = (
    lodged.groupby(DIMENSIONS, as_index=False)['lodged_count'].sum()
)

print(f"\nAfter grouping — Lodged: {len(lodged_grouped):,} unique combos, "
      f"Granted: {len(granted_grouped):,} unique combos")

# Outer join: keep every combination that appears in EITHER file
merged = pd.merge(lodged_grouped, granted_grouped, on=DIMENSIONS, how='outer')
merged['lodged_count']  = merged['lodged_count'].fillna(0).astype(int)
merged['granted_count'] = merged['granted_count'].fillna(0).astype(int)
merged['refused_count'] = (merged['lodged_count'] - merged['granted_count']).clip(lower=0)

# Grant rate per combo — undefined (NaN) where lodged_count is 0, not divide-by-zero
merged['grant_rate_calc'] = merged.apply(
    lambda r: round(r['granted_count'] / r['lodged_count'] * 100, 2) if r['lodged_count'] > 0 else None,
    axis=1
)
merged['refusal_rate_calc'] = merged['grant_rate_calc'].apply(
    lambda v: round(100 - v, 2) if v is not None else None
)

# Derive year_month from financial_year + month (e.g. 2005-06 + M01 Jul -> 2005-07)
MONTH_MAP = {
    'M01 Jul': 7, 'M02 Aug': 8, 'M03 Sep': 9, 'M04 Oct': 10,
    'M05 Nov': 11, 'M06 Dec': 12, 'M07 Jan': 1, 'M08 Feb': 2,
    'M09 Mar': 3, 'M10 Apr': 4, 'M11 May': 5, 'M12 Jun': 6,
}
def compute_year_month(row):
    fy_start = int(row['financial_year'][:4])  # e.g. '2005-06' -> 2005
    m_num = MONTH_MAP.get(row['month'])
    if m_num is None:
        return None
    year = fy_start if m_num >= 7 else fy_start + 1
    return f"{year:04d}-{m_num:02d}"

merged['year_month'] = merged.apply(compute_year_month, axis=1)

print(f"\nFinal merged shape: {merged.shape}")
print(f"Total lodged:  {merged['lodged_count'].sum():,}")
print(f"Total granted: {merged['granted_count'].sum():,}")
print(f"Total refused: {merged['refused_count'].sum():,}")
overall_rate = merged['granted_count'].sum() / merged['lodged_count'].sum() * 100
print(f"Overall grant rate: {overall_rate:.2f}%")

print("\n─── Preview ───")
print(merged.head(10).to_string())

merged.to_csv('nepal_merged_real.csv', index=False)
print("\nSaved to nepal_merged_real.csv")

# ── Quick sanity check: April 2026 specifically ─────────────────────────
april_2026 = merged[merged['year_month'] == '2026-04']
if len(april_2026):
    total_lodged  = april_2026['lodged_count'].sum()
    total_granted = april_2026['granted_count'].sum()
    rate = total_granted / total_lodged * 100 if total_lodged else 0
    print(f"\n─── April 2026 sanity check ───")
    print(f"Lodged: {total_lodged:,}  Granted: {total_granted:,}  Grant rate: {rate:.1f}%")
else:
    print("\n⚠ No April 2026 rows found — check year_month derivation.")