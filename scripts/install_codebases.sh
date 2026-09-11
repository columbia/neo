#!/usr/bin/env bash
# Fetch the third-party target applications used for evaluation.
#
# The small, hand-written test apps (codebases/go, codebases/java,
# codebases/python, codebases/javascript) are first-party and live in this repo.
# Everything below is upstream code, checked out at the pinned commit the
# CodeQL databases were built from.  Nothing here is committed to this repo.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CB="$ROOT/codebases"
mkdir -p "$CB"

# name|git url|pinned commit
APPS=(
  "AutoGPT|https://github.com/Significant-Gravitas/AutoGPT.git|3f19cba28f935415b25c4b95b6ae0f0297fb9151"
  "mlflow|https://github.com/mlflow/mlflow.git|85d667353364d30ca46c787fae75811f9995748e"
  "keystone-classic|https://github.com/keystonejs/keystone-classic.git|6e5ba1142a0909c64a1a38e20f31fcf9bed6e4db"
  "N4si-python|https://github.com/N4si/microservices-python-app.git|9f08966e8c38d304fe84dd0da5ae7a088fde6918"
  "gradio|https://github.com/gradio-app/gradio.git|b5a9f6688ef424e0ac286dc9bf03812dae1468c6"
  "pyramid|https://github.com/Pylons/pyramid.git|eb0e01a0fd7aff84c345b1c43bd4fa9d2fe04441"
  "reflex|https://github.com/reflex-dev/reflex.git|4468e148330ea7f016c70ad241f87473549a7828"
  "web3.py|https://github.com/ethereum/web3.py.git|a1c2e83a523c8da07939aeafffd12ba98531d3be"
)

# Optionally restrict to a subset:  ./install_codebases.sh AutoGPT mlflow
WANT=("$@")
want() { [ ${#WANT[@]} -eq 0 ] && return 0; for w in "${WANT[@]}"; do [ "$w" = "$1" ] && return 0; done; return 1; }

for entry in "${APPS[@]}"; do
  IFS='|' read -r name url sha <<< "$entry"
  want "$name" || continue
  dest="$CB/$name"
  if [ -n "$(ls -A "$dest" 2>/dev/null || true)" ]; then
    echo "== $name already present, skipping"
    continue
  fi
  echo "== $name @ ${sha:0:12}"
  rm -rf "$dest"; mkdir -p "$dest"
  git -C "$dest" init -q
  git -C "$dest" remote add origin "$url"
  if git -C "$dest" fetch --depth 1 origin "$sha" 2>/dev/null; then
    git -C "$dest" checkout -q FETCH_HEAD
  else
    echo "   (bare-SHA fetch unavailable; full clone then checkout)"
    rm -rf "$dest"
    git clone -q "$url" "$dest"
    git -C "$dest" checkout -q "$sha"
  fi
done

echo "done. Build CodeQL databases next — see README 'Build a CodeQL Database'."
