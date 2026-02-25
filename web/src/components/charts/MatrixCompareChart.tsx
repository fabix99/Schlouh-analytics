import { ChartCard } from "../ChartCard";
import type { MatrixCompareData } from "../../types/charts";

const rowStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr auto auto",
  gap: 12,
  padding: "6px 0",
  borderBottom: "1px solid var(--schlouh-border)",
  fontSize: "0.9rem",
  alignItems: "center",
};
const winnerStyle = (winner: string, p1: string, p2: string): React.CSSProperties => ({
  color: winner === p1 ? "var(--schlouh-gold)" : winner === p2 ? "var(--schlouh-gold-muted)" : "var(--schlouh-text-secondary)",
  fontWeight: winner !== "Tie" ? 600 : 400,
});

export function MatrixCompareChart({ data }: { data: MatrixCompareData }) {
  const p1 = data.player1.name;
  const p2 = data.player2.name;
  return (
    <ChartCard
      title={`${p1} vs ${p2}`}
      subtitle={data.competition ? `Head-to-head · ${data.competition}` : "Head-to-head"}
      footer="Sofascore · +% = player 1 ahead. Very large % = scale difference (e.g. carry dist)."
    >
      <div style={{ marginTop: 4 }}>
        {data.rows.map((r) => (
          <div key={r.metric} style={rowStyle}>
            <span style={{ color: "var(--schlouh-text-secondary)" }}>{r.metric}</span>
            <span style={winnerStyle(r.winner, p1, p2)}>{r.winner}{r.effectPct ? ` ${r.effectPct}` : ""}</span>
          </div>
        ))}
      </div>
    </ChartCard>
  );
}
