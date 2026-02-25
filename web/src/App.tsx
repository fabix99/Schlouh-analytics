import { useEffect, useState } from "react";
import { ArchetypeChart } from "./components/charts/ArchetypeChart";
import { CardRiskChart } from "./components/charts/CardRiskChart";
import { CompareBarChart } from "./components/charts/CompareBarChart";
import { ConsistencyCard } from "./components/charts/ConsistencyCard";
import { DistributionCard } from "./components/charts/DistributionCard";
import { FormOverTime } from "./components/charts/FormOverTime";
import { GoalTimelineChart } from "./components/charts/GoalTimelineChart";
import { MatrixCompareChart } from "./components/charts/MatrixCompareChart";
import { MomentumChart } from "./components/charts/MomentumChart";
import { PassZonesChart } from "./components/charts/PassZonesChart";
import { PenaltyProfileChart } from "./components/charts/PenaltyProfileChart";
import { PercentileBars } from "./components/charts/PercentileBars";
import { RadarCompareChart } from "./components/charts/RadarCompareChart";
import { RadarProfileChart } from "./components/charts/RadarProfileChart";
import { ScatterCompareChart } from "./components/charts/ScatterCompareChart";
import { ValueBreakdownChart } from "./components/charts/ValueBreakdownChart";
import type {
  ArchetypeData,
  CardRiskData,
  CompareBarData,
  ConsistencyData,
  DistributionData,
  GoalTimelineData,
  MatrixCompareData,
  MomentumData,
  PassZonesData,
  PenaltyProfileData,
  PercentilesData,
  RadarCompareData,
  RadarProfileData,
  ScatterCompareData,
  ValueBreakdownData,
} from "./types/charts";
import type { FormData as FormDataLegacy } from "./types/form";
import "./design/tokens.css";

const PLAYER_SLUG = "kylian-mbappe";
const COMPARE_SLUG = "robert-lewandowski";

const DATA_URLS = {
  form: `/data/player/${PLAYER_SLUG}/form.json`,
  momentum: `/data/player/${PLAYER_SLUG}/momentum.json`,
  consistency: `/data/player/${PLAYER_SLUG}/consistency.json`,
  distribution: `/data/player/${PLAYER_SLUG}/distribution.json`,
  valueBreakdown: `/data/player/${PLAYER_SLUG}/value_breakdown.json`,
  radarProfile: `/data/player/${PLAYER_SLUG}/radar_profile.json`,
  goalTimeline: `/data/player/${PLAYER_SLUG}/goal_timeline.json`,
  passZones: `/data/player/${PLAYER_SLUG}/pass_zones.json`,
  percentiles: `/data/player/${PLAYER_SLUG}/percentiles.json`,
  penalty: `/data/player/${PLAYER_SLUG}/penalty.json`,
  cardRisk: `/data/player/${PLAYER_SLUG}/card_risk.json`,
  compareBar: `/data/compare/${PLAYER_SLUG}_vs_${COMPARE_SLUG}_bar.json`,
  compareMatrix: `/data/compare/${PLAYER_SLUG}_vs_${COMPARE_SLUG}_matrix.json`,
  compareRadar: `/data/compare/${PLAYER_SLUG}_vs_${COMPARE_SLUG}_radar.json`,
  compareScatter: `/data/compare/${PLAYER_SLUG}_vs_${COMPARE_SLUG}_scatter.json`,
  archetype: `/data/league/archetype_spain-laliga.json`,
};

