import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { PassZonesData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GOLD_MUTED = "var(--schlouh-gold-muted)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

export function PassZonesChart({ data }: { data: PassZonesData }) {
  const volumeData = [
    { zone: "Own half", total: data.ownHalf.total, per90: data.ownHalf.per90 },
    { zone: "Opp. half", total: data.oppositionHalf.total, per90: data.oppositionHalf.per90 },
  ];
  const accData = [
    { zone: "Own half", accuracy: data.ownHalf.accuracy },
    { zone: "Opp. half", accuracy: data.oppositionHalf.accuracy },
  ];
  return (
    <ChartCard title={data.playerName} subtitle="Pass zones (season)" footer="Sofascore">
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <div style={{ fontSize: 11, color: TEXT_MUTED, marginBottom: 4 }}>Volume (total passes; per 90: {data.ownHalf.per90.toFixed(1)} / {data.oppositionHalf.per90.toFixed(1)})</div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={volumeData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <XAxis dataKey="zone" tick={{ fill: TEXT_MUTED, fontSize: 10 }} />
              <YAxis tick={{ fill: TEXT_MUTED, fontSize: 10 }} width={40} label={{ value: "Passes", angle: -90, position: "insideLeft", fill: TEXT_MUTED, fontSize: 9 }} />
              <Bar dataKey="total" fill={GOLD} radius={4} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <div style={{ fontSize: 11, color: TEXT_MUTED, marginBottom: 4 }}>Accuracy %</div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={accData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <XAxis dataKey="zone" tick={{ fill: TEXT_MUTED, fontSize: 10 }} />
              <YAxis domain={[0, 100]} tick={{ fill: TEXT_MUTED, fontSize: 10 }} width={36} />
              <Bar dataKey="accuracy" fill={GOLD_MUTED} radius={4} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </ChartCard>
  );
}
