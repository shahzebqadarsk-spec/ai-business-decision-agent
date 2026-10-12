import { useState } from "react";
import { Card } from "../components/ui/card";
import { DecisionChart } from "../components/decision/DecisionChart";
import { EvidenceDrawer } from "../components/evidence/EvidenceDrawer";
import { useCompareScenarios, useDecisions } from "../hooks/useDecision";
import { useScenarios } from "../hooks/useScenario";
import { DECISION_CRITERIA } from "../types/decision";
import type { DecisionCriterion, DecisionRun } from "../types/decision";

const CRITERION_LABEL: Record<DecisionCriterion, string> = {
  profitability: "Profitability",
  growth: "Growth",
  cost_efficiency: "Cost efficiency",
};

export function DecisionPage() {
  const [name, setName] = useState("");
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([]);
  const [weightInputs, setWeightInputs] = useState<Record<DecisionCriterion, string>>({
    profitability: "",
    growth: "",
    cost_efficiency: "",
  });
  const [activeRun, setActiveRun] = useState<DecisionRun | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);

  const scenariosQuery = useScenarios();
  const decisionsQuery = useDecisions();
  const compareMutation = useCompareScenarios();

  const run = activeRun ?? decisionsQuery.data?.[0] ?? null;

  function toggleScenario(id: string) {
    setSelectedScenarioIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  function handleCompare() {
    const filledWeights = Object.entries(weightInputs).filter(([, v]) => v.trim() !== "");
    const criteria_weights =
      filledWeights.length === 0
        ? null
        : Object.fromEntries(filledWeights.map(([k, v]) => [k, Number(v)]));

    compareMutation.mutate(
      {
        name: name.trim() || "Untitled comparison",
        scenario_ids: selectedScenarioIds,
        criteria_weights,
      },
      { onSuccess: (newRun) => setActiveRun(newRun) },
    );
  }

  const canCompare = selectedScenarioIds.length >= 2 && !compareMutation.isPending;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Decision Scoring</h2>
      </div>
      <p className="text-xs text-slate-400">
        Ranks two or more Scenarios you already built against each other on profitability,
        growth, and cost efficiency -- each criterion a deterministic average of that
        scenario's own results, never a new projection. The AI recommends; a human approves:
        every ranked option is advisory Evidence, not a decision made for you.
      </p>

      <Card>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col text-xs text-slate-500">
            Comparison name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Which growth lever first?"
              className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div className="mt-3">
          <p className="mb-1 text-xs text-slate-500">Scenarios to compare (pick at least 2)</p>
          {scenariosQuery.isLoading && <p className="text-sm text-slate-500">Loading scenarios...</p>}
          {scenariosQuery.data && scenariosQuery.data.length === 0 && (
            <p className="text-sm text-slate-400">
              No scenarios yet. Run some on the Scenario / What-If tab first.
            </p>
          )}
          <div className="flex flex-col gap-1">
            {(scenariosQuery.data ?? []).map((s) => (
              <label key={s.id} className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={selectedScenarioIds.includes(s.id)}
                  onChange={() => toggleScenario(s.id)}
                />
                {s.name}
                <span className="text-xs text-slate-400">({s.status})</span>
              </label>
            ))}
          </div>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {DECISION_CRITERIA.map((criterion) => (
            <label key={criterion} className="flex flex-col text-xs text-slate-500">
              {CRITERION_LABEL[criterion]} weight
              <input
                type="number"
                step={0.05}
                min={0}
                max={1}
                placeholder="auto"
                value={weightInputs[criterion]}
                onChange={(e) => setWeightInputs((prev) => ({ ...prev, [criterion]: e.target.value }))}
                className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
          ))}
        </div>
        <p className="mt-1 text-xs text-slate-400">
          Leave all three blank for an equal split. If any are filled, the ones you fill in must
          sum to ~1.0 -- they are never silently renormalized.
        </p>

        <div className="mt-3">
          <button
            type="button"
            onClick={handleCompare}
            disabled={!canCompare}
            className="rounded bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
          >
            {compareMutation.isPending ? "Comparing..." : "Compare"}
          </button>
        </div>

        {compareMutation.isError && (
          <p className="mt-2 text-xs text-red-600">
            {compareMutation.error instanceof Error
              ? compareMutation.error.message
              : "Could not compare these scenarios."}
          </p>
        )}
      </Card>

      {decisionsQuery.isLoading && (
        <Card>
          <p className="text-sm text-slate-500">Loading decisions...</p>
        </Card>
      )}
      {decisionsQuery.isError && (
        <Card>
          <p className="text-sm text-red-600">Could not reach the backend.</p>
        </Card>
      )}
      {!run && decisionsQuery.data && decisionsQuery.data.length === 0 && (
        <Card>
          <p className="text-sm text-slate-400">No comparisons yet. Run one above.</p>
        </Card>
      )}

      {run && run.status === "insufficient_data" && (
        <Card>
          <p className="text-sm text-amber-700">{run.status_reason}</p>
        </Card>
      )}

      {run && (
        <>
          <Card>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-700">{run.name}</p>
              {run.fact_evidence_id && (
                <button
                  type="button"
                  onClick={() => setSelectedEvidenceId(run.fact_evidence_id)}
                  className="text-xs text-blue-700 underline"
                >
                  View comparison evidence
                </button>
              )}
            </div>
            <p className="text-xs text-slate-400">
              Weights used:{" "}
              {Object.entries(run.criteria_weights)
                .map(([k, v]) => `${k}=${(v as number).toFixed(2)}`)
                .join(", ")}
            </p>
          </Card>

          <DecisionChart options={run.options} />

          <Card className="overflow-x-auto">
            <p className="mb-2 text-sm font-semibold text-slate-600">Ranked options</p>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-slate-400">
                  <th className="pb-1 pr-3">Rank</th>
                  <th className="pb-1 pr-3">Scenario</th>
                  <th className="pb-1 pr-3">Score</th>
                  <th className="pb-1 pr-3">Rationale</th>
                  <th className="pb-1">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {run.options.map((o) => (
                  <tr key={o.id} className="border-t border-slate-100 align-top">
                    <td className="py-1 pr-3 text-slate-700">{o.rank ?? "—"}</td>
                    <td className="py-1 pr-3 text-slate-700">{o.title}</td>
                    <td className="py-1 pr-3 text-slate-700">
                      {o.score !== null ? o.score.toFixed(3) : "—"}
                    </td>
                    <td className="py-1 pr-3 text-slate-500">{o.rationale ?? "—"}</td>
                    <td className="py-1">
                      {o.evidence_id && (
                        <button
                          type="button"
                          onClick={() => setSelectedEvidenceId(o.evidence_id)}
                          className="text-blue-700 underline"
                        >
                          View
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}

      <EvidenceDrawer evidenceId={selectedEvidenceId} onClose={() => setSelectedEvidenceId(null)} />
    </div>
  );
}
