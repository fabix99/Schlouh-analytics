import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { ArchetypeData } from "../../types/charts";

const GRID = "var(--schlouh-grid)";
const TEXT_MUTED = "var(--schlouh-text-muted)";
const POS_COLORS: Record<string, string> = {
  GK: "var(--schlouh-text-muted)",
  Def: "#5c9ead",
  Mid: "var(--schlouh-gold-muted)",
  Fwd: "var(--schlouh-gold)",
};

export function ArchetypeChart({ data }: { data: ArchetypeData }) {
  const allPoints: Array<{ xg_per90: number; kp_per90: number; position: string }> = [];
  for (const pos of data.positionOrder) {
    const pts = data.positions[pos] || [];
    for (const p of pts) {
      allPoints.push({ ...p, position: pos });
    }
  }
  return (
    <ChartCard
      title="Player archetypes"
      subtitle={`${data.competition} · min ${data.minMinutes} min · By position · Dotted = median`}
      footer="Sofascore · xG/90 vs Key passes/90 by position. GK=gray, Def=teal, Mid=brown, Fwd=gold."
    >
      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis type="number" dataKey="xg_per90" name="xG/90" tick={{ fill: TEXT_MUTED, fontSize: 9 }} />
          <YAxis type="number" dataKey="kp_per90" name="Key passes/90" tick={{ fill: TEXT_MUTED, fontSize: 9 }} width={40} />
          <ReferenceLine x={data.medianXg} stroke="var(--schlouh-border)" strokeDasharray="2 2" />
          <ReferenceLine y={data.medianKp} stroke="var(--schlouh-border)" strokeDasharray="2 2" />
          {data.positionOrder.map((pos) => {
            const pts = (data.positions[pos] || []).map((p) => ({ ...p, position: pos }));
            if (pts.length === 0) return null;
            return (
              <Scatter
                key={pos}
                data={pts}
                fill={POS_COLORS[pos] ?? "var(--schlouh-text-muted)"}
                fillOpacity={0.6}
                name={pos}
                isAnimationActive={false}
              />
            );
          })}
        </ScatterChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
