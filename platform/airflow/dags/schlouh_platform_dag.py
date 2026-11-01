"""
Airflow DAG — production Schlouh platform path:

  pandas (dbt owns 03/08) → DLT → dbt core+serving marts → validate → AI index

Optional Sofascore DLT extract is a separate task (rate-limited / often 403).
"""

from __future__ import annotations

import os
import shlex
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator

_DAG_FILE = Path(__file__).resolve()
_DEFAULT_ROOT = _DAG_FILE.parents[3]
PROJECT_ROOT = Path(os.environ.get("SCHLOUH_PROJECT_ROOT", str(_DEFAULT_ROOT)))
PYTHON = os.environ.get("SCHLOUH_PYTHON", "python")

_root = shlex.quote(str(PROJECT_ROOT))
_python = shlex.quote(PYTHON)

default_args = {
    "owner": "schlouh",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="schlouh_platform_pipeline",
    description="Full path: pandas → DLT → dbt marts → validate → AI index",
    default_args=default_args,
    schedule=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["schlouh", "platform", "dlt", "dbt", "airflow"],
) as dag:
    # Uses interleaved script: skip pandas 03/08, dbt owns core marts, export, rest.
    platform_full = BashOperator(
        task_id="run_platform_full",
        bash_command=f"cd {_root} && bash platform/scripts/run_platform_full.sh --skip-pandas",
    )

    # Live API extract (optional; fails soft if Sofascore 403s). Limit keeps DAG safe.
    dlt_extract = BashOperator(
        task_id="dlt_extract_pl_sample",
        bash_command=(
            f"cd {_root} && {_python} platform/pipelines/sofascore_extract.py "
            f"--competition england-premier-league --season 2025-26 --limit 2 "
            f"--also-write-raw || true"
        ),
    )

    dlt_extract >> platform_full
