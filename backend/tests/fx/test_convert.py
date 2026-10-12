from __future__ import annotations

import pytest
from app.fx.convert import convert_amount, fx_rate
from app.fx.rates import UnsupportedCurrencyError, rate_to_usd


def test_same_currency_is_a_no_op() -> None:
    assert convert_amount(1234.56, from_currency="PKR", to_currency="PKR") == 1234.56


def test_same_currency_is_a_no_op_case_insensitive() -> None:
    assert convert_amount(100.0, from_currency="usd", to_currency="USD") == 100.0


def test_converts_usd_to_pkr_using_the_table_rate() -> None:
    expected = 100.0 * rate_to_usd("PKR")
    assert convert_amount(100.0, from_currency="USD", to_currency="PKR") == pytest.approx(expected)


def test_converts_pkr_to_usd_is_the_inverse() -> None:
    pkr_amount = 27850.0
    as_usd = convert_amount(pkr_amount, from_currency="PKR", to_currency="USD")
    back_to_pkr = convert_amount(as_usd, from_currency="USD", to_currency="PKR")
    assert back_to_pkr == pytest.approx(pkr_amount)


def test_cross_rate_pivots_through_usd_correctly() -> None:
    # EUR -> PKR should equal EUR -> USD -> PKR done manually.
    amount_eur = 50.0
    direct = convert_amount(amount_eur, from_currency="EUR", to_currency="PKR")
    manual_usd = amount_eur / rate_to_usd("EUR")
    manual_pkr = manual_usd * rate_to_usd("PKR")
    assert direct == pytest.approx(manual_pkr)


def test_unsupported_currency_raises_not_fabricates() -> None:
    with pytest.raises(UnsupportedCurrencyError):
        convert_amount(100.0, from_currency="XXX", to_currency="PKR")
    with pytest.raises(UnsupportedCurrencyError):
        convert_amount(100.0, from_currency="PKR", to_currency="XXX")


def test_fx_rate_is_the_multiplier_matching_convert_amount() -> None:
    rate = fx_rate(from_currency="USD", to_currency="PKR")
    assert 100.0 * rate == pytest.approx(convert_amount(100.0, from_currency="USD", to_currency="PKR"))


def test_fx_rate_same_currency_is_one() -> None:
    assert fx_rate(from_currency="EUR", to_currency="EUR") == 1.0
