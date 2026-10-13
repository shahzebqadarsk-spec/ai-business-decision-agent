from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, insert, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("LLM_USE_MOCK", "true")
os.environ.setdefault("SYNTHETIC_DATA_ONLY", "true")
os.environ.setdefault("CURRENCY", "PKR")

import app.db.models  # noqa: E402,F401
from app.config import Settings, get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models.canonical import FactSales  # noqa: E402
from app.db.models.datasets import Dataset, DatasetFile  # noqa: E402
from app.fx.convert import fx_rate  # noqa: E402
from app.fx.rates import RATES_AS_OF  # noqa: E402
from generator.config import GeneratorConfig  # noqa: E402
from generator.pipeline import generate  # noqa: E402


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Phase 2's ingestion tests materialize their own small, uncleaned-up slices into
    fact_sales (see seeded_fact_sales_file_id's own docstring); the shared fixture depends on
    running *after* them so its wipe-then-load clears that leftover first. Directory-alphabetical
    collection order made this true by accident (ingestion < kpi, rca); Phase 5 added
    tests/forecasting, which sorts before tests/ingestion and broke that accident. This hook
    makes the ordering explicit and no longer dependent on test-directory naming."""

    def sort_key(item: pytest.Item) -> tuple[int, str]:
        path = str(item.fspath)
        return (0 if "/tests/ingestion/" in path else 1, path)

    items.sort(key=sort_key)


@pytest.fixture(scope="session")
def base_settings() -> Settings:
    return get_settings()


def _test_db_url(base_url: str) -> str:
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        return override
    if base_url.rsplit("/", 1)[-1].endswith("_test"):
        return base_url
    return base_url.rsplit("/", 1)[0] + "/" + base_url.rsplit("/", 1)[-1] + "_test"


@pytest.fixture(scope="session")
def db_available(base_settings: Settings) -> bool:
    try:
        engine = create_engine(base_settings.database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        if os.environ.get("REQUIRE_DB_TESTS") == "1":
            raise
        return False


@pytest.fixture(scope="session")
def test_engine(base_settings: Settings, db_available: bool) -> Generator[Engine, None, None]:
    if not db_available:
        pytest.skip("PostgreSQL not reachable; set REQUIRE_DB_TESTS=1 to make this a failure.")
    admin_engine = create_engine(base_settings.database_url, isolation_level="AUTOCOMMIT")
    test_url = _test_db_url(base_settings.database_url)
    test_db_name = test_url.rsplit("/", 1)[-1]
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db_name}"'))
        conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    admin_engine.dispose()

    engine = create_engine(test_url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

    admin_engine = create_engine(base_settings.database_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db_name}"'))
    admin_engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def app_settings(base_settings: Settings, test_engine: Engine) -> Settings:
    return base_settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, test_engine: Engine) -> Generator[TestClient, None, None]:
    test_url = test_engine.url.render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", test_url)
    get_settings.cache_clear()

    import app.db.session as db_session_module

    db_session_module._engine = None
    db_session_module._SessionLocal = None

    from app.main import create_app

    app_ = create_app()
    with TestClient(app_) as c:
        yield c

    if db_session_module._engine is not None:
        db_session_module._engine.dispose()
        db_session_module._engine = None
        db_session_module._SessionLocal = None
    get_settings.cache_clear()


# --- Real seed-42 dataset fixtures -----------------------------------------------------
#
# Shared by Phase 3 (tests/kpi/) and Phase 4 (tests/rca/): both need the full, real seed-42
# dataset materialized into `fact_sales` -- a KPI is a company-wide sum and an RCA detector
# screens for company-wide/dimensional materiality, so both need the genuine row volume and
# planted patterns, not a tiny synthetic slice. Defined once, here, so both suites share the
# same session-scoped load rather than each paying for (and wiping the other's) a separate one.

_CANONICAL_COLUMNS = (
    "sale_id",
    "month",
    "order_date",
    "invoice_date",
    "customer_id",
    "region_id",
    "product_id",
    "category_id",
    "quantity",
    "unit_price",
    "gross_amount",
    "net_amount",
    "cogs_amount",
    "gross_margin_pct",
    "discount_pct",
    "payment_terms",
    "currency",
)


@pytest.fixture(scope="session")
def planted_config() -> GeneratorConfig:
    """The exact generator config the official seed-42 dataset is built from -- used only by
    tests, per the Phase 3/4 spec's ground-truth-testing rule (never by production code)."""
    return GeneratorConfig(seed=42, scale=1.0)


@pytest.fixture(scope="session")
def full_scale_sales_csv(tmp_path_factory: pytest.TempPathFactory, planted_config: GeneratorConfig) -> Path:
    output_dir = tmp_path_factory.mktemp("full_scale") / "output"
    generate(planted_config, output_dir)
    return output_dir / "clean" / "sales.csv"


@pytest.fixture(scope="session")
def sales_df(full_scale_sales_csv: Path) -> pd.DataFrame:
    """The raw generator CSV as a DataFrame, for tests to independently compute an expected
    value with (pandas), rather than only ever testing an engine against itself."""
    df = pd.read_csv(full_scale_sales_csv, parse_dates=["month", "order_date", "invoice_date"])
    return df


@pytest.fixture(scope="session")
def seeded_fact_sales_file_id(test_engine: Engine, full_scale_sales_csv: Path) -> Generator[str, None, None]:
    """Loads the full seed-42 clean sales file into `fact_sales` once for the whole test
    session and returns its `source_file_id`. Cleans itself up at session end.

    Also wipes `fact_sales` first: other test modules (Phase 2's ingestion tests, which run
    earlier in the same shared test database) materialize their own small synthetic slices
    into this same table and never clean them up, since their own assertions are scoped to
    their own `source_file_id`. Phase 3/4's period-aggregate assertions are *not* scoped that
    way -- a KPI is a company-wide sum, an RCA detector screens company-wide materiality -- so
    leftover rows from an unrelated test would silently skew every figure in this whole suite.
    By the time this fixture runs (session-scoped, first used by the first KPI or RCA test),
    every Phase 0-2 test that depends on those rows has already made its assertions, so
    clearing the table here is safe."""
    with Session(test_engine) as session:
        session.execute(delete(FactSales))
        session.commit()

        dataset = Dataset(name="kpi-rca-test-fixture", status="materialized")
        session.add(dataset)
        session.flush()
        file_ = DatasetFile(
            dataset_id=dataset.id,
            original_filename="sales.csv",
            stored_filename="sales.csv",
            storage_path="",
            size_bytes=1,
            sha256="0" * 64,
            status="validated",
            row_count=0,
        )
        session.add(file_)
        session.flush()
        file_id = file_.id
        dataset_id = dataset.id

        df = pd.read_csv(full_scale_sales_csv, parse_dates=["month", "order_date", "invoice_date"])
        for date_col in ("month", "order_date", "invoice_date"):
            df[date_col] = df[date_col].dt.date
        sub = df[list(_CANONICAL_COLUMNS)].copy()
        sub["source_file_id"] = str(file_id)
        sub["source_row_number"] = range(len(sub))

        # Phase 8: this fixture bulk-inserts FactSales rows directly (bypassing
        # materialize_fact_sales), so it has to compute the *_reporting columns itself --
        # otherwise every KPI/RCA test that sums net_amount_reporting would silently sum
        # NULLs. The synthetic generator's rows are always in one native currency
        # (planted_config.currency), so this mirrors materialize.py's same-currency case:
        # one FX rate for the whole dataset, not a per-row lookup.
        reporting_currency = get_settings().reporting_currency
        sub["currency"] = sub["currency"].fillna(reporting_currency)
        native_currency = str(sub["currency"].iloc[0]) if len(sub) else reporting_currency
        rate = fx_rate(from_currency=native_currency, to_currency=reporting_currency)
        sub["fx_rate_to_reporting"] = rate
        sub["fx_rate_as_of"] = RATES_AS_OF
        sub["unit_price_reporting"] = sub["unit_price"] * rate
        sub["net_amount_reporting"] = sub["net_amount"] * rate
        sub["cogs_amount_reporting"] = sub["cogs_amount"] * rate

        sub = sub.where(pd.notnull(sub), None)
        records = cast(list[dict[str, Any]], sub.to_dict("records"))
        session.execute(insert(FactSales), records)
        session.commit()

    yield str(file_id)

    with Session(test_engine) as session:
        session.query(FactSales).filter(FactSales.source_file_id == file_id).delete()
        session.query(DatasetFile).filter(DatasetFile.id == file_id).delete()
        session.query(Dataset).filter(Dataset.id == dataset_id).delete()
        session.commit()
