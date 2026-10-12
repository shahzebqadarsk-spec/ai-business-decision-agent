from __future__ import annotations

import pytest
from app.fx.rates import SUPPORTED_CURRENCIES, UnsupportedCurrencyError, rate_to_usd


def test_usd_rate_is_exactly_one() -> None:
    assert rate_to_usd("USD") == 1.0


def test_pkr_has_a_rate() -> None:
    assert rate_to_usd("PKR") > 0


def test_lookup_is_case_insensitive_and_strips_whitespace() -> None:
    assert rate_to_usd("pkr") == rate_to_usd("PKR")
    assert rate_to_usd(" usd ") == rate_to_usd("USD")


def test_unknown_currency_raises_rather_than_guessing() -> None:
    with pytest.raises(UnsupportedCurrencyError):
        rate_to_usd("XXX")


def test_every_supported_rate_is_positive() -> None:
    for code in SUPPORTED_CURRENCIES:
        assert rate_to_usd(code) > 0, f"{code} has a non-positive rate"


def test_pegged_gulf_currencies_match_their_known_official_pegs() -> None:
    # These are hard pegs, not floating estimates -- worth asserting exactly so a future
    # refresh doesn't accidentally drift them.
    assert rate_to_usd("AED") == pytest.approx(3.6725)
    assert rate_to_usd("SAR") == pytest.approx(3.75)
