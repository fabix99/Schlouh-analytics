#!/usr/bin/env bash
# Install Airflow into the project venv and initialise a local AIRFLOW_HOME.
# Run from repo root: bash platform/scripts/setup_airflow.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

AIRFLOW_VERSION="${AIRFLOW_VERSION:-2.10.4}"
PYTHON_VERSION="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

echo "Installing apache-airflow==${AIRFLOW_VERSION} (Python ${PYTHON_VERSION})..."
pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"
# Keep typing_extensions new enough for pydantic_core (Airflow deps can pin too low)
pip install -U "typing_extensions>=4.12.0"

export AIRFLOW_HOME="${AIRFLOW_HOME:-$ROOT/platform/airflow_home}"
mkdir -p "$AIRFLOW_HOME"

export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=SequentialExecutor
export AIRFLOW__CORE__DAGS_FOLDER="$ROOT/platform/airflow/dags"
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="sqlite:///${AIRFLOW_HOME}/airflow.db"

# Persist env for later shells
cat > "$AIRFLOW_HOME/.env" <<EOF
export AIRFLOW_HOME=$AIRFLOW_HOME
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=SequentialExecutor
export AIRFLOW__CORE__DAGS_FOLDER=$ROOT/platform/airflow/dags
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=sqlite:///${AIRFLOW_HOME}/airflow.db
export SCHLOUH_PROJECT_ROOT=$ROOT
export SCHLOUH_PYTHON=$ROOT/.venv/bin/python
export PATH=$ROOT/.venv/bin:\$PATH
EOF

airflow db migrate
airflow dags list | head -40

echo "OK AIRFLOW_HOME=$AIRFLOW_HOME"
echo "Source env: source $AIRFLOW_HOME/.env"
echo "Test DAG:   airflow dags test schlouh_platform_pipeline $(date -u +%Y-%m-%d)"
