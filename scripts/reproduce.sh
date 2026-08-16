#!/usr/bin/env bash
# scripts/reproduce.sh
#
# T22 — Offline reproduction of the published T17-T19 RAG-latency reports.
#
# Per RAG_PIPELINE_PLAN.md §10 and README.md, this is the final reproducibility
# command. It does NOT start Ollama, does NOT re-run the benchmark, and does NOT
# touch sealed holdouts. Instead it:
#   1. verifies the frozen pins and Ollama/model/runtime identity (offline
#      manifest checks only),
#   2. verifies the frozen text-RAG evaluation fixtures and the content-
#      addressed dataset cache,
#   3. regenerates EVERY reported metric and chart from the immutable C05
#      development raw traces (the published report set), and
#   4. self-verifies that the regenerated reports are bit-for-bit identical to
#      the committed published reports (sha256-per-file).
#
# Every subordinate command and its output is appended to a timestamped run log
# under artifacts/repro-logs/, which is the saved log required by T22.
#
# Usage:  bash scripts/reproduce.sh
# Env:    PYTHON, REPRO_RUN_DIR, REPRO_REPORTS_DIR
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-.venv/bin/python}"
# Immutable C05 authoritative development run (360 attempts) and the report set
# it published. Defaults match the committed evidence.
RUN_DIR="${REPRO_RUN_DIR:-artifacts/authoritative-runs/20260816T112509Z-1df7268307b1}"
REPORTS_DIR="${REPRO_REPORTS_DIR:-artifacts/reports/20260816T112509Z-1df7268307b1}"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="artifacts/repro-logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/reproduce.$TIMESTAMP.log"

say()     { printf '%s\n' "$*" | tee -a "$LOG"; }
section() { printf '\n=== %s ===\n' "$*" | tee -a "$LOG"; }
run()     { say "+ $*"; "$@" 2>&1 | tee -a "$LOG"; }

{
  say "scripts/reproduce.sh — offline reproduction of published T17-T19 reports"
  say "started (UTC): $TIMESTAMP"
  say "repo_root: $REPO_ROOT"
  say "python: $($PYTHON --version 2>&1)"
  say "platform: $(uname -s) $(uname -m) ($(uname -r))"
  say "run_dir (immutable C05 raw traces): $RUN_DIR"
  say "published_reports (reproduction target): $REPORTS_DIR"
  say "log: $LOG"
  say "NOTE: offline — Ollama is not started or contacted; reports are regenerated"
  say "      from saved raw traces only."
} | tee -a "$LOG"

# --- 1. Verify frozen pins and Ollama/model/runtime identity (offline). ---
section "1/4  environment + model/runtime identity (offline manifest check)"
run "$PYTHON" scripts/verify_environment.py

# --- 2. Verify evaluation fixtures + content-addressed dataset cache. ---
section "2/4  evaluation fixtures, dataset cache, and frozen contract"
run "$PYTHON" scripts/verify_eval.py

# --- 3. Regenerate all reported metrics and charts from saved raw traces. ---
section "3/4  regenerate reported metrics and charts from saved raw traces"
REPRO_OUT="$(mktemp -d /tmp/reproduce-reports.XXXXXX)"
trap 'rm -rf "$REPRO_OUT"' EXIT
run "$PYTHON" -m scripts.reporting \
  --run-dir "$RUN_DIR" \
  --output-dir "$REPRO_OUT"

# --- 4. Self-verification: bit-for-bit parity with published reports. ---
section "4/4  self-verification: regenerated reports vs published reports (sha256)"
set +e
"$PYTHON" - "$REPRO_OUT" "$REPORTS_DIR" <<'PY' 2>&1 | tee -a "$LOG"
import hashlib, json, sys
from pathlib import Path

def sha256(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()

regen_dir = Path(sys.argv[1])
pub_dir = Path(sys.argv[2])

manifest = json.loads((pub_dir / "report-manifest.json").read_text())
pub_hashes: dict[str, str] = manifest.get("output_hashes", {})
regen_hashes = {
    p.relative_to(regen_dir).as_posix(): sha256(p)
    for p in regen_dir.rglob("*") if p.is_file() and p.name != "report-manifest.json"
}

missing   = sorted(set(pub_hashes) - set(regen_hashes))
extra     = sorted(set(regen_hashes) - set(pub_hashes))
mismatches = [n for n in sorted(set(pub_hashes) & set(regen_hashes))
              if pub_hashes.get(n) != regen_hashes.get(n)]

for label, items in (("missing report", missing),
                     ("extra report", extra),
                     ("hash mismatch", mismatches)):
    for name in items:
        print(f"  {label}: {name}")

for name in sorted(set(pub_hashes) | set(regen_hashes)):
    h = pub_hashes.get(name)
    g = regen_hashes.get(name)
    print(f"  [{'OK' if h == g and h is not None else 'FAIL'}] {name}")

ok = not missing and not extra and not mismatches
print(f"\nreports_reproduced: {len(regen_hashes)}")
print(f"reports_published:  {len(pub_hashes)}")
print(f"VERIFICATION: {'PASS — bit-for-bit reproduction of all published reports' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
PY
VERIFY_RC=$?
set -e

if [ "$VERIFY_RC" -ne 0 ]; then
  say "RESULT: FAIL — regenerated reports do not match the committed published reports"
  say "completed (UTC): $(date -u +%Y%m%dT%H%M%SZ)"
  say "log saved: $LOG"
  exit 1
fi

say "RESULT: PASS — all published reports reproduced bit-for-bit from saved raw traces"
say "generated_at (UTC): $TIMESTAMP"
say "completed (UTC): $(date -u +%Y%m%dT%H%M%SZ)"
say "log saved: $LOG"
