from __future__ import annotations

from typing import Any


def test_ground_truth_has_five_issues_and_locked_decisions(fast_ground_truth: dict[str, Any]) -> None:
    assert len(fast_ground_truth["issues"]) == 5
    assert {i["id"] for i in fast_ground_truth["issues"]} == {
        "GT-01",
        "GT-02",
        "GT-03",
        "GT-04",
        "GT-05",
    }
    assert fast_ground_truth["locked_decisions"]["currency"] == "PKR"
    assert fast_ground_truth["locked_decisions"]["months"] == 36


def test_ground_truth_has_red_herrings(fast_ground_truth: dict[str, Any]) -> None:
    assert len(fast_ground_truth["red_herrings"]) >= 3


def test_every_issue_has_required_fields(fast_ground_truth: dict[str, Any]) -> None:
    required = {
        "id",
        "category",
        "description",
        "affected_entities",
        "expected_direction",
        "expected_magnitude_range",
        "as_generated",
        "time_period",
        "expected_rca_driver",
    }
    for issue in fast_ground_truth["issues"]:
        assert required.issubset(issue.keys()), f"{issue['id']} missing {required - issue.keys()}"


def test_ground_truth_is_consistent_across_two_builds_of_the_same_seed(
    fast_config: Any, fast_dataset: Any
) -> None:
    from generator.ground_truth import build_ground_truth

    first = build_ground_truth(fast_config, fast_dataset)
    second = build_ground_truth(fast_config, fast_dataset)
    assert first == second
