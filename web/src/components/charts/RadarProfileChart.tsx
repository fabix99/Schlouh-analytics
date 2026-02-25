import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";
import { ChartCard } from "../ChartCard";
import type { RadarProfileData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GRID = "var(--schlouh-grid)";

export function RadarProfileChart({ data }: { data: RadarProfileData }) {
  const chartData = data.labels.map((label, i) => ({ subject: label, value: data.values[i], fullMark: 1 }));
  return (
    <ChartCard title={data.playerName} subtitle="Season profile (per 90, 0–1 scale)" footer="Sofascore · 0 = league min, 1 = league max (per 90).">
      <ResponsiveContainer width="100%" height={260}>
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
          <PolarGrid stroke={GRID} />
          <PolarAngleAxis dataKey="subject" tick={{ fill: "var(--schlouh-text-secondary)", fontSize: 11 }} />
          <Radar name={data.playerName} dataKey="value" stroke={GOLD} fill={GOLD} fillOpacity={0.3} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
