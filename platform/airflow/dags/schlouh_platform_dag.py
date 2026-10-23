"""
Airflow DAG: Schlouh platform slice — DLT load → dbt build → validate → AI index.

Designed for LocalExecutor / SequentialExecutor (local or docker-compose).
Does not call the live Sofascore API; uses platform/fixtures by default.
"""

from __future__ import annotations

import os
import shlex
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator

# Project root: .../Sofascore Scrapping
# In Docker this is /opt/airflow/project (mounted). Locally inferred from this file.
_DAG_FILE = Path(__file__).resolve()
_DEFAULT_ROOT = _DAG_FILE.parents[3]  # platform/airflow/dags -> repo root
PROJECT_ROOT = Path(os.environ.get("SCHLOUH_PROJECT_ROOT", str(_DEFAULT_ROOT)))

PYTHON = os.environ.get("SCHLOUH_PYTHON", "python")
DBT_PROFILES_DIR = PROJECT_ROOT / "platform" / "dbt"

# Quote paths that may contain spaces (e.g. "Schlouh Analytics")
_root = shlex.quote(str(PROJECT_ROOT))
_python = shlex.quote(PYTHON)
_dbt_profiles = shlex.quote(str(DBT_PROFILES_DIR))
_dbt_dir = shlex.quote(str(PROJECT_ROOT / "platform" / "dbt"))

default_args = {
    "owner": "schlouh",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="schlouh_platform_pipeline",
    description="DLT → DuckDB → dbt → validate → AI retrieval index",
    default_args=default_args,
    schedule=None,  # manual / triggered; set e.g. "@daily" when you want a schedule
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["schlouh", "platform", "dlt", "dbt", "airflow"],
) as dag:
    init_warehouse = BashOperator(
        task_id="init_warehouse",
        bash_command=f"cd {_root} && {_python} platform/scripts/init_warehouse.py",
    )

    dlt_load = BashOperator(
        task_id="dlt_load",
        bash_command=(
            f"cd {_root} && {_python} platform/pipelines/sofascore_load.py "
            f"--source platform/fixtures"
        ),
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {_dbt_dir} && dbt build --profiles-dir {_dbt_profiles}",
    )

    validate = BashOperator(
        task_id="validate_platform",
        bash_command=f"cd {_root} && {_python} platform/scripts/validate_platform.py",
    )

    build_retrieval_index = BashOperator(
        task_id="build_retrieval_index",
        bash_command=f"cd {_root} && {_python} platform/ai/build_retrieval_index.py",
    )

    init_warehouse >> dlt_load >> dbt_build >> validate >> build_retrieval_index
