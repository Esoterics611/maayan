#!/usr/bin/env bash
# Stop hook: a session may not end with a red branch.
# When Python files changed in the working tree, run `make lint` and
# `make typecheck`; on failure exit 2 so the errors are fed back to Claude
# to fix before the turn is allowed to end.
set -u

payload=$(cat)
# Don't re-fire on the continuation this hook itself triggered.
if printf '%s' "$payload" | grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || exit 0

# Only verify when Python files changed (tracked or untracked).
if ! git status --porcelain -- '*.py' 2>/dev/null | grep -q .; then
  exit 0
fi

if ! out=$(make lint 2>&1); then
  { echo "Stop blocked — make lint failed:"; printf '%s\n' "$out" | tail -40; } >&2
  exit 2
fi
if ! out=$(make typecheck 2>&1); then
  { echo "Stop blocked — make typecheck failed:"; printf '%s\n' "$out" | tail -60; } >&2
  exit 2
fi
exit 0
