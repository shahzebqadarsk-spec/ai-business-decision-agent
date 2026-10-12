"""Normalizes common real-world numeric string formatting (currency symbols,
thousands separators, accounting-style negatives) before anything attempts to
parse a value as a number, and -- for multi-currency support -- detects which
currency a cell is actually in, when that's unambiguous from the text itself.

Why this exists: `parsing.py` deliberately reads every cell as a raw string,
and `pd.to_numeric` has no idea that "Rs 1,441.26" and "1,441.26" and
"210.99" are all the same kind of value -- it just fails on the first two.
A real small-business Excel/CSV export mixes these formats within a single
column constantly (different staff, different habits, copy-pasted rows), so
treating that column as un-parseable text (as `pd.to_numeric` alone does)
was a real, measured gap, not a hypothetical one -- a pilot test against a
deliberately messy sample file hit it directly on a price column.

Deliberately conservative in two ways:
  1. `clean_numeric_string` only strips formatting noise around a number that
     is still fully present in the string. It never guesses, infers, or
     fabricates a value -- a string with no recognizable number still fails
     to parse, exactly as before.
  2. `detect_currency_code` only returns a currency when the text itself is
     unambiguous about which one it is. A bare "$" could be USD, AUD, CAD,
     SGD, HKD or NZD -- rather than silently guessing USD (and quietly
     mis-stating someone's revenue if it was actually AUD), it returns None
     and lets the caller fall back to an explicit `currency` column mapping
     or the deployment's configured default. Compound forms that *do*
     disambiguate ("US$", "A$", "CN¥", or any plain ISO code like "AED") are
     still recognized.
"""

from __future__ import annotations

import re

import pandas as pd

# Every token this module can recognize in a price/amount cell, mapped to the ISO 4217
# code it unambiguously identifies. Bare symbols shared by several currencies (plain "$",
# plain "¥", "kr") are deliberately absent -- see the module docstring.
_CURRENCY_TOKEN_TO_CODE: dict[str, str] = {
    # Pakistan -- the common local renderings of PKR.
    "RS": "PKR",
    "RS.": "PKR",
    "PKR": "PKR",
    "₨": "PKR",
    # Plain ISO 4217 codes are unambiguous by definition.
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "INR": "INR",
    "AED": "AED",
    "SAR": "SAR",
    "QAR": "QAR",
    "BHD": "BHD",
    "KWD": "KWD",
    "OMR": "OMR",
    "CNY": "CNY",
    "RMB": "CNY",
    "JPY": "JPY",
    "AUD": "AUD",
    "CAD": "CAD",
    "SGD": "SGD",
    "HKD": "HKD",
    "NZD": "NZD",
    "CHF": "CHF",
    "TRY": "TRY",
    "BDT": "BDT",
    "NGN": "NGN",
    "ZAR": "ZAR",
    "LKR": "LKR",
    "NPR": "NPR",
    "AFN": "AFN",
    "MYR": "MYR",
    "IDR": "IDR",
    "THB": "THB",
    "KRW": "KRW",
    "SEK": "SEK",
    "NOK": "NOK",
    "DKK": "DKK",
    "RUB": "RUB",
    "EGP": "EGP",
    "KES": "KES",
    # Symbols used by exactly one currency in this table.
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "₽": "RUB",
    "₦": "NGN",
    "₩": "KRW",
    # Compound "$" prefixes that disambiguate which dollar.
    "US$": "USD",
    "A$": "AUD",
    "AU$": "AUD",
    "C$": "CAD",
    "CA$": "CAD",
    "S$": "SGD",
    "HK$": "HKD",
    "NZ$": "NZD",
    # Compound "¥" prefixes that disambiguate yen vs. yuan.
    "CN¥": "CNY",
    "JP¥": "JPY",
}

# Longest tokens first, so "RS." matches before the shorter "RS" and "US$" before a
# (nonexistent) bare "$" -- alternation in a regex tries options left-to-right.
_TOKEN_ALTERNATION = "|".join(
    re.escape(t) for t in sorted(_CURRENCY_TOKEN_TO_CODE, key=len, reverse=True)
)
_CURRENCY_PREFIX_RE = re.compile(rf"^\s*({_TOKEN_ALTERNATION})\s*", re.IGNORECASE)
_CURRENCY_SUFFIX_RE = re.compile(rf"\s*({_TOKEN_ALTERNATION})\s*$", re.IGNORECASE)
_THOUSANDS_COMMA_RE = re.compile(r"(?<=\d),(?=\d{3}(\D|$))")
_ACCOUNTING_NEGATIVE_RE = re.compile(r"^\s*\(\s*(.+?)\s*\)\s*$")


def clean_numeric_string(value: object) -> object:
    """Best-effort cleanup of one cell before numeric parsing. Non-strings
    (including NaN/None) pass through untouched -- cleaning is a string-only
    concern; type coercion still happens downstream exactly as before."""
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value

    negative = False
    accounting_match = _ACCOUNTING_NEGATIVE_RE.match(text)
    if accounting_match:
        negative = True
        text = accounting_match.group(1)

    text = _CURRENCY_PREFIX_RE.sub("", text)
    text = _CURRENCY_SUFFIX_RE.sub("", text)
    text = text.strip()
    text = _THOUSANDS_COMMA_RE.sub("", text)

    if negative and text and not text.startswith("-"):
        text = f"-{text}"

    return text


def clean_numeric_series(series: pd.Series) -> pd.Series:
    """Vectorized form of `clean_numeric_string` for a whole column."""
    return series.map(clean_numeric_string)


def detect_currency_code(value: object) -> str | None:
    """Best-effort detection of which ISO 4217 currency a single cell is in, from an
    unambiguous symbol/code in the text itself (leading or trailing). Returns None --
    never a guess -- when the cell has no currency indicator or only an ambiguous one
    (bare "$", bare "¥", "kr"). Intended for price/amount columns; it is not a general
    text classifier."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None

    accounting_match = _ACCOUNTING_NEGATIVE_RE.match(text)
    if accounting_match:
        text = accounting_match.group(1)

    prefix_match = _CURRENCY_PREFIX_RE.match(text)
    if prefix_match and prefix_match.group(1):
        return _CURRENCY_TOKEN_TO_CODE[prefix_match.group(1).upper()]

    suffix_match = _CURRENCY_SUFFIX_RE.search(text)
    if suffix_match and suffix_match.group(1):
        return _CURRENCY_TOKEN_TO_CODE[suffix_match.group(1).upper()]

    return None


def detect_currency_series(series: pd.Series) -> pd.Series:
    """Vectorized form of `detect_currency_code` for a whole column."""
    return series.map(detect_currency_code)


__all__ = [
    "clean_numeric_string",
    "clean_numeric_series",
    "detect_currency_code",
    "detect_currency_series",
]
