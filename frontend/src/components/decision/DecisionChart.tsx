import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "../ui/card";
import type { DecisionOption } from "../../types/decision";

const RANK_COLORS = ["#059669", "#2563eb", "#7c3aed", "#d97706", "#64748b"];

function colorForRank(rank: number | null): string {
  if (rank === null) return "#cbd5e1";
  return RANK_COLORS[(rank - 1) % RANK_COLORS.length];
}

/** Composite score per scored option, highest (rank 1) drawn first -- no confidence band and
 * no baseline-vs-actual split, unlike ForecastChart/ScenarioChart: this is a single ranking
 * number per option, not a time series. Unscored options (score=None) are never plotted here --
 * there is nothing to bar-chart about a number that was never fabricated in the first place --
 * and are listed separately by the caller instead. */
export function DecisionChart({ options }: { options: DecisionOption[] }) {
  const scored = options
    .filter((o) => o.score !== null)
    .sort((a, b) => (a.rank ?? Number.MAX_SAFE_INTEGER) - (b.rank ?? Number.MAX_SAFE_INTEGER))
    .map((o) => ({ title: o.title, score: o.score as number, rank: o.rank }));

  if (scored.length === 0) {
    return (
      <Card>
        <p className="text-sm text-slate-400">No scored options to chart yet.</p>
      </Card>
    );
  }

  return (
    <Card>
      <h4 className="mb-2 text-sm font-semibold text-slate-600">Composite score by option</h4>
      <ResponsiveContainer width="100%" height={Math.max(180, scored.length * 48)}>
        <BarChart data={scored} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" fontSize={11} />
          <YAxis type="category" dataKey="title" fontSize={11} width={140} />
          <Tooltip
            formatter={(value: unknown, _name, item: { payload?: { rank: number | null } }) => {
              const rank = item.payload?.rank;
              const score = typeof value === "number" ? value.toFixed(3) : "—";
              return [score, rank !== undefined && rank !== null ? `score (rank ${rank})` : "score"];
            }}
          />
          <Bar dataKey="score" isAnimationActive={false}>
            {scored.map((entry) => (
              <Cell key={entry.title} fill={colorForRank(entry.rank)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
