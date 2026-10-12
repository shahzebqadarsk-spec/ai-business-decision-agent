from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_env_example_exists_and_documents_locked_decisions() -> None:
    env_example = _REPO_ROOT / ".env.example"
    assert env_example.exists()
    content = env_example.read_text()
    for key in ("SYNTHETIC_DATA_ONLY", "CURRENCY", "FISCAL_YEAR_START_MONTH", "DATABASE_URL", "LLM_USE_MOCK"):
        assert key in content
