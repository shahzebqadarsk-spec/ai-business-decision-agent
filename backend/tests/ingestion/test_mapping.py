from __future__ import annotations

from app.ingestion.canonical_fields import FACT_SALES_FIELDS
from app.ingestion.mapping import propose_mapping, propose_rule_based


def test_exact_name_match_is_confidence_1() -> None:
    result = propose_rule_based("customer_id", FACT_SALES_FIELDS)
    assert result is not None
    assert result.proposed_field == "customer_id"
    assert result.confidence == 1.0
    assert result.method == "rule"


def test_synonym_match_is_confidence_1() -> None:
    result = propose_rule_based("sku", FACT_SALES_FIELDS)
    assert result is not None
    assert result.proposed_field == "product_id"
    assert result.confidence == 1.0


def test_fuzzy_match_has_partial_confidence() -> None:
    result = propose_rule_based("product_code", FACT_SALES_FIELDS)
    assert result is not None
    assert 0.6 <= result.confidence < 1.0
    assert result.proposed_field == "product_id"


def test_unrelated_column_name_does_not_match() -> None:
    result = propose_rule_based("zzz_completely_unrelated_xyz", FACT_SALES_FIELDS)
    assert result is None or result.confidence < 0.6


def test_rule_based_mapping_is_deterministic() -> None:
    first = propose_rule_based("qty", FACT_SALES_FIELDS)
    second = propose_rule_based("qty", FACT_SALES_FIELDS)
    assert first == second


def test_propose_mapping_without_llm_falls_back_to_rule_only() -> None:
    proposal = propose_mapping(
        source_column="customer_id",
        sample_values=["CUST-0001"],
        inferred_dtype="string",
        fields=FACT_SALES_FIELDS,
        llm_client=None,
    )
    assert proposal.proposed_field == "customer_id"
    assert proposal.method == "rule"


def test_propose_mapping_returns_unresolved_shape_for_unmatched_column() -> None:
    proposal = propose_mapping(
        source_column="totally_unrelated_qwerty",
        sample_values=["x"],
        inferred_dtype="string",
        fields=FACT_SALES_FIELDS,
        llm_client=None,
    )
    assert proposal.proposed_field is None
    assert proposal.confidence == 0.0
