#!/bin/sh
set -eu
export DATABASE_URL=postgresql://neighbor:test-only-password@127.0.0.1:15432/neighborhub_test
export NEO4J_URI=bolt://127.0.0.1:17687
export NEO4J_PASSWORD=test-only-password
export ENVIRONMENT=development DEMO_MODE=true RUN_INTEGRATION=1 APP_URL=http://localhost:3000 GRAPH_ENABLED=true
exec "${PYTHON:-.venv/bin/python}" -m unittest discover -s backend/tests -p 'test_*.py' -v
