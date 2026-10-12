"""Application settings.

A handful of fields are *locked* by the Phase 0 / Phase 1 business decisions
(see docs/DECISIONS.md). They are still ordinary environment variables so the
rest of the config story stays simple, but an invalid override raises at
startup instead of silently being accepted.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.fx.rates import SUPPORTED_CURRENCIES

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Locked business decisions (Phase 0 approval) -----------------------------------
    synthetic_data_only: bool = Field(default=True, alias="SYNTHETIC_DATA_ONLY")
    # Phase 0 locked this to PKR outright. Phase 8 (see docs/DECISIONS.md) supersedes that:
    # a deployment now picks ANY currency it has an FX rate for as its *reporting*
    # currency -- the one every KPI/RCA/forecast number is converted into and displayed
    # in. A row's own *native* transaction currency is separate (`fact_sales.currency`,
    # set per row during materialization) and is never locked -- that's the whole point
    # of multi-currency support: a dataset can mix native currencies freely, they all
    # convert into this one reporting currency.
    reporting_currency: str = Field(default="PKR", alias="CURRENCY")
    fiscal_year_start_month: int = Field(default=1, alias="FISCAL_YEAR_START_MONTH")
    default_comparison: str = Field(default="YoY", alias="DEFAULT_COMPARISON")

    @field_validator("synthetic_data_only")
    @classmethod
    def _synthetic_only_locked(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("SYNTHETIC_DATA_ONLY is locked to true for this project (Phase 0 decision).")
        return value

    @field_validator("reporting_currency")
    @classmethod
    def _reporting_currency_must_have_a_known_rate(cls, value: str) -> str:
        code = value.strip().upper()
        if code not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"CURRENCY (reporting currency) '{value}' has no FX rate in app/fx/rates.py. "
                f"Supported: {sorted(SUPPORTED_CURRENCIES)}. Add a sourced, dated rate there "
                "rather than setting a currency this project can't actually convert into."
            )
        return code

    @field_validator("default_comparison")
    @classmethod
    def _comparison_choice(cls, value: str) -> str:
        if value not in {"YoY", "QoQ"}:
            raise ValueError("DEFAULT_COMPARISON must be 'YoY' or 'QoQ'.")
        return value

    # --- Database -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://abda:abda@localhost:5432/abda", alias="DATABASE_URL"
    )
    test_database_url: str | None = Field(default=None, alias="TEST_DATABASE_URL")
    require_db_tests: bool = Field(default=False, alias="REQUIRE_DB_TESTS")

    # --- API / CORS -------------------------------------------------------------------------
    cors_origins_raw: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")

    # --- Auth stub ----------------------------------------------------------------------
    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")
    admin_api_token: SecretStr | None = Field(default=None, alias="ADMIN_API_TOKEN")

    # --- LLM ----------------------------------------------------------------------------
    llm_use_mock: bool = Field(default=True, alias="LLM_USE_MOCK")
    llm_provider: str = Field(default="deepseek", alias="LLM_PROVIDER")
    deepseek_api_key: SecretStr | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    llm_routing_config_path: Path = Field(
        default=_BACKEND_ROOT / "config" / "llm_routing.yaml", alias="LLM_ROUTING_CONFIG_PATH"
    )

    # --- Phase 2 (pre-declared so later phases don't need a new settings shape) ---------
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    max_upload_rows: int = Field(default=500_000, alias="MAX_UPLOAD_ROWS")
    mapping_confidence_threshold: float = Field(default=0.8, alias="MAPPING_CONFIDENCE_THRESHOLD")
    upload_storage_path: Path = Field(default=_REPO_ROOT / "var" / "uploads", alias="UPLOAD_STORAGE_PATH")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
