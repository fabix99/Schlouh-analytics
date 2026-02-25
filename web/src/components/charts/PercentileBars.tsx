import { Bar, BarChart, Cell, LabelList, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { PercentilesData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GOLD_MUTED = "var(--schlouh-gold-muted)";
const GRID = "var(--schlouh-grid)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

export function PercentileBars({ data }: { data: PercentilesData }) {
  const chartData = data.metrics.map((m, i) => ({ metric: m, percentile: data.percentiles[i] }));
  const positionLabel = data.position === "F" || data.position === "Fs" ? "forwards (Fs)" : `${data.position}s`;
  return (
    <ChartCard title={data.playerName} subtitle={`Percentiles vs ${data.competition} ${positionLabel} · n=${data.nPeers} peers`} footer="Sofascore · Gold ≥50th, Brown <50th">
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 8, left: 80, bottom: 0 }}>
          <XAxis type="number" domain={[0, 100]} tick={{ fill: TEXT_MUTED, fontSize: 10 }} axisLine={{ stroke: GRID }} tickLine={false} />
          <YAxis type="category" dataKey="metric" tick={{ fill: TEXT_MUTED, fontSize: 10 }} axisLine={false} tickLine={false} width={78} />
          <ReferenceLine x={50} stroke={GRID} strokeDasharray="2 2" />
          <Bar dataKey="percentile" radius={2} isAnimationActive={false}>
            <LabelList dataKey="percentile" position="right" fill={TEXT_MUTED} fontSize={9} formatter={(v: number) => `${Math.round(v)}`} />
            {chartData.map((_, i) => (
              <Cell key={i} fill={chartData[i].percentile >= 50 ? GOLD : GOLD_MUTED} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
