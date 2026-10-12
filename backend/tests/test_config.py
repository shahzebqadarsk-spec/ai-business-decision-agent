from __future__ import annotations

import pytest
from app.config import Settings


def test_defaults_are_locked_decisions() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.synthetic_data_only is True
    assert settings.reporting_currency == "PKR"
    assert settings.fiscal_year_start_month == 1
    assert settings.default_comparison == "YoY"


def test_rejects_synthetic_data_only_override() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, SYNTHETIC_DATA_ONLY=False)  # type: ignore[call-arg]


def test_accepts_any_currency_with_a_known_fx_rate() -> None:
    # Phase 8 supersedes the old Phase 0 "locked to PKR" rule (see docs/DECISIONS.md):
    # a deployment's reporting currency can now be anything app/fx/rates.py has a rate
    # for, since multi-currency datasets convert into it rather than assuming PKR.
    settings = Settings(_env_file=None, CURRENCY="USD")  # type: ignore[call-arg]
    assert settings.reporting_currency == "USD"
    settings_eur = Settings(_env_file=None, CURRENCY="eur")  # type: ignore[call-arg]
    assert settings_eur.reporting_currency == "EUR"


def test_rejects_currency_with_no_known_fx_rate() -> None:
    # Still refuses to fabricate a rate for a currency it knows nothing about.
    with pytest.raises(ValueError):
        Settings(_env_file=None, CURRENCY="XXX")  # type: ignore[call-arg]


def test_accepts_qoq_comparison() -> None:
    settings = Settings(_env_file=None, DEFAULT_COMPARISON="QoQ")  # type: ignore[call-arg]
    assert settings.default_comparison == "QoQ"


def test_rejects_invalid_comparison() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, DEFAULT_COMPARISON="MoM")  # type: ignore[call-arg]


def test_cors_origins_parsing() -> None:
    settings = Settings(_env_file=None, CORS_ORIGINS="http://a.com, http://b.com")  # type: ignore[call-arg]
    assert settings.cors_origins == ["http://a.com", "http://b.com"]
