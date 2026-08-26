#!/bin/bash
# check-public-safe.sh — verify this checkout is safe to push to the PUBLIC repo.
#
# Run it before every public push (see docs/01-setup.md, "Before you push"):
#     ./check-public-safe.sh
#
# Exit 0 = safe to push.  Exit 1 = something sensitive would be published.
#
# It checks what git ACTUALLY tracks (not what's on disk), because that is
# exactly what a push sends to GitHub. .gitignore stops accidents; this catches
# the ones that slip past it (a force-added file, or a secret pasted into code
# or a doc). Belt and suspenders.
#
# Safe to run anywhere. It never changes files — it only looks and reports.

cd "$(dirname "$0")" || exit 1

# Make sure we're inside a git repository before doing anything.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository — run this from the project folder." ; exit 1
fi

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
fail=0

echo "Checking whether this checkout is safe to publish..."
echo ""

# ── 1. Paths that must never be tracked ────────────────────────────────────
# Environments, real data, and secrets. (The empty data/ folders keep only a
# .gitkeep placeholder, which is allowed — everything else under data/ is not.)
echo "1. Secret / environment / data paths"
step1=0
for p in .venv renv/library .streamlit/secrets.toml .env .env.local .Renviron ; do
  tracked=$(git ls-files -- "$p" 2>/dev/null)
  if [ -n "$tracked" ]; then
    echo -e "   ${RED}✗ TRACKED: $p${NC}"
    echo "$tracked" | sed 's/^/     /'
    fail=1 ; step1=1
  fi
done
# Anything tracked under data/ other than the .gitkeep placeholders is a leak
# of (potentially large or private) data — our rule is data is regenerated,
# never committed.
data_tracked=$(git ls-files -- data 2>/dev/null | grep -v '/\.gitkeep$')
if [ -n "$data_tracked" ]; then
  echo -e "   ${RED}✗ data files tracked (data/ is regenerated, never committed):${NC}"
  echo "$data_tracked" | sed 's/^/     /'
  fail=1 ; step1=1
fi
[ $step1 -eq 0 ] && echo -e "   ${GREEN}✓ none tracked${NC}"

# ── 2. Sensitive file extensions anywhere ──────────────────────────────────
# Catches a secret/data file force-added (git add -f) at ANY path. We do NOT
# flag .csv or .pkl — those are our intended, small artifacts in artifacts/.
echo ""
echo "2. Sensitive file extensions"
ext=$(git ls-files | grep -iE '\.(key|pem|crt|cer|csr|p12|pfx|jks|der|db|sqlite3?|duckdb|dump|bak)$')
if [ -n "$ext" ]; then
  echo -e "   ${RED}✗ sensitive file extension(s) tracked:${NC}"
  echo "$ext" | sed 's/^/     /'
  fail=1
else
  echo -e "   ${GREEN}✓ none tracked${NC}"
fi

# ── 3. Credential-shaped strings in tracked content ────────────────────────
# Real API keys and private keys have recognisable formats. We match the
# FORMATS (not the word "api_key"), so ordinary docs that merely mention keys
# don't trip the alarm. The script excludes itself from the scan.
echo ""
echo "3. Credential-shaped strings in tracked content"
creds=$(git grep -inE \
  'sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----' \
  -- ':!check-public-safe.sh' 2>/dev/null)
if [ -n "$creds" ]; then
  echo -e "   ${RED}✗ found something that looks like a real credential — redact before pushing:${NC}"
  echo "$creds" | cut -c1-120 | sed 's/^/     /'
  fail=1
else
  echo -e "   ${GREEN}✓ none found${NC}"
fi

# ── 4. Hard-coded local machine paths ──────────────────────────────────────
# A path like /Users/<name>/ or /home/<name>/ or C:\Users\ leaks your machine
# AND breaks reproducibility for anyone who clones the repo. Use ~ or relative
# paths instead. The script excludes itself.
echo ""
echo "4. Hard-coded local machine paths"
paths=$(git grep -inE '/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|[A-Za-z]:\\\\Users\\\\' \
  -- ':!check-public-safe.sh' 2>/dev/null)
if [ -n "$paths" ]; then
  echo -e "   ${RED}✗ hard-coded local path(s) — replace with ~ or a relative path:${NC}"
  echo "$paths" | cut -c1-120 | sed 's/^/     /'
  fail=1
else
  echo -e "   ${GREEN}✓ none found${NC}"
fi

# ── 5. Large tracked files (informational) ─────────────────────────────────
# Data and models are meant to be small or regenerated. A big tracked file is
# usually a mistake. Warning only — review, don't necessarily block.
echo ""
echo "5. Large tracked files (informational)"
big=$(git ls-files | while read -r f; do
        [ -f "$f" ] || continue
        sz=$(wc -c <"$f" 2>/dev/null)
        if [ "${sz:-0}" -gt 5242880 ]; then       # > 5 MB
          awk -v s="$sz" -v f="$f" 'BEGIN{printf "     %6.1f MB  %s\n", s/1048576, f}'
        fi
      done)
if [ -n "$big" ]; then
  echo -e "   ${YELLOW}– files over 5 MB are tracked — is that intended?${NC}"
  echo "$big"
else
  echo -e "   ${GREEN}✓ nothing oversized${NC}"
fi

# ── 6. Personal attribution (informational) ────────────────────────────────
# Your name / email / GitHub handle in README and LICENSE is DELIBERATE public
# attribution, not a leak. This just lists where it appears so you can confirm
# it's intended and nothing new crept in. Edit the pattern to your own details.
echo ""
echo "6. Personal attribution (informational — accepted where intended)"
attr=$(git grep -inE 'akannan2987|abhilash' -- ':!check-public-safe.sh' 2>/dev/null | cut -c1-100)
if [ -n "$attr" ]; then
  echo "$attr" | sed 's/^/     /'
  echo -e "   ${YELLOW}– confirm these are intended attribution (README/LICENSE), not new leaks${NC}"
else
  echo -e "   ${GREEN}✓ none${NC}"
fi

echo ""
if [ $fail -eq 0 ]; then
  echo -e "${GREEN}✓ SAFE TO PUSH to the public repository${NC}"
  exit 0
fi
echo -e "${RED}✗ NOT SAFE TO PUSH — fix the items marked ✗ above${NC}"
exit 1
