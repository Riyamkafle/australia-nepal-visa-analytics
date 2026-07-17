"""
Filter nepal_merged_real.csv to match the LinkedIn comparison exactly:
offshore (Client Location = 'Outside Australia'), Primary applicants only,
for April 2026 — and compare against the reported real-world figures:
  Total lodged: 1,626 (Primary: 1,212, Secondary: 414)
  Total granted: 838 (Primary: 248, Secondary: 590)
  Primary applicant grant rate: 36.1%

Usage:
    python verify_offshore_primary.py
"""
import pandas as pd

df = pd.read_csv('nepal_merged_real.csv')

april = df[df['year_month'] == '2026-04']

print("─── All April 2026 combined (onshore + offshore, all applicant types) ───")
print(f"Lodged: {april['lodged_count'].sum():,}  Granted: {april['granted_count'].sum():,}")

print("\n─── Breakdown by client_location ───")
loc_breakdown = april.groupby('client_location')[['lodged_count', 'granted_count']].sum()
print(loc_breakdown)

print("\n─── Breakdown by applicant_type (within Outside Australia only) ───")
offshore = april[april['client_location'] == 'Outside Australia']
type_breakdown = offshore.groupby('applicant_type')[['lodged_count', 'granted_count']].sum()
print(type_breakdown)

print("\n─── Offshore + Primary only (matches LinkedIn comparison) ───")
offshore_primary = offshore[offshore['applicant_type'] == 'Primary']
lodged  = offshore_primary['lodged_count'].sum()
granted = offshore_primary['granted_count'].sum()
rate = granted / lodged * 100 if lodged else 0
print(f"Lodged: {lodged:,}   (LinkedIn reported: 1,212)")
print(f"Granted: {granted:,}   (LinkedIn reported: 248)")
print(f"Grant rate: {rate:.1f}%   (LinkedIn reported: 36.1%)")