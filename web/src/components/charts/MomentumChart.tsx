import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { MomentumData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const BASELINE = "var(--schlouh-gold-muted)";
const GRID = "var(--schlouh-grid)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

export function MomentumChart({ data }: { data: MomentumData }) {
  const points = data.points.map((p) => ({ ...p, above: p.formScore >= data.baseline }));
  return (
    <ChartCard title={data.playerName} subtitle="Momentum (recency-weighted form)" footer="Sofascore · Baseline = season median. Recent games weighted higher.">
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
          <XAxis dataKey="date" tick={{ fill: TEXT_MUTED, fontSize: 10 }} axisLine={{ stroke: GRID }} tickLine={false} />
          <YAxis domain={["dataMin - 0.2", "dataMax + 0.2"]} tick={{ fill: TEXT_MUTED, fontSize: 10 }} axisLine={false} tickLine={false} width={28} tickFormatter={(v) => v.toFixed(1)} />
          <ReferenceLine
            y={data.baseline}
            stroke={BASELINE}
            strokeDasharray="4 4"
            label={{ value: "Season median", position: "right", fill: BASELINE, fontSize: 10 }}
          />
          <Area type="monotone" dataKey="formScore" stroke={GOLD} strokeWidth={2} fill={GOLD} fillOpacity={0.2} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
