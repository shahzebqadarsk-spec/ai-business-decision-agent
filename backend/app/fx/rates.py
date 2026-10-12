"""Static, versioned snapshot of exchange rates, used to convert each row's *native*
transaction currency into the deployment's configured *reporting* currency.

This is a deliberately static reference table, not a live feed:
  - Every number here is manually curated and dated (`RATES_AS_OF`). It will drift from
    the real market rate the moment it's written, and nobody should treat it as current.
  - It is static on purpose, to match this project's "every number comes from deterministic
    analytics, never fabricated" discipline (see docs/DECISIONS.md): a live FX API call
    makes every downstream KPI non-reproducible run-to-run (today's rate != yesterday's
    rate for the exact same uploaded file) and this sandboxed environment's egress
    allowlist usually can't reach arbitrary FX APIs anyway (see root CLAUDE/README notes
    on the proxy allowlist), so a live feed would silently fail at the worst possible
    layer -- after materialization looks like it succeeded.
  - If/when a live-feed or paid FX data source is wired in later, it should REPLACE the
    body of `rate_to_usd()` behind the exact same function signature -- nothing calling
    this module needs to change.

Rates are stored as "units of currency per 1 USD" (a standard indirect quote), and every
conversion pivots through USD: amount_in_X -> USD -> amount_in_Y. This needs one rate per
currency instead of one per *pair* of currencies.

To refresh this table: update `RATES_AS_OF` and the affected entries together, in one
commit, and re-run `tests/fx/test_rates.py` (it checks the table's own internal
consistency, not real-world accuracy -- only a human can judge that).
"""

from __future__ import annotations

from datetime import date

# Last time this table was manually reviewed/updated. Treat anything older than a few
# months as a reason to double check before relying on it for a real decision.
RATES_AS_OF: date = date(2026, 1, 1)

# Units of currency per 1 USD, as of RATES_AS_OF. Pegged currencies (AED, SAR, QAR, BHD,
# KWD) are genuinely stable; floating ones (PKR, TRY, NGN, ZAR especially) move a lot and
# this snapshot should be refreshed more often for those if real decisions ride on them.
_RATES_PER_USD: dict[str, float] = {
    "USD": 1.0,
    "PKR": 278.50,
    "EUR": 0.92,
    "GBP": 0.79,
    "INR": 83.20,
    "AED": 3.6725,
    "SAR": 3.75,
    "QAR": 3.64,
    "BHD": 0.376,
    "KWD": 0.307,
    "OMR": 0.3845,
    "CNY": 7.20,
    "JPY": 150.0,
    "AUD": 1.52,
    "CAD": 1.37,
    "SGD": 1.34,
    "CHF": 0.88,
    "TRY": 34.0,
    "BDT": 110.0,
    "NGN": 1550.0,
    "ZAR": 18.5,
    "LKR": 300.0,
    "NPR": 133.0,
    "AFN": 70.0,
    "MYR": 4.47,
    "IDR": 15700.0,
    "THB": 34.5,
    "KRW": 1330.0,
    "HKD": 7.82,
    "NZD": 1.64,
    "SEK": 10.4,
    "NOK": 10.6,
    "DKK": 6.85,
    "RUB": 92.0,
    "EGP": 48.5,
    "KES": 129.0,
}

SUPPORTED_CURRENCIES: frozenset[str] = frozenset(_RATES_PER_USD)


class UnsupportedCurrencyError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(
            f"No FX rate for currency code '{code}'. Supported: {sorted(SUPPORTED_CURRENCIES)}. "
            "Add it to app/fx/rates.py (with a source and date) rather than guessing a rate."
        )


def rate_to_usd(currency_code: str) -> float:
    """Units of `currency_code` per 1 USD. Raises UnsupportedCurrencyError rather than
    guessing for anything not in the table -- same 'never fabricate' rule as the rest of
    the ingestion pipeline."""
    code = currency_code.strip().upper()
    try:
        return _RATES_PER_USD[code]
    except KeyError:
        raise UnsupportedCurrencyError(code) from None


__all__ = [
    "RATES_AS_OF",
    "SUPPORTED_CURRENCIES",
    "UnsupportedCurrencyError",
    "rate_to_usd",
]
