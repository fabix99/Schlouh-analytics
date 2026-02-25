import { Legend, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";
import { ChartCard } from "../ChartCard";
import type { RadarCompareData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GOLD_MUTED = "var(--schlouh-gold-muted)";
const GRID = "var(--schlouh-grid)";

export function RadarCompareChart({ data }: { data: RadarCompareData }) {
  const chartData = data.labels.map((label, i) => ({
    subject: label,
    [data.player1.name]: data.player1.values[i],
    [data.player2.name]: data.player2.values[i],
    fullMark: 1,
  }));
  return (
    <ChartCard
      title={`${data.player1.name} vs ${data.player2.name}`}
      subtitle={data.sameLeague && data.competition ? `Radar · 0–1 scale · ${data.competition}` : "Radar · 0–1 scale"}
      footer={`Sofascore · Gold = ${data.player1.name}, Brown = ${data.player2.name}. 0 = league min, 1 = league max.`}
    >
      <ResponsiveContainer width="100%" height={280}>
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
          <PolarGrid stroke={GRID} />
          <PolarAngleAxis dataKey="subject" tick={{ fill: "var(--schlouh-text-secondary)", fontSize: 10 }} />
          <Legend wrapperStyle={{ fontSize: 10 }} formatter={(value) => <span style={{ color: "var(--schlouh-text-secondary)" }}>{value}</span>} />
          <Radar name={data.player1.name} dataKey={data.player1.name} stroke={GOLD} fill={GOLD} fillOpacity={0.25} strokeWidth={2} />
          <Radar name={data.player2.name} dataKey={data.player2.name} stroke={GOLD_MUTED} fill={GOLD_MUTED} fillOpacity={0.25} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
