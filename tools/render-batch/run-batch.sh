#!/bin/sh
# Run a batch of render jobs, one at a time, resuming after a kill.
#
# usage: run-batch.sh <jobs.tsv> <workdir>
#
# jobs.tsv holds one job per line: <name><TAB><command>
# A job is skipped when <workdir>/done/<name>.done exists, so a batch
# killed mid-run resumes from the last completed job instead of
# redoing it. Output is written to <workdir>/out/<name>.txt through a
# temporary name and renamed, so a killed job leaves no partial
# output behind. Progress goes to <workdir>/batch.log.
set -u

if [ $# -ne 2 ]; then
  echo "usage: run-batch.sh <jobs.tsv> <workdir>" >&2
  exit 2
fi

JOBS=$1
WORK=$2
OUT=$WORK/out
DONE=$WORK/done
LOG=$WORK/batch.log

mkdir -p "$OUT" "$DONE"

while IFS="$(printf '\t')" read -r name cmd; do
  [ -z "${name:-}" ] && continue
  case "$name" in \#*) continue ;; esac

  if [ -f "$DONE/$name.done" ]; then
    echo "$(date -u +%FT%TZ) skip    $name (already done)" >> "$LOG"
    continue
  fi

  echo "$(date -u +%FT%TZ) start   $name" >> "$LOG"
  tmp="$OUT/$name.txt.part"
  if sh -c "$cmd" > "$tmp" 2>> "$LOG"; then
    mv "$tmp" "$OUT/$name.txt"
    echo "$(date -u +%FT%TZ) done    $name" >> "$LOG"
    printf '%s\n' "$name" > "$DONE/$name.done"
  else
    rm -f "$tmp"
    echo "$(date -u +%FT%TZ) FAILED  $name (exit $?)" >> "$LOG"
    exit 1
  fi
done < "$JOBS"

echo "$(date -u +%FT%TZ) batch complete" >> "$LOG"
