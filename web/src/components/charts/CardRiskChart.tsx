import { CartesianGrid, Line, LineChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { CardRiskData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GRID = "var(--schlouh-grid)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

export function CardRiskChart({ data }: { data: CardRiskData }) {
  return (
    <ChartCard
      title={data.playerName}
      subtitle={`Card risk · Avg ${data.avgCardsPer90.toFixed(2)} cards/90`}
      footer="Sofascore · Cards/90 over time (yellow + red)"
    >
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data.points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="date" tick={{ fill: TEXT_MUTED, fontSize: 9 }} tickFormatter={(v) => v.slice(0, 7)} />
          <YAxis tick={{ fill: TEXT_MUTED, fontSize: 9 }} width={32} />
          <Line type="monotone" dataKey="cardsPer90" stroke={GOLD} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} name="Cards/90" />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
