# Synthetic data generator (Phase 1)

Deterministic, seeded generator for PakManufacture Pvt Ltd's synthetic business history.
Lives entirely under `synthetic_data/generator/`, outside the backend app, so Phase 2's
ingestion pipeline consumes it the same way it would consume a real export.

## Generating data

```bash
make generate-data                      # seed=42, writes to synthetic_data/output/
make generate-data SEED=7 OUT=/tmp/alt   # override seed and output path
```

or directly:

```bash
PYTHONPATH=synthetic_data backend/.venv/bin/python -m generator \
  --seed 42 --output synthetic_data/output
```

Flags: `--seed` (int, default 42), `--output` (path), `--scale` (float, default 1.0 -
shrinks customer/employee counts and sales-line volume proportionally, with floors, for
fast test runs), `--no-messy` (skip the messy variant), `--skip-verify` (skip the built-in
integrity checks).

## Locked decisions

January 2023 - December 2025 (36 months), PKR, calendar-year fiscal start - enforced by
`GeneratorConfig`'s field validators (`start_month`, `months`, `currency` all raise
`ValueError` on any other value).

## Output layout

```
synthetic_data/output/
  clean/            18 CSV tables - the primary, well-formed dataset
  messy/            the same tables with deliberate data-quality defects (unless --no-messy)
  _hidden/
    ground_truth.yaml      planted-problem answer key - NEVER read by backend/app or any API
    messy_defects.yaml     manifest of injected defects - NEVER read by backend/app or any API
```

`tests/synthetic/test_isolation.py` statically greps `backend/app/` source for any mention
of `ground_truth`, `generator.measure`, `generator.planted`, or `messy_defects` and fails the
build if found - this is checked independently of whether any test happens to exercise the
code path that would leak it.

## Entities (seed-independent catalog)

| Entity | Count |
|---|---|
| Regions | 5 |
| Product categories | 4 |
| Products | 25 |
| Suppliers | 12 |
| Raw materials | 8 |
| Plants | 3 |
| Production lines | 9 |
| Customers | 300 (scales with `--scale`) |
| Employees | 250 (scales with `--scale`) |

## Row counts at `scale=1.0`, seed 42

| Table | Rows |
|---|---|
| sales | 185,400 |
| payroll | 9,000 |
| production / inventory | 900 each |
| procurement | 864 |
| overtime | 324 |
| expenses | 540 |

Sales volume is controlled by `_BASE_LINES_PER_MONTH` in `sales.py`, calibrated to land
near the middle of the Phase 1 spec's 150k-300k target band.

## Mechanisms

- **Determinism**: every random draw comes from a named stream (`rng.py`), derived from
  `SeedSequence([seed, crc32(stream_name)])`. Adding a new random draw anywhere in the
  codebase can never perturb a different, unrelated component's numbers for the same seed.
- **Seasonality**: a fixed calendar-month multiplier (`macro.py`) peaking ahead of
  Eid/summer and the winter home-textile season, troughing in the monsoon low season.
- **Inflation / FX**: CPI compounds at ~0.6%/month (~+24% cumulative over 36 months); PKR
  depreciates against USD at ~0.4%/month. Both are shared macro facts, not seed-dependent.
- **Customer concentration**: a fixed Zipf curve (`rank ** -0.85`) with *randomised rank
  assignment per seed - the degree of concentration is seed-robust, but which specific
  customer is the "whale" is not.
- **Demand growth**: a company-wide linear ramp (+60% by the final month) plus an extra,
  convex ramp specifically for CAT-02 (Knitwear) - this is what eventually pushes the
  Knitting line (LINE-05) toward capacity and ties the overtime problem to a real,
  causally-connected demand story rather than an arbitrary label.
- **No-backlog production**: every product except the one planted overstock product is
  produced to order each month (production ratio ~= shipments); finished-goods inventory is
  rebuilt purely from written production/shipment flows (`closing = opening + produced -
  shipped`), so the stock identity is trivially re-checkable from the output files alone.

