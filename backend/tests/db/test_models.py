from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.db.models.recommendations import Recommendation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def test_recommendation_cannot_be_approved_without_approver(db_session: Session) -> None:
    rec = Recommendation(title="t", narrative="n", status="approved")
    db_session.add(rec)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_recommendation_can_be_approved_with_approver_and_timestamp(db_session: Session) -> None:
    rec = Recommendation(
        title="t",
        narrative="n",
        status="approved",
        approved_by="cfo@pakmanufacture.example",
        approved_at=datetime.now(UTC),
    )
    db_session.add(rec)
    db_session.commit()
    assert rec.id is not None


def test_recommendation_draft_needs_no_approver(db_session: Session) -> None:
    rec = Recommendation(title="t", narrative="n", status="draft")
    db_session.add(rec)
    db_session.commit()
    assert rec.id is not None


def test_dataset_file_cascade_delete(db_session: Session) -> None:
    from app.db.models.datasets import Dataset, DatasetFile

    dataset = Dataset(name="d1", status="uploaded")
    db_session.add(dataset)
    db_session.flush()
    file_ = DatasetFile(
        dataset_id=dataset.id,
        original_filename="a.csv",
        stored_filename="a.csv",
        storage_path="/tmp/a.csv",
        size_bytes=10,
        sha256="x" * 64,
        status="pending",
    )
    db_session.add(file_)
    db_session.commit()

    db_session.delete(dataset)
    db_session.commit()

    remaining = db_session.query(DatasetFile).filter_by(dataset_id=dataset.id).all()
    assert remaining == []
