# Airflow local config notes

`AIRFLOW_HOME` defaults to `platform/airflow_home` (created by `scripts/setup_airflow.sh`).

Key settings applied by the setup script:

- `core.executor` = `SequentialExecutor` (local, no Redis/Celery)
- `core.load_examples` = `False`
- `core.dags_folder` = `platform/airflow/dags`
