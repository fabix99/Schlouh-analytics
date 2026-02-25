import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FormData, FormPoint } from "../../types/form";

const GOLD = "var(--schlouh-gold)";
const GRID = "var(--schlouh-grid)";
const TEXT = "var(--schlouh-text)";
const TEXT_MUTED = "var(--schlouh-text-muted)";
const BASELINE = "var(--schlouh-gold-muted)";

type FilterMode = "season" | "lastN" | "dateRange";

/** Season boundaries: start date (inclusive) for 2024/25 and 2025/26 */
const SEASONS = [
  { id: "2025-26", label: "2025/26", start: "2025-08-01", end: "2026-07-31" },
  { id: "2024-25", label: "2024/25", start: "2024-08-01", end: "2025-07-31" },
  { id: "all", label: "All", start: "", end: "" },
] as const;

const LAST_N_OPTIONS = [5, 10, 15, 20, 25, 30, 40, 50] as const;

function filterBySeason(points: FormPoint[], seasonId: string): FormPoint[] {
  if (seasonId === "all") return points;
  const season = SEASONS.find((s) => s.id === seasonId);
  if (!season || !season.start) return points;
  return points.filter((p) => p.date >= season.start && p.date <= season.end);
}

function filterByLastN(points: FormPoint[], n: number): FormPoint[] {
  if (n >= points.length) return points;
  return points.slice(-n);
}

function filterByDateRange(points: FormPoint[], start: string, end: string): FormPoint[] {
  if (!start || !end) return points;
  return points.filter((p) => p.date >= start && p.date <= end);
}

