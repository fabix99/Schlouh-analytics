import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { ScatterCompareData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GOLD_MUTED = "var(--schlouh-gold-muted)";
const GRID = "var(--schlouh-grid)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

export function ScatterCompareChart({ data }: { data: ScatterCompareData }) {
  const othersData = data.others.map((o) => ({ x: o.xg_per90, y: o.xa_per90 }));
  const p1 = { x: data.player1.xg_per90, y: data.player1.xa_per90, name: data.player1.name };
  const p2 = { x: data.player2.xg_per90, y: data.player2.xa_per90, name: data.player2.name };
  return (
    <ChartCard
      title={`${data.player1.name} vs ${data.player2.name}`}
      subtitle={`xG/90 vs xA/90 · ${data.competition} (min ${data.minMinutes} min) · n=${data.nOthers} others`}
      footer={`Sofascore · Dotted = league median. Gold = ${data.player1.name}, Brown = ${data.player2.name}.`}
    >
      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis type="number" dataKey="x" name="xG/90" tick={{ fill: TEXT_MUTED, fontSize: 9 }} />
          <YAxis type="number" dataKey="y" name="xA/90" tick={{ fill: TEXT_MUTED, fontSize: 9 }} width={36} />
          <ReferenceLine x={data.medianXg} stroke="var(--schlouh-border)" strokeDasharray="2 2" />
          <ReferenceLine y={data.medianXa} stroke="var(--schlouh-border)" strokeDasharray="2 2" />
          <Scatter data={othersData} fill="var(--schlouh-text-muted)" fillOpacity={0.35} isAnimationActive={false} />
          <Scatter data={[p1]} fill={GOLD} name={data.player1.name} isAnimationActive={false} />
          <Scatter data={[p2]} fill={GOLD_MUTED} name={data.player2.name} isAnimationActive={false} />
          <Tooltip
            contentStyle={{ background: "var(--schlouh-card)", border: "1px solid var(--schlouh-border)" }}
            formatter={(val: number) => [val.toFixed(3), ""]}
            labelFormatter={(label) => (typeof label === "string" ? label : "")}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
