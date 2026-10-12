"""Ingestion pipeline API: upload -> validate -> profile -> quality-check -> propose
mappings -> human-confirm -> materialize.

Nothing in this module (or anything it imports from app.ingestion) ever imports the
synthetic-data generator's hidden fixtures -- see tests/synthetic/test_isolation.py, which
statically greps this whole package for exactly that.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_llm_router
from app.api.schemas.ingestion import (
    CanonicalFieldOut,
    ColumnProfileOut,
    DatasetCreate,
    DatasetOut,
    FileOut,
    MappingConfirmRequest,
    MappingOut,
    MappingRejectRequest,
    MaterializeRequest,
    MaterializeResult,
    QualityIssueOut,
)
from app.audit import record_audit
from app.config import Settings, get_settings
from app.db.models.datasets import ColumnMapping, ColumnProfile, DataQualityIssue, Dataset, DatasetFile
from app.ingestion import mapping as mapping_module
from app.ingestion import parsing, profiling, quality, storage, validation
from app.ingestion.canonical_fields import CANONICAL_TABLES, field_names
from app.ingestion.materialize import MissingRequiredFieldMappingError, materialize_fact_sales
from app.llm.router import LLMRouter
from app.llm.types import Purpose

router = APIRouter(prefix="/datasets", tags=["ingestion"])

# Separate from `router`: this is metadata about the canonical schema itself (not scoped to
# a dataset), so it is not nested under the "/datasets" prefix.
canonical_fields_router = APIRouter(prefix="/canonical-fields", tags=["ingestion"])

_CANONICAL_TABLE = "fact_sales"
_IDENTIFIER_SIBLING_COLUMNS = ("customer_id", "product_id", "region_id", "category_id")


@canonical_fields_router.get("/{table}", response_model=list[CanonicalFieldOut])
def list_canonical_fields(table: str) -> list[CanonicalFieldOut]:
    """The canonical schema the mapping-confirmation UI lets a human map columns into --
    single source of truth, so the frontend never hand-maintains its own copy of this list."""
    if table not in CANONICAL_TABLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown canonical table '{table}'.")
    return [
        CanonicalFieldOut(name=f.name, required=f.required, data_type=f.data_type)
        for f in CANONICAL_TABLES[table]
    ]


def _get_dataset_or_404(session: Session, dataset_id: UUID) -> Dataset:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Dataset not found.")
    return dataset


def _get_file_or_404(session: Session, dataset_id: UUID, file_id: UUID) -> DatasetFile:
    file_ = session.get(DatasetFile, file_id)
    if file_ is None or file_.dataset_id != dataset_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found in this dataset.")
    return file_


def _sibling_known_ids(session: Session, dataset_id: UUID, exclude_file_id: UUID) -> dict[str, set[str]]:
    """Referential-integrity reference set, built only from *other already-validated files
    in the same dataset* -- e.g. a customers.csv uploaded alongside sales.csv. There is no
    dependency on the synthetic-data catalog here; if no sibling file supplies a given
    column, that check is simply skipped ("where detectable"), per the spec."""
    known: dict[str, set[str]] = {}
    siblings = (
        session.query(DatasetFile)
        .filter(
            DatasetFile.dataset_id == dataset_id,
            DatasetFile.id != exclude_file_id,
            DatasetFile.status == "validated",
        )
        .all()
    )
    for sibling in siblings:
        try:
            df = parsing.read_upload(
                Path(sibling.storage_path),
                extension=validation.extension_of(sibling.stored_filename),
                max_rows=10_000_000,
            )
        except (OSError, ValueError):
            continue
        for col in _IDENTIFIER_SIBLING_COLUMNS:
            if col in df.columns:
                known.setdefault(col, set()).update(df[col].dropna().astype(str).unique())
    return known


def _sibling_reference_columns(
    session: Session, dataset_id: UUID, exclude_file_id: UUID
) -> tuple[str, ...] | None:
    first_sibling = (
        session.query(DatasetFile)
        .filter(
            DatasetFile.dataset_id == dataset_id,
            DatasetFile.id != exclude_file_id,
            DatasetFile.status == "validated",
        )
        .order_by(DatasetFile.created_at.asc())
        .first()
    )
    if first_sibling is None:
        return None
    first_profiles = (
        session.query(ColumnProfile)
        .filter(ColumnProfile.file_id == first_sibling.id)
        .order_by(ColumnProfile.position.asc())
        .all()
    )
    if not first_profiles:
        return None
    return tuple(p.column_name for p in first_profiles)


@router.post("", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def create_dataset(body: DatasetCreate, session: Session = Depends(get_db_session)) -> Dataset:
    dataset = Dataset(name=body.name, status="uploaded")
    session.add(dataset)
    session.commit()
    record_audit(
        session, actor="api", action="create_dataset", entity_type="dataset", entity_id=str(dataset.id)
    )
    return dataset


@router.get("", response_model=list[DatasetOut])
def list_datasets(session: Session = Depends(get_db_session)) -> list[Dataset]:
    return list(session.query(Dataset).order_by(Dataset.created_at.desc()).all())


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: UUID, session: Session = Depends(get_db_session)) -> Dataset:
    return _get_dataset_or_404(session, dataset_id)


@router.get("/{dataset_id}/files", response_model=list[FileOut])
def list_files(dataset_id: UUID, session: Session = Depends(get_db_session)) -> list[DatasetFile]:
    _get_dataset_or_404(session, dataset_id)
    return list(session.query(DatasetFile).filter(DatasetFile.dataset_id == dataset_id).all())


@router.post("/{dataset_id}/files", response_model=FileOut)
def upload_file(
    dataset_id: UUID,
    file: UploadFile,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> DatasetFile:
    dataset = _get_dataset_or_404(session, dataset_id)
    content = file.file.read()
    filename = file.filename or "upload"

    result = validation.validate_upload(
        filename=filename,
        content=content,
        max_bytes=settings.max_upload_bytes,
        max_rows=settings.max_upload_rows,
    )

    dataset_file = DatasetFile(
        dataset_id=dataset.id,
        original_filename=filename,
        stored_filename=filename,
        storage_path="",
        content_type=file.content_type,
        detected_mime=result.detected_mime,
        size_bytes=len(content),
        sha256=storage.sha256_hex(content),
        status="validated" if result.ok else "rejected",
        rejection_reason=result.reason,
    )

    if not result.ok:
        session.add(dataset_file)
        session.commit()
        record_audit(
            session,
            actor="api",
            action="reject_file",
            entity_type="dataset_file",
            entity_id=str(dataset_file.id),
            details={"reason": result.reason},
        )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=result.reason)

    stored_filename = validation.generate_stored_filename(result.extension or "")
    destination = storage.store_upload(
        storage_root=settings.upload_storage_path, stored_filename=stored_filename, content=content
    )
    dataset_file.stored_filename = stored_filename
    dataset_file.storage_path = str(destination)

    df = parsing.read_upload(destination, extension=result.extension or "", max_rows=settings.max_upload_rows)
    dataset_file.row_count = len(df)
    session.add(dataset_file)
    session.flush()

    for profile in profiling.profile_dataframe(df):
        session.add(
            ColumnProfile(
                file_id=dataset_file.id,
                column_name=profile.column_name,
                position=profile.position,
                inferred_dtype=profile.inferred_dtype,
                classification=profile.classification,
                null_count=profile.null_count,
                null_percentage=profile.null_percentage,
                unique_count=profile.unique_count,
                sample_values=profile.sample_values,
                min_value=profile.min_value,
                max_value=profile.max_value,
                mean_value=profile.mean_value,
                stddev_value=profile.stddev_value,
                date_min=profile.date_min,
                date_max=profile.date_max,
            )
        )

    known_ids = _sibling_known_ids(session, dataset_id, dataset_file.id)
    reference_columns = _sibling_reference_columns(session, dataset_id, dataset_file.id)
    for issue in quality.run_quality_checks(
        df, known_ids_by_column=known_ids, reference_columns=reference_columns
    ):
        session.add(
            DataQualityIssue(
                file_id=dataset_file.id,
                column_name=issue.column_name,
                issue_type=issue.issue_type,
                severity=issue.severity,
                description=issue.description,
                affected_row_count=issue.affected_row_count,
                details=issue.details,
            )
        )

    dataset.status = "profiled"
    session.commit()
    record_audit(
        session,
        actor="api",
        action="upload_and_profile_file",
        entity_type="dataset_file",
        entity_id=str(dataset_file.id),
        details={"row_count": dataset_file.row_count},
    )
    return dataset_file


@router.get("/files/{file_id}/profile", response_model=list[ColumnProfileOut])
def get_file_profile(file_id: UUID, session: Session = Depends(get_db_session)) -> list[ColumnProfile]:
    file_ = session.get(DatasetFile, file_id)
    if file_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found.")
    return list(
        session.query(ColumnProfile)
        .filter(ColumnProfile.file_id == file_id)
        .order_by(ColumnProfile.position)
        .all()
    )


@router.get("/files/{file_id}/quality-issues", response_model=list[QualityIssueOut])
def get_quality_issues(file_id: UUID, session: Session = Depends(get_db_session)) -> list[DataQualityIssue]:
    file_ = session.get(DatasetFile, file_id)
    if file_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found.")
    return list(session.query(DataQualityIssue).filter(DataQualityIssue.file_id == file_id).all())


@router.post("/files/{file_id}/mappings/propose", response_model=list[MappingOut])
def propose_mappings(
    file_id: UUID,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> list[ColumnMapping]:
    file_ = session.get(DatasetFile, file_id)
    if file_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found.")
    if file_.status != "validated":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Only a validated file can be mapped.")

    fields = CANONICAL_TABLES[_CANONICAL_TABLE]
    profiles = (
        session.query(ColumnProfile)
        .filter(ColumnProfile.file_id == file_id)
        .order_by(ColumnProfile.position)
        .all()
    )

    already_decided_columns = {
        m.source_column
        for m in session.query(ColumnMapping)
        .filter(ColumnMapping.file_id == file_id, ColumnMapping.status.in_(("confirmed", "rejected")))
        .all()
    }
    session.query(ColumnMapping).filter(
        ColumnMapping.file_id == file_id, ColumnMapping.status.in_(("proposed", "unresolved"))
    ).delete(synchronize_session=False)

    llm_client = llm_router.client_for(Purpose.CLASSIFY)

    created: list[ColumnMapping] = []
    for profile in profiles:
        if profile.column_name in already_decided_columns:
            continue
        proposal = mapping_module.propose_mapping(
            source_column=profile.column_name,
            sample_values=[str(v) for v in profile.sample_values],
            inferred_dtype=profile.inferred_dtype,
            fields=fields,
            llm_client=llm_client,
        )
        mapping_status = "unresolved"
        if (
            proposal.proposed_field is not None
            and proposal.confidence >= settings.mapping_confidence_threshold
        ):
            mapping_status = "proposed"
        column_mapping = ColumnMapping(
            file_id=file_id,
            source_column=proposal.source_column,
            proposed_canonical_field=proposal.proposed_field,
            confidence=proposal.confidence,
            method=proposal.method,
            reason=proposal.reason,
            status=mapping_status,
        )
        session.add(column_mapping)
        created.append(column_mapping)

    dataset_file_dataset = session.get(Dataset, file_.dataset_id)
    if dataset_file_dataset is not None:
        dataset_file_dataset.status = "mapping"
    session.commit()
    record_audit(
        session,
        actor="api",
        action="propose_mappings",
        entity_type="dataset_file",
        entity_id=str(file_id),
        details={"proposed_count": len(created)},
    )
    return list(
        session.query(ColumnMapping)
        .filter(ColumnMapping.file_id == file_id)
        .order_by(ColumnMapping.created_at)
        .all()
    )


@router.get("/files/{file_id}/mappings", response_model=list[MappingOut])
def list_mappings(file_id: UUID, session: Session = Depends(get_db_session)) -> list[ColumnMapping]:
    return list(session.query(ColumnMapping).filter(ColumnMapping.file_id == file_id).all())


@router.post("/files/{file_id}/mappings/{mapping_id}/confirm", response_model=MappingOut)
def confirm_mapping(
    file_id: UUID, mapping_id: UUID, body: MappingConfirmRequest, session: Session = Depends(get_db_session)
) -> ColumnMapping:
    column_mapping = session.get(ColumnMapping, mapping_id)
    if column_mapping is None or column_mapping.file_id != file_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mapping not found.")
    if body.confirmed_canonical_field not in field_names(_CANONICAL_TABLE):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"'{body.confirmed_canonical_field}' is not a known canonical field.",
        )
    column_mapping.confirmed_canonical_field = body.confirmed_canonical_field
    column_mapping.confirmed_by = body.confirmed_by
    column_mapping.confirmed_at = datetime.now(UTC)
    column_mapping.status = "confirmed"
    session.commit()
    record_audit(
        session,
        actor=body.confirmed_by,
        action="confirm_mapping",
        entity_type="column_mapping",
        entity_id=str(mapping_id),
        details={"confirmed_canonical_field": body.confirmed_canonical_field},
    )
    return column_mapping


@router.post("/files/{file_id}/mappings/{mapping_id}/reject", response_model=MappingOut)
def reject_mapping(
    file_id: UUID, mapping_id: UUID, body: MappingRejectRequest, session: Session = Depends(get_db_session)
) -> ColumnMapping:
    column_mapping = session.get(ColumnMapping, mapping_id)
    if column_mapping is None or column_mapping.file_id != file_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mapping not found.")
    column_mapping.status = "rejected"
    column_mapping.confirmed_canonical_field = None
    column_mapping.confirmed_by = body.rejected_by
    column_mapping.confirmed_at = datetime.now(UTC)
    session.commit()
    record_audit(
        session,
        actor=body.rejected_by,
        action="reject_mapping",
        entity_type="column_mapping",
        entity_id=str(mapping_id),
    )
    return column_mapping


@router.post("/files/{file_id}/materialize", response_model=MaterializeResult)
def materialize(
    file_id: UUID,
    body: MaterializeRequest,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> MaterializeResult:
    file_ = session.get(DatasetFile, file_id)
    if file_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found.")

    confirmed = (
        session.query(ColumnMapping)
        .filter(ColumnMapping.file_id == file_id, ColumnMapping.status == "confirmed")
        .all()
    )
    confirmed_mapping = {
        m.source_column: m.confirmed_canonical_field for m in confirmed if m.confirmed_canonical_field
    }

    df = parsing.read_upload(
        Path(file_.storage_path),
        extension=validation.extension_of(file_.stored_filename),
        max_rows=settings.max_upload_rows,
    )

    try:
        rows, result = materialize_fact_sales(
            df, confirmed_mapping=confirmed_mapping, source_file_id=file_.id
        )
    except MissingRequiredFieldMappingError as exc:
        dataset = session.get(Dataset, file_.dataset_id)
        if dataset is not None:
            dataset.status = "failed"
        session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    session.add_all(rows)
    dataset = session.get(Dataset, file_.dataset_id)
    if dataset is not None:
        dataset.status = "materialized"
    session.commit()
    record_audit(
        session,
        actor=body.performed_by,
        action="materialize",
        entity_type="dataset_file",
        entity_id=str(file_id),
        details={"rows_written": result.rows_written, "rows_skipped": result.rows_skipped},
    )
    return MaterializeResult(
        rows_written=result.rows_written,
        rows_skipped=result.rows_skipped,
        skipped_reasons=result.skipped_reasons,
    )
