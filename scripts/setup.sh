#!/usr/bin/env bash
# One-shot environment setup for a fresh clone.
#
#   scripts/setup.sh                # deps + codeql-lib
#   scripts/setup.sh --codebases    # also fetch every third-party target app
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== python dependencies"
python3 -m pip install -r src/requirements.txt

echo "== codeql-lib (CodeQL standard library)"
bash "$ROOT/scripts/install_codeql_lib.sh"

if [ "${1:-}" = "--codebases" ]; then
  echo "== third-party target applications"
  bash "$ROOT/scripts/install_codebases.sh"
fi

if [ ! -f src/.env ]; then
  cp src/.env.example src/.env
  echo "== wrote src/.env from template — fill in CODEQL_BIN and Vertex AI settings"
fi

echo
echo "next:"
echo "  - edit src/.env (CODEQL_BIN, GOOGLE_APPLICATION_CREDENTIALS, VERTEX_PROJECT_ID)"
echo "  - build a CodeQL database (README: 'Build a CodeQL Database')"
echo "  - run:  cd src && python3 main.py --app <appname> --find-sinks --find-flows --validate-flows"
