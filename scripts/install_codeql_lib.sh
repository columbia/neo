#!/usr/bin/env bash
# Fetch the CodeQL standard library (github/codeql) used via --search-path.
# Third-party code — not vendored in this repo. Pinned to the commit the
# project was developed against.
set -euo pipefail

CODEQL_LIB_COMMIT="4f8166a661eb374bf733bd8d155922f9f728f4ca"   # codeql-cli/latest-509-g4f8166a661e
CODEQL_LIB_URL="https://github.com/github/codeql.git"
DEST="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/codeql-lib}"

if [ -e "$DEST/ql" ] || [ -e "$DEST/java/ql" ]; then
  echo "codeql-lib already present at $DEST"
  exit 0
fi

echo "Fetching codeql-lib @ ${CODEQL_LIB_COMMIT:0:12} -> $DEST"
mkdir -p "$DEST"
git -C "$DEST" init -q
git -C "$DEST" remote add origin "$CODEQL_LIB_URL" 2>/dev/null || true
# Shallow-fetch just the pinned commit (fast; ~1 GB checkout).
if ! git -C "$DEST" fetch --depth 1 origin "$CODEQL_LIB_COMMIT" 2>/dev/null; then
  echo "note: server does not allow fetching a bare SHA; fetching default branch"
  git -C "$DEST" fetch --depth 1 origin
fi
git -C "$DEST" checkout -q FETCH_HEAD 2>/dev/null || git -C "$DEST" checkout -q "$CODEQL_LIB_COMMIT"
echo "done."