/** Custom tooltip for Rating per game: date, team, opponent, score */
function MatchTooltipContent({
  active,
  payload,
  lineLabel,
}: {
  active?: boolean;
  payload?: Array<{ value: number; payload: FormPoint & { dateLabel: string; gameRating: number } }>;
  label?: string;
  lineLabel: string;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  const value = payload[0].value;
  return (
    <div
      style={{
        background: "var(--schlouh-card)",
        border: "1px solid var(--schlouh-grid)",
        borderRadius: 8,
        padding: "10px 12px",
        color: TEXT,
        fontSize: 12,
        minWidth: 180,
      }}
    >
      <div style={{ marginBottom: 6, fontWeight: 600, color: "var(--schlouh-text-secondary)" }}>{p.date}</div>
      <div style={{ marginBottom: 4 }}>
        <span style={{ color: "var(--schlouh-text-muted)" }}>{lineLabel}:</span>{" "}
        <span style={{ fontWeight: 600 }}>{value.toFixed(2)}</span>
      </div>
      {p.team && (
        <div style={{ marginBottom: 2 }}>
          <span style={{ color: "var(--schlouh-text-muted)" }}>Played for:</span> {p.team}
        </div>
      )}
      {p.opponent && (
        <div style={{ marginBottom: 2 }}>
          <span style={{ color: "var(--schlouh-text-muted)" }}>vs</span> {p.opponent}
        </div>
      )}
      {(p.score ?? "").length > 0 && (
        <div>
          <span style={{ color: "var(--schlouh-text-muted)" }}>Score:</span> {p.score}
        </div>
      )}
    </div>
  );
}

export type FormChartVariant = "rolling" | "perGame";

interface FormOverTimeProps {
  data: FormData;
  /** "rolling" = rolling average (default), "perGame" = rating of each game */
  variant?: FormChartVariant;
  /** Show only rating panel for a compact/social card */
  ratingOnly?: boolean;
  className?: string;
}

export function FormOverTime({ data, variant = "rolling", ratingOnly = false, className = "" }: FormOverTimeProps) {
  const { playerName, seasonAvg, points, window: w } = data;
  const [filterMode, setFilterMode] = useState<FilterMode>("season");
  const [seasonFilter, setSeasonFilter] = useState<string>("2025-26");
  const [lastN, setLastN] = useState<number>(20);
  const [dateStart, setDateStart] = useState<string>("");
  const [dateEnd, setDateEnd] = useState<string>("");

  const filteredPoints = useMemo(() => {
    if (filterMode === "season") {
      const out = filterBySeason(points, seasonFilter);
      return out.length > 0 ? out : points;
    }
    if (filterMode === "lastN") {
      return filterByLastN(points, lastN);
    }
    if (filterMode === "dateRange") {
      const out = filterByDateRange(points, dateStart, dateEnd);
      return out.length > 0 ? out : points;
    }
    return points;
  }, [points, filterMode, seasonFilter, lastN, dateStart, dateEnd]);

  const pointsWithDate = useMemo(() => {
    return filteredPoints.map((p) => ({
      ...p,
      dateLabel: p.date.slice(0, 7),
      gameRating: p.rating ?? p.rollRating,
    }));
  }, [filteredPoints]);
  const nFiltered = filteredPoints.length;

  const isPerGame = variant === "perGame";
  const lineDataKey = isPerGame ? "gameRating" : "rollRating";
  const lineLabel = isPerGame ? "Rating" : "Form (rolling avg)";

  const ratingChart = (
    <ResponsiveContainer width="100%" height={ratingOnly ? 280 : 220}>
      <LineChart data={pointsWithDate} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis
          dataKey="dateLabel"
          tick={{ fill: TEXT_MUTED, fontSize: 11 }}
          axisLine={{ stroke: GRID }}
          tickLine={false}
        />
        <YAxis
          domain={["dataMin - 0.3", "dataMax + 0.3"]}
          tick={{ fill: TEXT_MUTED, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={32}
          tickFormatter={(v) => v.toFixed(1)}
        />
        <Tooltip
          contentStyle={{
            background: "var(--schlouh-card)",
            border: `1px solid ${GRID}`,
            borderRadius: 8,
            color: TEXT,
          }}
          labelStyle={{ color: TEXT_MUTED }}
          formatter={isPerGame ? undefined : (value: number) => [value.toFixed(2), lineLabel]}
          labelFormatter={isPerGame ? undefined : (label) => label}
          content={
            isPerGame ? (
              <MatchTooltipContent lineLabel={lineLabel} />
            ) : undefined
          }
        />
        <ReferenceLine
          y={seasonAvg.rating}
          stroke={BASELINE}
          strokeDasharray="4 4"
          strokeWidth={1.5}
          label={{ value: `Season avg ${seasonAvg.rating.toFixed(2)}`, position: "right", fill: BASELINE, fontSize: 10 }}
        />
        <Line
          type="monotone"
          dataKey={lineDataKey}
          stroke={GOLD}
          strokeWidth={2.5}
          dot={isPerGame}
          isAnimationActive={false}
          name={isPerGame ? "Game rating" : "Rolling avg"}
        />
      </LineChart>
    </ResponsiveContainer>
  );

  const filterControls = (
    <div style={filterRowStyle}>
      <div style={filterModeGroupStyle}>
        {(["season", "lastN", "dateRange"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            style={{ ...filterModeButtonStyle, ...(filterMode === mode ? filterModeButtonActiveStyle : {}) }}
            onClick={() => setFilterMode(mode)}
          >
            {mode === "season" ? "Season" : mode === "lastN" ? "Last N matches" : "Date range"}
          </button>
        ))}
      </div>
      <div style={filterInputsStyle}>
        {filterMode === "season" && (
          <select
            value={seasonFilter}
            onChange={(e) => setSeasonFilter(e.target.value)}
            style={selectStyle}
            aria-label="Season"
          >
            {SEASONS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        )}
        {filterMode === "lastN" && (
          <select
            value={lastN}
            onChange={(e) => setLastN(Number(e.target.value))}
            style={selectStyle}
            aria-label="Last N matches"
          >
            {LAST_N_OPTIONS.map((n) => (
              <option key={n} value={n}>
                Last {n} matches
              </option>
            ))}
          </select>
        )}
        {filterMode === "dateRange" && (
          <>
            <input
              type="date"
              value={dateStart}
              onChange={(e) => setDateStart(e.target.value)}
              style={inputStyle}
              aria-label="Start date"
            />
            <span style={dateRangeSepStyle}>→</span>
            <input
              type="date"
              value={dateEnd}
              onChange={(e) => setDateEnd(e.target.value)}
              style={inputStyle}
              aria-label="End date"
            />
          </>
        )}
      </div>
    </div>
  );

  const subtitleRolling = `Form (rolling ${w}-game avg) · Season avg ${seasonAvg.rating.toFixed(2)}`;
  const subtitlePerGame = "Rating per game · Season avg " + seasonAvg.rating.toFixed(2);
  const subtitleMain = isPerGame ? `Rating per game · ${nFiltered} games shown` : `Form over time (rolling ${w}-game avg) · ${nFiltered} games shown`;
  const footerNote = isPerGame ? "Sofascore · Gold = game rating, dashed = season avg" : "Sofascore · Gold = rolling avg, dashed = season avg";

  if (ratingOnly) {
    return (
      <article className={className} style={cardStyle}>
        <header style={headerStyle}>
          <div style={titleRowStyle}>
            <div>
              <h1 style={titleStyle}>{playerName}</h1>
              <p style={subtitleStyle}>{isPerGame ? subtitlePerGame : subtitleRolling}</p>
            </div>
          </div>
          {filterControls}
        </header>
        {ratingChart}
        <footer style={footerStyle}>
          <span style={logoStyle}>SCHLOUH</span>
          <span style={footnoteStyle}>Sofascore · {nFiltered} games shown</span>
        </footer>
      </article>
    );
  }

  return (
    <article className={className} style={cardStyle}>
      <header style={headerStyle}>
        <div style={titleRowStyle}>
          <div>
            <h1 style={titleStyle}>{playerName}</h1>
            <p style={subtitleStyle}>{subtitleMain}</p>
          </div>
        </div>
        {filterControls}
      </header>
      {ratingChart}
      <footer style={footerStyle}>
        <span style={logoStyle}>SCHLOUH</span>
        <span style={footnoteStyle}>{footerNote}</span>
      </footer>
    </article>
  );
}

const cardStyle: React.CSSProperties = {
  background: "var(--schlouh-card)",
  borderRadius: 12,
  padding: "24px 24px 16px",
  width: "100%",
};

const titleRowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  flexWrap: "wrap",
};

const filterRowStyle: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: 12,
  marginTop: 8,
};

const filterModeGroupStyle: React.CSSProperties = {
  display: "flex",
  gap: 0,
  borderRadius: 8,
  overflow: "hidden",
  border: "1px solid var(--schlouh-border)",
};

const filterModeButtonStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontSize: "var(--schlouh-label-size)",
  color: "var(--schlouh-text-secondary)",
  background: "var(--schlouh-surface)",
  border: "none",
  padding: "6px 12px",
  cursor: "pointer",
};

const filterModeButtonActiveStyle: React.CSSProperties = {
  color: "var(--schlouh-text)",
  background: "var(--schlouh-card)",
  fontWeight: 600,
};

const filterInputsStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const selectStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontSize: "var(--schlouh-label-size)",
  color: "var(--schlouh-text)",
  background: "var(--schlouh-surface)",
  border: "1px solid var(--schlouh-border)",
  borderRadius: 8,
  padding: "6px 10px",
  cursor: "pointer",
};

const inputStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontSize: "var(--schlouh-label-size)",
  color: "var(--schlouh-text)",
  background: "var(--schlouh-surface)",
  border: "1px solid var(--schlouh-border)",
  borderRadius: 8,
  padding: "6px 10px",
};

const dateRangeSepStyle: React.CSSProperties = {
  color: "var(--schlouh-text-muted)",
  fontSize: "var(--schlouh-label-size)",
};

const headerStyle: React.CSSProperties = {
  marginBottom: 8,
};

const titleStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontWeight: 700,
  fontSize: "var(--schlouh-title-size)",
  color: "var(--schlouh-text)",
  margin: 0,
};

const subtitleStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontSize: "var(--schlouh-label-size)",
  color: "var(--schlouh-text-secondary)",
  margin: "4px 0 0 0",
};

const footerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginTop: 8,
  paddingTop: 12,
  borderTop: "1px solid var(--schlouh-border)",
};

const logoStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontWeight: 700,
  fontSize: "var(--schlouh-label-size)",
  color: "var(--schlouh-gold)",
  letterSpacing: "0.05em",
};

const footnoteStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontSize: "var(--schlouh-footnote-size)",
  color: "var(--schlouh-text-muted)",
};