function fetchJson<T>(url: string): Promise<T> {
  return fetch(url).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${url} ${r.status}`))));
}

export default function App() {
  const [form, setForm] = useState<FormDataLegacy | null>(null);
  const [momentum, setMomentum] = useState<MomentumData | null>(null);
  const [consistency, setConsistency] = useState<ConsistencyData | null>(null);
  const [distribution, setDistribution] = useState<DistributionData | null>(null);
  const [valueBreakdown, setValueBreakdown] = useState<ValueBreakdownData | null>(null);
  const [radarProfile, setRadarProfile] = useState<RadarProfileData | null>(null);
  const [goalTimeline, setGoalTimeline] = useState<GoalTimelineData | null>(null);
  const [passZones, setPassZones] = useState<PassZonesData | null>(null);
  const [percentiles, setPercentiles] = useState<PercentilesData | null>(null);
  const [penalty, setPenalty] = useState<PenaltyProfileData | null>(null);
  const [cardRisk, setCardRisk] = useState<CardRiskData | null>(null);
  const [compareBar, setCompareBar] = useState<CompareBarData | null>(null);
  const [compareMatrix, setCompareMatrix] = useState<MatrixCompareData | null>(null);
  const [compareRadar, setCompareRadar] = useState<RadarCompareData | null>(null);
  const [compareScatter, setCompareScatter] = useState<ScatterCompareData | null>(null);
  const [archetype, setArchetype] = useState<ArchetypeData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchJson<FormDataLegacy>(DATA_URLS.form).then(setForm).catch(() => setForm(null)),
      fetchJson<MomentumData>(DATA_URLS.momentum).then(setMomentum).catch(() => setMomentum(null)),
      fetchJson<ConsistencyData>(DATA_URLS.consistency).then(setConsistency).catch(() => setConsistency(null)),
      fetchJson<DistributionData>(DATA_URLS.distribution).then(setDistribution).catch(() => setDistribution(null)),
      fetchJson<ValueBreakdownData>(DATA_URLS.valueBreakdown).then(setValueBreakdown).catch(() => setValueBreakdown(null)),
      fetchJson<RadarProfileData>(DATA_URLS.radarProfile).then(setRadarProfile).catch(() => setRadarProfile(null)),
      fetchJson<GoalTimelineData>(DATA_URLS.goalTimeline).then(setGoalTimeline).catch(() => setGoalTimeline(null)),
      fetchJson<PassZonesData>(DATA_URLS.passZones).then(setPassZones).catch(() => setPassZones(null)),
      fetchJson<PercentilesData>(DATA_URLS.percentiles).then(setPercentiles).catch(() => setPercentiles(null)),
      fetchJson<PenaltyProfileData>(DATA_URLS.penalty).then(setPenalty).catch(() => setPenalty(null)),
      fetchJson<CardRiskData>(DATA_URLS.cardRisk).then(setCardRisk).catch(() => setCardRisk(null)),
      fetchJson<CompareBarData>(DATA_URLS.compareBar).then(setCompareBar).catch(() => setCompareBar(null)),
      fetchJson<MatrixCompareData>(DATA_URLS.compareMatrix).then(setCompareMatrix).catch(() => setCompareMatrix(null)),
      fetchJson<RadarCompareData>(DATA_URLS.compareRadar).then(setCompareRadar).catch(() => setCompareRadar(null)),
      fetchJson<ScatterCompareData>(DATA_URLS.compareScatter).then(setCompareScatter).catch(() => setCompareScatter(null)),
      fetchJson<ArchetypeData>(DATA_URLS.archetype).then(setArchetype).catch(() => setArchetype(null)),
    ])
      .then(() => setError(null))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={pageStyle}>
        <p style={{ color: "var(--schlouh-text-secondary)" }}>Loading all charts…</p>
      </div>
    );
  }

  if (error && !form) {
    return (
      <div style={pageStyle}>
        <p style={{ color: "var(--schlouh-negative)" }}>
          No data found. From project root run: <code>python export/scripts/export_all.py</code> then refresh.
        </p>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <header style={headerStyle}>
        <span style={logoStyle}>SCHLOUH</span>
        <h1 style={titleStyle}>Charts — {PLAYER_SLUG}</h1>
      </header>

      <div style={gridStyle}>
        {form && <FormOverTime data={form} />}
        {form && <FormOverTime data={form} variant="perGame" />}
        {momentum && <MomentumChart data={momentum} />}
        {consistency && <ConsistencyCard data={consistency} />}
        {distribution && <DistributionCard data={distribution} />}
        {valueBreakdown && <ValueBreakdownChart data={valueBreakdown} />}
        {radarProfile && <RadarProfileChart data={radarProfile} />}
        {goalTimeline && <GoalTimelineChart data={goalTimeline} />}
        {passZones && <PassZonesChart data={passZones} />}
        {percentiles && <PercentileBars data={percentiles} />}
        {penalty && <PenaltyProfileChart data={penalty} />}
        {cardRisk && <CardRiskChart data={cardRisk} />}
        {compareBar && <CompareBarChart data={compareBar} />}
        {compareMatrix && <MatrixCompareChart data={compareMatrix} />}
        {compareRadar && <RadarCompareChart data={compareRadar} />}
        {compareScatter && <ScatterCompareChart data={compareScatter} />}
        {archetype && <ArchetypeChart data={archetype} />}
      </div>

      <footer style={footerStyle}>Data: Sofascore · Stats per 90 where stated</footer>
    </div>
  );
}

const pageStyle: React.CSSProperties = {
  minHeight: "100vh",
  background: "var(--schlouh-bg)",
  padding: "24px 32px 32px",
  fontFamily: "var(--schlouh-font)",
  color: "var(--schlouh-text)",
};

const headerStyle: React.CSSProperties = {
  marginBottom: 24,
};

const logoStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontWeight: 700,
  fontSize: "0.75rem",
  color: "var(--schlouh-gold)",
  letterSpacing: "0.08em",
  display: "block",
  marginBottom: 4,
};

const titleStyle: React.CSSProperties = {
  fontFamily: "var(--schlouh-font)",
  fontWeight: 700,
  fontSize: "1.5rem",
  color: "var(--schlouh-text)",
  margin: 0,
};

const gridStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 20,
  alignItems: "stretch",
  maxWidth: 1100,
  margin: "0 auto",
};

const footerStyle: React.CSSProperties = {
  marginTop: 32,
  paddingTop: 16,
  borderTop: "1px solid var(--schlouh-border)",
  fontSize: "var(--schlouh-footnote-size)",
  color: "var(--schlouh-text-muted)",
};