## Planted problems (ground truth, seed 42, `scale=1.0`)

| ID | Problem | Entities | Target band | As generated |
|---|---|---|---|---|
| GT-01 | Procurement cost increase, concentrated | SUP-04 / MAT-01 | +12% to +24% | **+15.58%** |
| GT-02 | Regional sales decline | REG-05 (Balochistan) | -35% to -10% | **-25.78%** |
| GT-03 | Product margin deterioration | PROD-12 | +5pp to +18pp | **+12.16pp** |
| GT-04 | Overtime rise, one line/staffing gap | LINE-05 (Knitting 2, Plant 2) | 50-1600 hrs/mo (2025 Q4 avg) | **924.61 hrs/mo** |
| GT-05 | Inventory overstock | PROD-20 | 2.0-7.0 months of cover (2025 Q4 avg) | **2.42 months** |

GT-01 is measured on the *CPI-deflated* unit price (see DECISIONS.md #3) - comparing nominal
prices instead conflates the planted, supplier-specific repricing with three years of macro
inflation and overstates the effect by roughly 3x.

## Red herrings

| ID | Pattern | Why it's a trap |
|---|---|---|
| RH-01 | PROD-04 spikes every Mar/Apr | Seasonal (Ramadan/Eid), not a trend - reverts every year |
| RH-02 | SUP-11 has a one-month price spike (2024-03) | Fully reverts the next month - not sustained like GT-01 |
| RH-03 | REG-02 has one weak month (2023-08) | No underlying trend - not a decline like GT-02 |

## Messy dataset (data-quality defects)

Built from a copy of the clean tables via `messy.py`, using its own deterministic RNG
stream. Defects (manifest hidden in `_hidden/messy_defects.yaml`): missing values
(`discount_pct`, `region_id`), duplicate records (verbatim re-appended rows, same
`sale_id`), invalid dates (malformed `order_date` strings), impossible numeric values
(negative quantities, zero prices), inconsistent categorical values (casing/spelling
variants of `payment_terms`), suspicious outliers (quantity inflated ~500x on a handful of
rows), referential-integrity violations (`customer_id` pointing at a non-existent
`CUST-9999`), and a schema inconsistency (`net_amount_pkr` renamed to `net_amount` in the
messy variant only).

## Known limitations

- Red herrings (3) are illustrative, not exhaustive - a real dataset would have more subtle
  traps than a synthetic generator can practically enumerate.
- GT-04's magnitude band is intentionally wide (50-1600 hrs/month) to reflect genuine
  cross-seed variance in the random product-popularity permutation interacting with a
  capacity threshold; the *qualitative* signal (zero overtime in year one, material overtime
  in the final year, every tested seed) is the robust claim, not a tight number.
- Procurement unit prices carry no random noise (only quantity does), so GT-01's measured
  value is identical across seeds - a deliberate simplification (repricing is modelled as a
  deterministic contract/policy effect), not a bug.

## Tests

| File | Covers |
|---|---|
| `test_config.py` | Locked fields reject overrides; `effective_sizes` scaling/floors |
| `test_dataset_shape.py` | Required entities, 36 months, row-count band, no future dates, PKR, arithmetic |
| `test_determinism.py` | Same seed -> identical tables; different seed -> different; shared static catalog |
| `test_planted_problems.py` | All 5 GT issues land in band; GT-01 deflation regression test |
| `test_integrity.py` | Mutation tests - each `verify_tables()` check is tripped by the specific corruption it should catch |
| `test_ground_truth.py` | Structure/consistency of `ground_truth.yaml`, red herrings present |
| `test_messy.py` | Every injected defect type is present and documented; `--no-messy` is honoured |
| `test_isolation.py` | Static source-grep: `app/` never mentions hidden fixtures |
| `test_cli.py` | `python -m generator` subprocess: runs, respects `--no-messy`, seed changes output |
