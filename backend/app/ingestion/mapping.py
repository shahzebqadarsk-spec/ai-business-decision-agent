"""Three-layer semantic mapping: deterministic rules, then an optional LLM *proposal*,
then mandatory human confirmation.

The LLM (Layer 2) only ever proposes a field name, a confidence, and a reason -- it never
writes to the canonical schema and never executes SQL/Python (see `app/llm/`'s structured-
output contract: the response is schema-validated JSON, nothing else is ever evaluated).
Layer 3 (human confirmation) is enforced by the API/materialization layer, not here: this
module only ever returns *proposals*.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from app.ingestion.canonical_fields import CanonicalFieldSpec
from app.llm.client import LLMClient

_RULE_EXACT_CONFIDENCE = 1.0
_RULE_FUZZY_MIN_CONFIDENCE = 0.6


@dataclass
class MappingProposal:
    source_column: str
    proposed_field: str | None
    confidence: float
    method: str  # "rule" | "llm"
    reason: str


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def propose_rule_based(source_column: str, fields: tuple[CanonicalFieldSpec, ...]) -> MappingProposal | None:
    normalized_source = _normalize(source_column)
    best: tuple[float, CanonicalFieldSpec] | None = None

    for spec in fields:
        candidates = (spec.name, *spec.synonyms)
        for candidate in candidates:
            normalized_candidate = _normalize(candidate)
            if normalized_source == normalized_candidate:
                return MappingProposal(
                    source_column=source_column,
                    proposed_field=spec.name,
                    confidence=_RULE_EXACT_CONFIDENCE,
                    method="rule",
                    reason=f"Exact match against canonical field/synonym '{candidate}'.",
                )
            ratio = difflib.SequenceMatcher(None, normalized_source, normalized_candidate).ratio()
            if best is None or ratio > best[0]:
                best = (ratio, spec)

    if best is not None and best[0] >= _RULE_FUZZY_MIN_CONFIDENCE:
        ratio, spec = best
        return MappingProposal(
            source_column=source_column,
            proposed_field=spec.name,
            confidence=round(ratio, 4),
            method="rule",
            reason=f"Fuzzy name match against canonical field '{spec.name}' (ratio={ratio:.2f}).",
        )
    return None


def propose_llm_assisted(
    *,
    client: LLMClient,
    source_column: str,
    sample_values: list[str],
    inferred_dtype: str,
    fields: tuple[CanonicalFieldSpec, ...],
) -> MappingProposal:
    """Layer 2: ask the LLM to propose a field from the allowed canonical set, given only
    the column name, dtype, and a few sample values -- never the full dataset, and the
    response is schema-validated so the LLM cannot propose anything outside the allowed
    field list (or return anything other than this exact shape)."""
    allowed_fields = [spec.name for spec in fields]
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "proposed_field": {"type": "string", "enum": [*allowed_fields, "NONE"]},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
        "required": ["proposed_field", "confidence", "reason"],
    }
    system_prompt = (
        "You map a spreadsheet column to one canonical business field, or 'NONE' if no "
        "field fits. You must only choose from the allowed field list. You never modify "
        "any database or execute code -- you only propose a mapping."
    )
    user_prompt = (
        f"Column name: {source_column!r}\n"
        f"Inferred dtype: {inferred_dtype}\n"
        f"Sample values: {sample_values[:5]!r}\n"
        f"Allowed canonical fields: {allowed_fields!r}\n"
        "Propose the single best-fitting canonical field."
    )
    result = client.complete(system_prompt=system_prompt, user_prompt=user_prompt, schema=schema)
    parsed = result.parsed or {}
    proposed_field = parsed.get("proposed_field")
    if proposed_field == "NONE" or proposed_field not in allowed_fields:
        proposed_field = None
    confidence_raw = parsed.get("confidence", 0.0)
    confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.0
    reason = str(parsed.get("reason", "")) or "LLM proposal (no reason given)."
    return MappingProposal(
        source_column=source_column,
        proposed_field=proposed_field,
        confidence=max(0.0, min(1.0, confidence)),
        method="llm",
        reason=reason,
    )


def propose_mapping(
    *,
    source_column: str,
    sample_values: list[str],
    inferred_dtype: str,
    fields: tuple[CanonicalFieldSpec, ...],
    llm_client: LLMClient | None,
) -> MappingProposal:
    rule_result = propose_rule_based(source_column, fields)
    if rule_result is not None and rule_result.confidence >= _RULE_EXACT_CONFIDENCE:
        return rule_result

    if llm_client is not None:
        llm_result = propose_llm_assisted(
            client=llm_client,
            source_column=source_column,
            sample_values=sample_values,
            inferred_dtype=inferred_dtype,
            fields=fields,
        )
        if rule_result is None or llm_result.confidence > rule_result.confidence:
            return llm_result

    if rule_result is not None:
        return rule_result

    return MappingProposal(
        source_column=source_column,
        proposed_field=None,
        confidence=0.0,
        method="rule",
        reason="No rule-based or LLM match found for this column.",
    )
