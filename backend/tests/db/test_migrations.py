from __future__ import annotations

from app.db.base import Base
from sqlalchemy import inspect
from sqlalchemy.engine import Engine


def test_create_all_matches_declared_models(test_engine: Engine) -> None:
    inspector = inspect(test_engine)
    tables = set(inspector.get_table_names())
    expected = set(Base.metadata.tables.keys())
    assert expected.issubset(tables)


def test_check_constraints_present(test_engine: Engine) -> None:
    inspector = inspect(test_engine)
    constraints = inspector.get_check_constraints("recommendations")
    names = {c["name"] for c in constraints}
    assert "ck_recommendations_approved_requires_approver_and_timestamp" in names
