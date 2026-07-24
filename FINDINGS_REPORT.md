# Findings Report: Lodged-Month vs Decided-Month Timing Mismatch

## Summary

`grant_rate` and `refusal_rate` in the `monthly_trend` and `by_sector` tables
are calculated per calendar month. In principle this can produce values
outside the normal 0-100% range, because the applications *decided* (granted
or refused) in a given month are not necessarily the same applications
*lodged* in that month.

## Why this happens

A visa decision can land months (or years) after the original lodgement.
So for any single month:

- The **numerator** (grants + refusals *decided* this month) reflects a mix
  of applications lodged across many prior months.
- If the table instead divides against a **denominator** of applications
  *lodged* this month, the two numbers describe different cohorts of
  applicants entirely — they were never meant to be compared 1:1.

When a month clears an unusually large backlog of older decisions relative
to how many new applications were lodged that same month, the naive
`granted_this_month / lodged_this_month` calculation can exceed 100%, or
`refused_this_month / lodged_this_month` can behave unexpectedly. This is a
data-shape characteristic of monthly-bucketed lodged/decided data, not a
calculation bug in the traditional sense — but it does mean any formula
using `lodged` as a monthly denominator is fragile.

## The fix applied

As of commit `4b55b82` (and reinforced by the real decision-based pivot-cache
extraction added in `a6e8ee5`/`e809327`), every rate calculation in this
project uses only decided applications as the denominator:

```
Grant Rate   = Granted / (Granted + Refused) * 100
Refusal Rate = Refused / (Granted + Refused) * 100
```

This is mathematically bounded to 0-100% **by construction** — a ratio of a
part to a whole containing that part can never exceed the whole or fall
below zero. It cannot go out of range regardless of how the lodged/decided
cohorts line up across months, because `lodged` no longer appears in the
formula at all.

## Current status (as of this report)

Checked directly against the currently-generated `data sources/*.csv` files:

| File | Rows | grant_rate range | Rows outside 0-100% |
|---|---|---|---|
| `monthly_trend.csv` | 251 | 24.79% – 100.0% | 0 |
| `by_sector.csv` | 1,559 | 0.0% – 100.0% | 0 |

**No rows are currently out of range in either table.** An earlier version
of this codebase's comments (in `analytics/views.py`, `monthly_trend()` and
`sector_breakdown()`) cited "71 of 293 rows" as affected — that figure is
stale, from an earlier and much smaller dataset (293 rows total, predating
the full real 21-year extraction now in use) and does not reflect current
data. Those comments should be updated to avoid confusion.

## `display_grant_rate` / `display_refusal_rate` fields

`analytics/views.py`'s `monthly_trend()` and `sector_breakdown()` endpoints
still compute a `data_quality_flag` and clamp values into
`display_grant_rate` / `display_refusal_rate` fields (capped to 0-100%) for
safe charting, while preserving the raw `grant_rate` / `refusal_rate` fields
uncapped for data-quality auditing. This defensive logic is retained as a
safety net — it currently has nothing to clamp, since the underlying values
are already bounded by the fixed formula — but protects against any future
regression (e.g. if a data source is ever swapped back to a
lodged-denominator calculation by mistake).

## Recommendation

- Treat any future report of `grant_rate` or `refusal_rate` outside 0-100%
  as a genuine bug to investigate immediately (most likely: a denominator
  using `lodged` instead of `granted + refused` was reintroduced somewhere),
  not as an expected data artifact.
- Update the stale "71 of 293" comments in `analytics/views.py` to reflect
  current reality (0 rows out of range) or remove the specific figure
  entirely in favor of a reference to this report.