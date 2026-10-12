from __future__ import annotations

from app.api.deps import require_auth
from app.config import Settings


def test_auth_disabled_allows_any_request() -> None:
    settings = Settings(_env_file=None, AUTH_ENABLED=False)  # type: ignore[call-arg]
    require_auth(settings=settings, authorization=None)  # should not raise
