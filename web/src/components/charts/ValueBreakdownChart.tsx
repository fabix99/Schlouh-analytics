import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { ValueBreakdownData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GRID = "var(--schlouh-grid)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

export function ValueBreakdownChart({ data }: { data: ValueBreakdownData }) {
  const chartData = data.categories.map((cat, i) => ({ name: cat, value: data.values[i] }));
  return (
    <ChartCard title={data.playerName} subtitle="Sofascore value breakdown (per 90)" footer="Sofascore · Contribution to rating (action-weighted impact per 90).">
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <XAxis dataKey="name" tick={{ fill: TEXT_MUTED, fontSize: 11 }} axisLine={{ stroke: GRID }} tickLine={false} />
          <YAxis tick={{ fill: TEXT_MUTED, fontSize: 10 }} axisLine={false} tickLine={false} width={36} label={{ value: "Contribution to rating", angle: -90, position: "insideLeft", fill: TEXT_MUTED, fontSize: 10 }} />
          <Bar dataKey="value" fill={GOLD} radius={4} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
