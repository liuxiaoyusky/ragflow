#!/usr/bin/env bash
set -euo pipefail

# One-click sync with upstream using rebase.
# Usage:
#   scripts/sync-upstream.sh [-b branch] [-p]
#
# Options:
#   -b branch   Target branch to sync (default: main)
#   -p          Push to origin after successful rebase (uses --force-with-lease)

TARGET_BRANCH="main"
PUSH_AFTER=false

while getopts ":b:p" opt; do
  case "$opt" in
    b)
      TARGET_BRANCH="$OPTARG"
      ;;
    p)
      PUSH_AFTER=true
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 2
      ;;
    :)
      echo "Option -$OPTARG requires an argument" >&2
      exit 2
      ;;
  esac
done

if ! command -v git >/dev/null 2>&1; then
  echo "git is not installed." >&2
  exit 1
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "This is not a git repository." >&2
  exit 1
fi

# Ensure remotes
if ! git remote get-url upstream >/dev/null 2>&1; then
  echo "Remote 'upstream' is not configured. Please add it first, e.g.:" >&2
  echo "  git remote add upstream https://github.com/infiniflow/ragflow.git" >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Remote 'origin' is not configured. Please add your fork as origin." >&2
  echo "  git remote add origin https://github.com/<your-user>/<your-repo>.git" >&2
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"

echo "[1/5] Fetch upstream..."
git fetch upstream --prune

echo "[2/5] Checkout target branch: ${TARGET_BRANCH}"
if git show-ref --verify --quiet "refs/heads/${TARGET_BRANCH}"; then
  git checkout "${TARGET_BRANCH}"
else
  # Create local branch tracking origin if exists, otherwise create from upstream
  if git show-ref --verify --quiet "refs/remotes/origin/${TARGET_BRANCH}"; then
    git checkout -b "${TARGET_BRANCH}" "origin/${TARGET_BRANCH}"
  else
    git checkout -b "${TARGET_BRANCH}" "upstream/${TARGET_BRANCH}"
  fi
fi

echo "[3/5] Rebase ${TARGET_BRANCH} onto upstream/${TARGET_BRANCH}"
git rebase "upstream/${TARGET_BRANCH}"

echo "[4/5] Done rebase. You are up-to-date with upstream/${TARGET_BRANCH}."

if [ "$PUSH_AFTER" = true ]; then
  if git remote get-url origin >/dev/null 2>&1; then
    echo "[5/5] Pushing ${TARGET_BRANCH} to origin with --force-with-lease"
    git push --force-with-lease origin "${TARGET_BRANCH}"
  else
    echo "[5/5] Skip push: 'origin' is not configured."
  fi
else
  echo "[5/5] Skip push (no -p). To push: git push --force-with-lease origin ${TARGET_BRANCH}"
fi

echo "Done."


