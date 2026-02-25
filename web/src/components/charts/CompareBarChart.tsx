import { Bar, BarChart, Legend, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { CompareBarData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GOLD_MUTED = "var(--schlouh-gold-muted)";
const GRID = "var(--schlouh-grid)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

export function CompareBarChart({ data }: { data: CompareBarData }) {
  const chartData = data.metrics.map((m, i) => ({
    metric: m,
    [data.player1.name]: data.player1.values[i],
    [data.player2.name]: data.player2.values[i],
  }));
  const hasCarryDist = data.metrics.some((m) => /carry|dist/i.test(m));
  return (
    <ChartCard
      title={`${data.player1.name} vs ${data.player2.name}`}
      subtitle="Season per 90"
      footer={`Sofascore · Gold = ${data.player1.name}, Brown = ${data.player2.name}${hasCarryDist ? ". Large % on carry dist = scale difference." : ""}`}
    >
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 8, left: 72, bottom: 0 }}>
          <XAxis type="number" tick={{ fill: TEXT_MUTED, fontSize: 9 }} axisLine={{ stroke: GRID }} tickLine={false} />
          <YAxis type="category" dataKey="metric" tick={{ fill: TEXT_MUTED, fontSize: 9 }} axisLine={false} tickLine={false} width={70} />
          <Legend wrapperStyle={{ fontSize: 10 }} formatter={(value) => <span style={{ color: "var(--schlouh-text-secondary)" }}>{value}</span>} />
          <Bar dataKey={data.player1.name} fill={GOLD} radius={2} barSize={14} isAnimationActive={false} />
          <Bar dataKey={data.player2.name} fill={GOLD_MUTED} radius={2} barSize={14} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
