from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.llm.config import RoutingConfig
from app.llm.recording import DbCallRecorder
from app.llm.router import LLMRouter


def get_settings_dep() -> Settings:
    return get_settings()


def get_db_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_llm_router(
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(get_db_session),
) -> LLMRouter:
    routing = RoutingConfig.load(settings.llm_routing_config_path)
    recorder = DbCallRecorder(session)
    return LLMRouter(
        routing=routing,
        use_mock=settings.llm_use_mock,
        deepseek_api_key=settings.deepseek_api_key.get_secret_value() if settings.deepseek_api_key else None,
        recorder=recorder,
    )


def require_auth(
    settings: Settings = Depends(get_settings_dep),
    authorization: str | None = Header(default=None),
) -> None:
    if not settings.auth_enabled:
        return
    expected = settings.admin_api_token.get_secret_value() if settings.admin_api_token else None
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
