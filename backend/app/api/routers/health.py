from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_llm_router, get_settings_dep
from app.config import Settings
from app.llm.router import LLMRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready(session: Session = Depends(get_db_session)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/system/config")
def system_config(settings: Settings = Depends(get_settings_dep)) -> dict[str, object]:
    return {
        "currency": settings.reporting_currency,
        "fiscal_year_start_month": settings.fiscal_year_start_month,
        "default_comparison": settings.default_comparison,
        "synthetic_data_only": settings.synthetic_data_only,
        "llm_use_mock": settings.llm_use_mock,
    }


@router.get("/llm/status")
def llm_status(router_: LLMRouter = Depends(get_llm_router)) -> dict[str, object]:
    return router_.describe()
