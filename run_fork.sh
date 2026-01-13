#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_forks.sh repos.csv
LIST_FILE="${1:-repos.csv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SCRIPT="${SCRIPT:-fork.py}"

if [ ! -f "$LIST_FILE" ]; then
  echo "List file not found: $LIST_FILE" >&2
  exit 2
fi

# Detect delimiter by extension
case "$LIST_FILE" in
  *.csv) DELIM=',' ;;
  *.tsv) DELIM=$'\t' ;;
  *.txt) DELIM=' ' ;;
  *) DELIM=',' ;;
esac

echo "Using list $LIST_FILE with delimiter [$DELIM]"

# Read each line, skip empty and comment lines starting with #
while IFS= read -r line || [ -n "$line" ]; do
  # Trim whitespace
  repo="$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  [ -z "$repo" ] && continue
  case "$repo" in
    \#*) continue ;; # comment
  esac

  echo "Processing repo: $repo"
  "$PYTHON_BIN" "$SCRIPT" --source "$repo" --config obinexus_targets.xml
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "fork.py failed for $repo with exit code $rc" >&2
  else
    echo "Completed $repo"
  fi
done < "$LIST_FILE"
r
