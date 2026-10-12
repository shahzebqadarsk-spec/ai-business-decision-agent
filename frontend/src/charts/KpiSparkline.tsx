import { Line, LineChart, ResponsiveContainer } from "recharts";

export interface SparklinePoint {
  month: string;
  value: number;
}

export function KpiSparkline({ data }: { data: SparklinePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={48}>
      <LineChart data={data}>
        <Line type="monotone" dataKey="value" stroke="#1d4ed8" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
