import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ChartCard } from "../ChartCard";
import type { DistributionData } from "../../types/charts";

const GOLD = "var(--schlouh-gold)";
const GOLD_MUTED = "var(--schlouh-gold-muted)";
const TEXT_MUTED = "var(--schlouh-text-muted)";

function toHistogram(values: number[], numBins: number = 14): { bin: string; count: number }[] {
  const min = Math.min(...values);
  const max = Math.max(...values) || 1;
  const step = (max - min) / numBins || 0.01;
  const buckets: { bin: string; count: number }[] = [];
  for (let i = 0; i < numBins; i++) {
    const lo = min + i * step;
    const hi = i === numBins - 1 ? max + 0.001 : lo + step;
    const count = values.filter((x) => x >= lo && x < hi).length;
    buckets.push({ bin: lo.toFixed(2), count });
  }
  return buckets;
}

export function DistributionCard({ data }: { data: DistributionData }) {
  const ratingHist = toHistogram(data.rating.values);
  const xgHist = toHistogram(data.xg.values);
  const xgSkew = data.xg.mean > data.xg.median ? " · xG right-skewed" : "";
  const ratingSkew = data.rating.mean > data.rating.median ? " · Rating right-skewed" : "";
  return (
    <ChartCard title={data.playerName} subtitle={`Distribution · n=${data.nMatches} · Mean/median shown${xgSkew}${ratingSkew}`} footer="Sofascore">
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <div style={{ fontSize: 11, color: TEXT_MUTED, marginBottom: 4 }}>Rating (μ={data.rating.mean.toFixed(2)}, med={data.rating.median.toFixed(2)})</div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={ratingHist} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <XAxis dataKey="bin" tick={{ fill: TEXT_MUTED, fontSize: 8 }} />
              <YAxis tick={{ fill: TEXT_MUTED, fontSize: 9 }} width={24} />
              <Bar dataKey="count" fill={GOLD} radius={2} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <div style={{ fontSize: 11, color: TEXT_MUTED, marginBottom: 4 }}>xG per match (μ={data.xg.mean.toFixed(2)}, med={data.xg.median.toFixed(2)})</div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={xgHist} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <XAxis dataKey="bin" tick={{ fill: TEXT_MUTED, fontSize: 8 }} />
              <YAxis tick={{ fill: TEXT_MUTED, fontSize: 9 }} width={24} />
              <Bar dataKey="count" fill={GOLD_MUTED} radius={2} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </ChartCard>
  );
}
