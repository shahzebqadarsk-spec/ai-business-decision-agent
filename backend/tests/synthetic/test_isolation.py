"""Static proof that the hidden ground-truth / messy-defects fixtures can never leak into
the backend application: nothing under app/ may import or even mention the generator's
`ground_truth`, `measure`, or `planted` modules, or the `messy_defects` fixture name.

This is checked by grepping *source text*, not by running the app, so it catches an import
even if it's never exercised by a test -- exactly the kind of leak a runtime-only check
would miss.
"""

from __future__ import annotations

from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parents[2] / "app"
_FORBIDDEN_SUBSTRINGS = (
    "ground_truth",
    "generator.measure",
    "generator.planted",
    "messy_defects",
)


def test_app_source_never_mentions_hidden_fixtures() -> None:
    offending: list[str] = []
    for path in _APP_ROOT.rglob("*.py"):
        text = path.read_text()
        for needle in _FORBIDDEN_SUBSTRINGS:
            if needle in text:
                offending.append(f"{path.relative_to(_APP_ROOT.parent)}: contains {needle!r}")
    assert offending == [], "Hidden ground-truth fixtures leaked into app/ source:\n" + "\n".join(offending)


def test_app_root_exists_and_has_python_files() -> None:
    # sanity check that the scan above isn't silently scanning zero files
    assert any(_APP_ROOT.rglob("*.py"))


def test_hidden_fixtures_are_not_under_app_or_served_statically() -> None:
    assert not (_APP_ROOT / "ground_truth.yaml").exists()
    assert not (_APP_ROOT / "messy_defects.yaml").exists()
