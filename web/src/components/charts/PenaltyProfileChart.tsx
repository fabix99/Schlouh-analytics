import { Bar, BarChart, Cell, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { PenaltyProfileData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const NEGATIVE = "var(--schlouh-negative)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

export function PenaltyProfileChart({ data }: { data: PenaltyProfileData }) {
  const barData = [
    { name: "Scored", value: data.scored, fill: GOLD },
    { name: "Missed", value: data.missed, fill: NEGATIVE },
  ];
  return (
    <ChartCard
      title={data.playerName}
      subtitle={`Penalties · n=${data.total} · Conversion ${data.conversionPct}%${data.conversionPct >= 78 ? " (above league fwd avg)" : ""}`}
      footer="Sofascore · League fwd avg ~78%"
    >
      <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
        <ResponsiveContainer width="50%" minWidth={140} height={120}>
          <BarChart data={barData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <XAxis dataKey="name" tick={{ fill: TEXT_MUTED, fontSize: 10 }} />
            <YAxis tick={{ fill: TEXT_MUTED, fontSize: 9 }} width={28} />
            <Bar dataKey="value" radius={4} isAnimationActive={false}>
              {barData.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--schlouh-gold)" }}>
          {data.conversionPct}%<span style={{ fontSize: "0.85rem", fontWeight: 400, color: "var(--schlouh-text-secondary)" }}> ({data.scored}/{data.total})</span>
        </div>
      </div>
    </ChartCard>
  );
}
