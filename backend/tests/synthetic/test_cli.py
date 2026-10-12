"""Subprocess-based tests of `python -m generator`, exercising the actual CLI entry point
(argument parsing included) rather than calling `generate()` directly."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SYNTHETIC_DATA_ROOT = _REPO_ROOT / "synthetic_data"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": str(_SYNTHETIC_DATA_ROOT)}
    import os

    full_env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, "-m", "generator", *args],
        cwd=_REPO_ROOT,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_runs_and_reports_row_counts(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    result = _run_cli("--seed", "42", "--scale", "0.05", "--output", str(output_dir))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["seed"] == 42
    assert payload["row_counts"]["sales"] > 0
    assert (output_dir / "clean" / "sales.csv").exists()
    assert (output_dir / "_hidden" / "ground_truth.yaml").exists()


def test_cli_no_messy_flag(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    result = _run_cli("--seed", "42", "--scale", "0.05", "--output", str(output_dir), "--no-messy")
    assert result.returncode == 0, result.stderr
    assert not (output_dir / "messy").exists()
    assert not (output_dir / "_hidden" / "messy_defects.yaml").exists()
    assert (output_dir / "_hidden" / "ground_truth.yaml").exists()


def test_cli_different_seed_changes_output(tmp_path: Path) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    _run_cli("--seed", "1", "--scale", "0.05", "--output", str(out_a), "--no-messy")
    _run_cli("--seed", "2", "--scale", "0.05", "--output", str(out_b), "--no-messy")
    sales_a = (out_a / "clean" / "sales.csv").read_text()
    sales_b = (out_b / "clean" / "sales.csv").read_text()
    assert sales_a != sales_b
