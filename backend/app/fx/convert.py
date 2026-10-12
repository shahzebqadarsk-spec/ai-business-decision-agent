"""Deterministic currency conversion, pivoting through USD via the static table in
`rates.py`. Pure function, no I/O, no model calls -- the same inputs always produce the
same output, which is the point: a KPI computed from a mixed-currency upload has to be
reproducible, not dependent on when it happened to be calculated.
"""

from __future__ import annotations

from app.fx.rates import rate_to_usd


def convert_amount(amount: float, *, from_currency: str, to_currency: str) -> float:
    """Convert `amount` from `from_currency` to `to_currency` using the static rate
    table. Same currency on both sides is a no-op (and avoids a float round-trip through
    USD introducing noise for the common single-currency case)."""
    from_code = from_currency.strip().upper()
    to_code = to_currency.strip().upper()
    if from_code == to_code:
        return amount

    from_per_usd = rate_to_usd(from_code)
    to_per_usd = rate_to_usd(to_code)
    amount_usd = amount / from_per_usd
    return amount_usd * to_per_usd


def fx_rate(*, from_currency: str, to_currency: str) -> float:
    """The multiplier such that `amount * fx_rate(...) == convert_amount(amount, ...)`.
    Stored alongside converted amounts (as `fx_rate_to_reporting`) so every converted
    number carries the exact rate used for it -- an audit trail, not a black box."""
    return convert_amount(1.0, from_currency=from_currency, to_currency=to_currency)


__all__ = ["convert_amount", "fx_rate"]
