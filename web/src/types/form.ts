/** Data contract: form-over-time (rolling 5G) — matches export/scripts/export_form.py */

export interface FormPoint {
  date: string;
  /** Per-game Sofascore rating (optional for backward compatibility with old exports) */
  rating?: number;
  rollRating: number;
  rollRatingSeLower: number;
  rollRatingSeUpper: number;
  rollXg90: number;
  rollGoals90: number;
  /** Player's team name (for tooltip) */
  team?: string;
  /** Opponent team name (for tooltip) */
  opponent?: string;
  /** Match score e.g. "2-1" (home-away), when available */
  score?: string | null;
}

export interface FormSeasonAvg {
  rating: number;
  xg90: number;
  goals90: number;
}

export interface FormData {
  playerSlug: string;
  playerName: string;
  nMatches: number;
  window: number;
  seasonAvg: FormSeasonAvg;
  points: FormPoint[];
}
