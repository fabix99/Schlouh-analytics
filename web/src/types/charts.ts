/** Form over time */
export interface FormData {
  playerSlug: string;
  playerName: string;
  nMatches: number;
  window: number;
  seasonAvg: { rating: number; xg90: number; goals90: number };
  points: Array<{ date: string; rollRating: number; rollRatingSeLower: number; rollRatingSeUpper: number; rollXg90: number; rollGoals90: number }>;
}

/** Momentum */
export interface MomentumData {
  playerSlug: string;
  playerName: string;
  baseline: number;
  points: Array<{ date: string; formScore: number }>;
}

/** Consistency */
export interface ConsistencyData {
  playerSlug: string;
  playerName: string;
  nMatches: number;
  xg: { mean: number; std: number; cv: number; band: string; bins: number[] };
  rating: { mean: number; std: number; cv: number; band: string; bins: number[] };
}

/** Distribution */
export interface DistributionData {
  playerSlug: string;
  playerName: string;
  nMatches: number;
  rating: { values: number[]; mean: number; median: number };
  xg: { values: number[]; mean: number; median: number };
}

/** Value breakdown */
export interface ValueBreakdownData {
  playerSlug: string;
  playerName: string;
  categories: string[];
  values: number[];
}

/** Radar profile */
export interface RadarProfileData {
  playerSlug: string;
  playerName: string;
  labels: string[];
  values: number[];
}

/** Goal timeline */
export interface GoalTimelineData {
  playerSlug: string;
  playerName: string;
  points: Array<{ date: string; goals: number; assists: number; gPlusA: number; roll5GPlusA: number }>;
}

/** Pass zones */
export interface PassZonesData {
  playerSlug: string;
  playerName: string;
  ownHalf: { total: number; per90: number; accuracy: number };
  oppositionHalf: { total: number; per90: number; accuracy: number };
}

/** Percentiles */
export interface PercentilesData {
  playerSlug: string;
  playerName: string;
  competition: string;
  position: string;
  nPeers: number;
  metrics: string[];
  percentiles: number[];
}

/** Compare bar */
export interface CompareBarData {
  player1: { slug: string; name: string; values: number[] };
  player2: { slug: string; name: string; values: number[] };
  metrics: string[];
}

/** Penalty profile */
export interface PenaltyProfileData {
  playerSlug: string;
  playerName: string;
  scored: number;
  missed: number;
  total: number;
  conversionPct: number;
}

/** Card risk */
export interface CardRiskData {
  playerSlug: string;
  playerName: string;
  points: Array<{ date: string; cardsPer90: number; foulsPer90: number }>;
  avgCardsPer90: number;
}

/** Matrix compare (head-to-head winner per metric) */
export interface MatrixCompareData {
  player1: { slug: string; name: string };
  player2: { slug: string; name: string };
  competition: string;
  rows: Array<{ metric: string; player1Value: number; player2Value: number; winner: string; effectPct: string }>;
}

/** Radar compare (two players, same scale) */
export interface RadarCompareData {
  player1: { slug: string; name: string; values: number[] };
  player2: { slug: string; name: string; values: number[] };
  labels: string[];
  sameLeague: boolean;
  competition: string;
}

/** Scatter compare (xG vs xA, two players + others) */
export interface ScatterCompareData {
  player1: { slug: string; name: string; xg_per90: number; xa_per90: number };
  player2: { slug: string; name: string; xg_per90: number; xa_per90: number };
  medianXg: number;
  medianXa: number;
  others: Array<{ xg_per90: number; xa_per90: number }>;
  nOthers: number;
  competition: string;
  minMinutes: number;
}

/** Archetype scatter (league: xG/90 vs key passes/90 by position) */
export interface ArchetypeData {
  competition: string;
  minMinutes: number;
  medianXg: number;
  medianKp: number;
  positions: Record<string, Array<{ xg_per90: number; kp_per90: number }>>;
  positionOrder: string[];
}
