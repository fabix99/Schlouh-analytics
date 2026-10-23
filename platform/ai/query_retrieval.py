#!/usr/bin/env python3
"""
Query the AI-ready FTS index over warehouse marts.

Example:
  python platform/ai/query_retrieval.py "high scoring forward"
  python platform/ai/query_retrieval.py "Union Saint-Gilloise" --limit 5
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WAREHOUSE = ROOT / "data" / "warehouse" / "schlouh.duckdb"


def warehouse_path() -> Path:
    env = os.environ.get("SOFASCORE_WAREHOUSE_PATH")
    if env:
        p = Path(env)
        return p if p.is_absolute() else ROOT / p
    return DEFAULT_WAREHOUSE


def main() -> int:
    parser = argparse.ArgumentParser(description="Search AI retrieval documents")
    parser.add_argument("query", help="Natural language / keyword query")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    path = warehouse_path()
    if not path.exists():
        print(f"Warehouse missing: {path}", file=sys.stderr)
        return 1

    con = duckdb.connect(str(path), read_only=True)
    con.execute("INSTALL fts")
    con.execute("LOAD fts")

    # Escape single quotes in query for SQL literal
    q = args.query.replace("'", "''")
    # DuckDB names the FTS macro after schema+table: fts_ai_retrieval_documents
    try:
        rows = con.execute(
            f"""
            SELECT
                doc_id,
                doc_type,
                title,
                content,
                fts_ai_retrieval_documents.match_bm25(doc_id, '{q}') AS score
            FROM ai.retrieval_documents
            WHERE score IS NOT NULL
            ORDER BY score DESC
            LIMIT {int(args.limit)}
            """
        ).fetchdf()
    except Exception as e:
        print(f"FTS query fallback ({e})", file=sys.stderr)
        rows = con.execute(
            """
            SELECT doc_id, doc_type, title, content, 0.0 AS score
            FROM ai.retrieval_documents
            WHERE content ILIKE '%' || ? || '%' OR title ILIKE '%' || ? || '%'
            LIMIT ?
            """,
            [args.query, args.query, args.limit],
        ).fetchdf()

    if rows.empty:
        print("No hits.")
        return 0
    print(rows.to_string(index=False))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
