from __future__ import annotations

import pandas as pd
from app.ingestion.numeric_format import (
    clean_numeric_series,
    clean_numeric_string,
    detect_currency_code,
    detect_currency_series,
)


def test_strips_rs_prefix_with_and_without_space() -> None:
    assert clean_numeric_string("Rs 1,441.26") == "1441.26"
    assert clean_numeric_string("Rs1441.26") == "1441.26"
    assert clean_numeric_string("Rs.1,441.26") == "1441.26"


def test_strips_pkr_and_rupee_symbol_case_insensitively() -> None:
    assert clean_numeric_string("PKR 2,100") == "2100"
    assert clean_numeric_string("pkr 2,100") == "2100"
    assert clean_numeric_string("₨2,100") == "2100"


def test_strips_thousands_comma_without_currency_prefix() -> None:
    assert clean_numeric_string("1,379.22") == "1379.22"
    assert clean_numeric_string("1,234,567.89") == "1234567.89"


def test_plain_number_passes_through_unchanged() -> None:
    assert clean_numeric_string("210.99") == "210.99"
    assert clean_numeric_string("42") == "42"


def test_accounting_style_parentheses_become_negative() -> None:
    assert clean_numeric_string("(1,441.26)") == "-1441.26"
    assert clean_numeric_string("(500)") == "-500"


def test_does_not_mangle_a_comma_that_is_not_a_thousands_separator() -> None:
    # A single trailing digit group that isn't exactly 3 digits is left alone --
    # conservative by design, never guesses.
    assert clean_numeric_string("1,4") == "1,4"


def test_non_string_values_pass_through_untouched() -> None:
    assert clean_numeric_string(None) is None
    assert clean_numeric_string(42) == 42
    assert pd.isna(clean_numeric_string(float("nan")))


def test_empty_and_blank_strings_pass_through_untouched() -> None:
    assert clean_numeric_string("") == ""
    assert clean_numeric_string("   ") == "   "


def test_unparseable_text_is_left_alone_not_fabricated() -> None:
    # No recognizable number in the string -- must still fail to parse downstream,
    # exactly as before this module existed.
    assert clean_numeric_string("N/A") == "N/A"
    assert clean_numeric_string("pending") == "pending"


def test_clean_numeric_series_applies_elementwise() -> None:
    series = pd.Series(["Rs 1,441.26", "1,379.22", "210.99"])
    cleaned = clean_numeric_series(series)
    assert list(cleaned) == ["1441.26", "1379.22", "210.99"]
    assert pd.to_numeric(cleaned).tolist() == [1441.26, 1379.22, 210.99]


def test_cleans_suffix_style_currency_codes_too() -> None:
    # "1200.50 USD" (code after the number) is just as real-world as a prefix.
    assert clean_numeric_string("1200.50 USD") == "1200.50"
    assert clean_numeric_string("45.50€") == "45.50"
    assert clean_numeric_string("2,100 AED") == "2100"


def test_detects_unambiguous_prefix_currency() -> None:
    assert detect_currency_code("Rs 1,441.26") == "PKR"
    assert detect_currency_code("Rs.500") == "PKR"
    assert detect_currency_code("PKR 2,100") == "PKR"
    assert detect_currency_code("€45.50") == "EUR"
    assert detect_currency_code("£100") == "GBP"
    assert detect_currency_code("₹500") == "INR"
    assert detect_currency_code("AED 3.6725") == "AED"


def test_detects_unambiguous_suffix_currency() -> None:
    assert detect_currency_code("1200.50 USD") == "USD"
    assert detect_currency_code("45.50€") == "EUR"
    assert detect_currency_code("2,100 AED") == "AED"


def test_detects_compound_dollar_prefixes_that_disambiguate() -> None:
    assert detect_currency_code("US$100") == "USD"
    assert detect_currency_code("A$100") == "AUD"
    assert detect_currency_code("C$100") == "CAD"
    assert detect_currency_code("S$100") == "SGD"
    assert detect_currency_code("HK$100") == "HKD"
    assert detect_currency_code("NZ$100") == "NZD"


def test_detects_compound_yen_yuan_prefixes_that_disambiguate() -> None:
    assert detect_currency_code("CN¥100") == "CNY"
    assert detect_currency_code("JP¥100") == "JPY"


def test_bare_ambiguous_symbols_return_none_not_a_guess() -> None:
    # A bare "$" could be USD, AUD, CAD, SGD, HKD or NZD; a bare "¥" could be JPY or
    # CNY. Guessing either would risk silently mis-stating revenue, so this must stay
    # None rather than defaulting to one.
    assert detect_currency_code("$100") is None
    assert detect_currency_code("¥100") is None
    assert detect_currency_code("100 kr") is None


def test_plain_number_has_no_detectable_currency() -> None:
    assert detect_currency_code("210.99") is None
    assert detect_currency_code("1,441.26") is None


def test_non_string_and_unparseable_values_detect_as_none() -> None:
    assert detect_currency_code(None) is None
    assert detect_currency_code(42) is None
    assert detect_currency_code("N/A") is None


def test_detect_currency_series_applies_elementwise() -> None:
    series = pd.Series(["Rs 1,441.26", "$210.99", "€38.00", "500"])
    detected = list(detect_currency_series(series))
    assert detected[0] == "PKR"
    assert pd.isna(detected[1])
    assert detected[2] == "EUR"
    assert pd.isna(detected[3])
