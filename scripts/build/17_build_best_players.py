"""
Step 17: Build match best-players and player profile extras from raw best_players_summary.json.

Reads data/raw/{season}/club/{competition_slug}/{match_id}/best_players_summary.json where present.
Outputs:
  - data/processed/17_match_best_players.parquet (match_id, player_of_match_id, player_of_match_name, best_home_player_ids, best_away_player_ids)
  - data/processed/17_player_profile_extras.parquet (player_id, match_id, height, market_value_eur, source)
  - data/processed/17_match_ai_insights.parquet (match_id, predictions flattened) from ai_insights_postmatch.json
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import RAW_DIR, PROCESSED_DIR, INDEX_DIR


def get_raw_match_dir(match_id: str, season: str, competition_slug: str) -> Optional[Path]:
    """Return path to match folder if it exists."""
    p = RAW_DIR / str(season) / "club" / competition_slug / str(match_id)
    return p if p.exists() else None


def _player_market_value_eur(raw: Any) -> Optional[float]:
    """Extract market value in EUR from proposedMarketValueRaw."""
    if not isinstance(raw, dict):
        return None
    v = raw.get("value")
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    matches = pd.read_csv(INDEX_DIR / "matches.csv")
    matches["match_id"] = matches["match_id"].astype(str)

    match_best_rows = []
    profile_rows = []

    for _, row in matches.iterrows():
        match_id = row["match_id"]
        season = row["season"]
        comp = row["competition_slug"]
        match_dir = get_raw_match_dir(match_id, season, comp)
        if not match_dir:
            continue
        path = match_dir / "best_players_summary.json"
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # Match-level: player of match + best home/away ids
        potm = data.get("playerOfTheMatch") or {}
        potm_player = potm.get("player") if isinstance(potm, dict) else {}
        player_of_match_id = potm_player.get("id") if isinstance(potm_player, dict) else None
        player_of_match_name = potm_player.get("name") if isinstance(potm_player, dict) else None

        best_home = data.get("bestHomeTeamPlayers") or []
        best_away = data.get("bestAwayTeamPlayers") or []
        home_ids = []
        away_ids = []
        for item in best_home if isinstance(best_home, list) else []:
            p = item.get("player") if isinstance(item, dict) else {}
            pid = p.get("id") if isinstance(p, dict) else None
            if pid is not None:
                home_ids.append(int(pid))
                # Profile extras: height, market value
                height = p.get("height") if isinstance(p, dict) else None
                mv_raw = p.get("proposedMarketValueRaw") if isinstance(p, dict) else None
                mv_eur = _player_market_value_eur(mv_raw)
                if height is not None or mv_eur is not None:
                    profile_rows.append({
                        "player_id": int(pid),
                        "match_id": match_id,
                        "height": int(height) if height is not None else None,
                        "market_value_eur": mv_eur,
                        "source": "best_players",
                    })
        for item in best_away if isinstance(best_away, list) else []:
            p = item.get("player") if isinstance(item, dict) else {}
            pid = p.get("id") if isinstance(p, dict) else None
            if pid is not None:
                away_ids.append(int(pid))
                height = p.get("height") if isinstance(p, dict) else None
                mv_raw = p.get("proposedMarketValueRaw") if isinstance(p, dict) else None
                mv_eur = _player_market_value_eur(mv_raw)
                if height is not None or mv_eur is not None:
                    profile_rows.append({
                        "player_id": int(pid),
                        "match_id": match_id,
                        "height": int(height) if height is not None else None,
                        "market_value_eur": mv_eur,
                        "source": "best_players",
                    })
        # Player of match might not be in best home/away
        if player_of_match_id is not None:
            pid = int(player_of_match_id) if not isinstance(player_of_match_id, int) else player_of_match_id
            potm_obj = potm_player if isinstance(potm_player, dict) else {}
            height = potm_obj.get("height")
            mv_raw = potm_obj.get("proposedMarketValueRaw")
            mv_eur = _player_market_value_eur(mv_raw)
            if height is not None or mv_eur is not None:
                profile_rows.append({
                    "player_id": pid,
                    "match_id": match_id,
                    "height": int(height) if height is not None else None,
                    "market_value_eur": mv_eur,
                    "source": "best_players",
                })

        match_best_rows.append({
            "match_id": match_id,
            "player_of_match_id": player_of_match_id,
            "player_of_match_name": player_of_match_name,
            "best_home_player_ids": ",".join(str(x) for x in home_ids) if home_ids else "",
            "best_away_player_ids": ",".join(str(x) for x in away_ids) if away_ids else "",
        })

    # Write match best players
    df_match = pd.DataFrame(match_best_rows)
    if not df_match.empty:
        out_path = PROCESSED_DIR / "17_match_best_players.parquet"
        df_match.to_parquet(out_path, index=False)
        print(f"Wrote {out_path} ({len(df_match)} rows)")
    else:
        print("No best_players_summary.json found; skipping 17_match_best_players.parquet")

    # Write player profile extras (dedupe by player_id + match_id)
    if profile_rows:
        df_prof = pd.DataFrame(profile_rows).drop_duplicates(subset=["player_id", "match_id"], keep="first")
        out_prof = PROCESSED_DIR / "17_player_profile_extras.parquet"
        df_prof.to_parquet(out_prof, index=False)
        print(f"Wrote {out_prof} ({len(df_prof)} rows)")
    else:
        print("No player profile extras; skipping 17_player_profile_extras.parquet")

    # Build 17_match_ai_insights from ai_insights_postmatch.json
    ai_rows = []
    for _, row in matches.iterrows():
        match_id = row["match_id"]
        season = row["season"]
        comp = row["competition_slug"]
        match_dir = get_raw_match_dir(match_id, season, comp)
        if not match_dir:
            continue
        path = match_dir / "ai_insights_postmatch.json"
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        pred = data.get("predictions") if isinstance(data, dict) else None
        if not isinstance(pred, dict):
            continue
        rec = {"match_id": match_id}
        rec["yellow_cards_pred"] = pred.get("yellowCards")
        rec["corners_pred"] = pred.get("corners")
        rec["both_teams_to_score_pred"] = pred.get("bothTeamsToScore")
        rec["home_score_pred"] = pred.get("homeNormaltimeScore")
        rec["away_score_pred"] = pred.get("awayNormaltimeScore")
        wp = pred.get("winningProbability") if isinstance(pred.get("winningProbability"), dict) else {}
        rec["winning_prob_home"] = wp.get("home")
        rec["winning_prob_draw"] = wp.get("draw")
        rec["winning_prob_away"] = wp.get("away")
        ai_rows.append(rec)
    if ai_rows:
        df_ai = pd.DataFrame(ai_rows)
        out_ai = PROCESSED_DIR / "17_match_ai_insights.parquet"
        df_ai.to_parquet(out_ai, index=False)
        print(f"Wrote {out_ai} ({len(df_ai)} rows)")
    else:
        print("No ai_insights_postmatch.json found; skipping 17_match_ai_insights.parquet")

    # H2H API: match_id, home_wins, away_wins, draws from h2h.json
    h2h_rows = []
    for _, row in matches.iterrows():
        match_id = row["match_id"]
        season = row["season"]
        comp = row["competition_slug"]
        match_dir = get_raw_match_dir(match_id, season, comp)
        if not match_dir:
            continue
        path = match_dir / "h2h.json"
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        duel = data.get("teamDuel") if isinstance(data, dict) else None
        if not isinstance(duel, dict):
            continue
        h2h_rows.append({
            "match_id": match_id,
            "home_wins": duel.get("homeWins"),
            "away_wins": duel.get("awayWins"),
            "draws": duel.get("draws"),
        })
    if h2h_rows:
        df_h2h = pd.DataFrame(h2h_rows)
        out_h2h = PROCESSED_DIR / "17_match_h2h_api.parquet"
        df_h2h.to_parquet(out_h2h, index=False)
        print(f"Wrote {out_h2h} ({len(df_h2h)} rows)")
    else:
        print("No h2h.json found; skipping 17_match_h2h_api.parquet")


if __name__ == "__main__":
    main()
