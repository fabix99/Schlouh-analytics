import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { ConsistencyData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GOLD_MUTED = "var(--schlouh-gold-muted)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

function histogram(bins: number[], numBins: number = 12) {
  const min = Math.min(...bins);
  const max = Math.max(...bins) || 1;
  const step = (max - min) / numBins || 0.01;
  const counts: { bin: string; count: number }[] = [];
  for (let i = 0; i < numBins; i++) {
    const lo = min + i * step;
    const hi = lo + step;
    const count = bins.filter((x) => x >= lo && (i === numBins - 1 ? x <= hi + 0.001 : x < hi)).length;
    counts.push({ bin: lo.toFixed(2), count });
  }
  return counts;
}

export function ConsistencyCard({ data }: { data: ConsistencyData }) {
  const xgHist = histogram(data.xg.bins);
  const ratingHist = histogram(data.rating.bins);
  return (
    <ChartCard title={data.playerName} subtitle={`Consistency · n=${data.nMatches} · CV xG=${data.xg.cv.toFixed(2)} (${data.xg.band}), Rating=${data.rating.cv.toFixed(2)} (${data.rating.band}). High/Low = variability.`} footer="Sofascore · CV = σ/μ (std/mean)">
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <div style={{ fontSize: 11, color: "var(--schlouh-text-muted)", marginBottom: 4 }}>xG per match (μ={data.xg.mean})</div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={xgHist} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <XAxis dataKey="bin" tick={{ fill: TEXT_MUTED, fontSize: 9 }} />
              <YAxis tick={{ fill: TEXT_MUTED, fontSize: 9 }} width={24} />
              <Bar dataKey="count" fill={GOLD} radius={2} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--schlouh-text-muted)", marginBottom: 4 }}>Rating per match (μ={data.rating.mean})</div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={ratingHist} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <XAxis dataKey="bin" tick={{ fill: TEXT_MUTED, fontSize: 9 }} />
              <YAxis tick={{ fill: TEXT_MUTED, fontSize: 9 }} width={24} />
              <Bar dataKey="count" fill={GOLD_MUTED} radius={2} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </ChartCard>
  );
}
