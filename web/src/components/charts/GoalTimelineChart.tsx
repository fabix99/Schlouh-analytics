import { Bar, ComposedChart, Legend, Line, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { GoalTimelineData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GOLD_MUTED = "var(--schlouh-gold-muted)";
const GRID = "var(--schlouh-grid)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

export function GoalTimelineChart({ data }: { data: GoalTimelineData }) {
  const points = data.points.map((p) => ({ ...p, dateShort: p.date.slice(0, 7) }));
  return (
    <ChartCard title={data.playerName} subtitle="Goals & assists per match (chronological)" footer="Sofascore · Bars = match G+A, line = rolling 5-game avg.">
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <XAxis dataKey="dateShort" tick={{ fill: TEXT_MUTED, fontSize: 9 }} axisLine={{ stroke: GRID }} tickLine={false} />
          <YAxis yAxisId="left" tick={{ fill: TEXT_MUTED, fontSize: 10 }} axisLine={false} tickLine={false} width={24} label={{ value: "Goals / Assists", angle: -90, position: "insideLeft", fill: TEXT_MUTED, fontSize: 9 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fill: TEXT_MUTED, fontSize: 10 }} axisLine={false} tickLine={false} width={28} label={{ value: "Rolling 5-game G+A", angle: 90, position: "insideRight", fill: TEXT_MUTED, fontSize: 9 }} />
          <Legend wrapperStyle={{ fontSize: 10 }} formatter={(value) => <span style={{ color: "var(--schlouh-text-secondary)" }}>{value}</span>} />
          <Bar yAxisId="left" dataKey="goals" fill={GOLD} radius={2} isAnimationActive={false} name="Goals" />
          <Bar yAxisId="left" dataKey="assists" fill={GOLD_MUTED} radius={2} isAnimationActive={false} name="Assists" />
          <Line yAxisId="right" type="monotone" dataKey="roll5GPlusA" stroke="var(--schlouh-text-secondary)" strokeWidth={1.5} dot={false} isAnimationActive={false} name="Rolling 5-game G+A" />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
