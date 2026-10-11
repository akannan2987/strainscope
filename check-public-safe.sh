#!/bin/bash
# check-public-safe.sh: verify this checkout is safe to push to the PUBLIC repo.
#
# Run it before every public push (see docs/01-setup.md, "Before you push"):
#     ./check-public-safe.sh
#
# Exit 0 = safe to push.  Exit 1 = something sensitive would be published.
#
# It checks exactly what your next commit could publish:
#   * every file Git already TRACKS, and
#   * every NEW file Git would add with `git add -A` (new and not ignored).
# Ignored files (.env, .venv/, data/ ...) are skipped: Git will never add them
# unless someone forces it with `git add -f` -- and a forced file is tracked,
# so it is checked. .gitignore stops accidents; this catches the ones that slip
# past it (a force-added file, or a secret pasted into code or a doc).
# Belt and suspenders.
#
# Why new files too (since v0.1.1): the gate runs BEFORE `git add -A`, so a
# brand-new file is not tracked yet. An earlier version looked only at tracked
# files and so never checked a new file on its first commit.
# See docs/01-setup.md, Part H.
#
# Safe to run anywhere. It never changes files; it only looks and reports.

cd "$(dirname "$0")" || exit 1

# Make sure we're inside a git repository before doing anything.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository. Run this from the project folder." ; exit 1
fi

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
fail=0

# The files a commit could publish: tracked (--cached) + new, not ignored
# (--others --exclude-standard).
candidates() { git ls-files --cached --others --exclude-standard "$@" 2>/dev/null; }
# Search the CONTENT of that same set. Two searches, merged, because neither
# covers it alone: plain `git grep` reads every tracked file (even a tracked
# file that .gitignore lists, e.g. one force-added with `git add -f`), and
# `git grep --untracked` adds the new files -- but skips anything .gitignore
# lists, even when it is tracked. Together they cover exactly what a commit
# could publish.
gitscan() { { git grep "$@"; git grep --untracked "$@"; } 2>/dev/null | sort -u; }
n_tracked=$(git ls-files | wc -l | tr -d ' ')
n_new=$(git ls-files --others --exclude-standard | wc -l | tr -d ' ')

echo "Checking whether this checkout is safe to publish..."
echo "Scanning ${n_tracked} tracked file(s) + ${n_new} new file(s) that 'git add -A' would add."
echo ""

# ── 1. Paths that must never be published ──────────────────────────────────
# Environments, real data, and secrets. (The empty data/ folders keep only a
# .gitkeep placeholder, which is allowed; everything else under data/ is not.)
echo "1. Secret / environment / data paths"
step1=0
for p in .venv renv/library .streamlit/secrets.toml .env .env.local .Renviron ; do
  tracked=$(candidates -- "$p")
  if [ -n "$tracked" ]; then
    echo -e "   ${RED}✗ WOULD BE PUBLISHED: $p${NC}"
    echo "$tracked" | sed 's/^/     /'
    fail=1 ; step1=1
  fi
done
# Anything tracked under data/ other than the .gitkeep placeholders is a leak
# of (potentially large or private) data. Our rule is that data is regenerated,
# never committed.
data_tracked=$(candidates -- data | grep -v '/\.gitkeep$')
if [ -n "$data_tracked" ]; then
  echo -e "   ${RED}✗ data files would be published (data/ is regenerated, never committed):${NC}"
  echo "$data_tracked" | sed 's/^/     /'
  fail=1 ; step1=1
fi
[ $step1 -eq 0 ] && echo -e "   ${GREEN}✓ none${NC}"

# ── 2. Sensitive file extensions anywhere ──────────────────────────────────
# Catches a secret/data file force-added (git add -f) at ANY path. We do NOT
# flag .csv or .pkl: those are our intended, small artifacts in artifacts/.
echo ""
echo "2. Sensitive file extensions"
ext=$(candidates | grep -iE '\.(key|pem|crt|cer|csr|p12|pfx|jks|der|db|sqlite3?|duckdb|dump|bak)$')
if [ -n "$ext" ]; then
  echo -e "   ${RED}✗ sensitive file extension(s) would be published:${NC}"
  echo "$ext" | sed 's/^/     /'
  fail=1
else
  echo -e "   ${GREEN}✓ none${NC}"
fi

# ── 3. Credential-shaped strings in tracked content ────────────────────────
# Real API keys and private keys have recognisable formats. We match the
# FORMATS (not the word "api_key"), so ordinary docs that merely mention keys
# don't trip the alarm. A key must START a token (the character before it may
# not be a letter, digit, "_" or "-"), so words that merely contain the letters
# (the link anchor "#ask-strainscope-…", "task-…", "risk-…") are not mistaken
# for an "sk-…" key. The script excludes itself from the scan.
echo ""
echo "3. Credential-shaped strings (tracked and new files)"
B='(^|[^A-Za-z0-9_-])'   # "start of a token"
creds=$(gitscan -inE \
  "${B}sk-[A-Za-z0-9_-]{20,}|${B}ghp_[A-Za-z0-9]{20,}|${B}gho_[A-Za-z0-9]{20,}|${B}github_pat_[A-Za-z0-9_]{20,}|${B}AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----" \
  -- ':!check-public-safe.sh' 2>/dev/null)
if [ -n "$creds" ]; then
  echo -e "   ${RED}✗ found something that looks like a real credential; redact it before pushing:${NC}"
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
paths=$(gitscan -inE '/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|[A-Za-z]:\\\\Users\\\\' \
  -- ':!check-public-safe.sh' 2>/dev/null)
if [ -n "$paths" ]; then
  echo -e "   ${RED}✗ hard-coded local path(s); replace with ~ or a relative path:${NC}"
  echo "$paths" | cut -c1-120 | sed 's/^/     /'
  fail=1
else
  echo -e "   ${GREEN}✓ none found${NC}"
fi

# ── 5. Large files (informational) ─────────────────────────────────────────
# Data and models are meant to be small or regenerated. A big tracked file is
# usually a mistake. Warning only: review, don't necessarily block.
echo ""
echo "5. Large files (informational)"
big=$(candidates | while read -r f; do
        [ -f "$f" ] || continue
        sz=$(wc -c <"$f" 2>/dev/null)
        if [ "${sz:-0}" -gt 5242880 ]; then       # > 5 MB
          awk -v s="$sz" -v f="$f" 'BEGIN{printf "     %6.1f MB  %s\n", s/1048576, f}'
        fi
      done)
if [ -n "$big" ]; then
  echo -e "   ${YELLOW}! files over 5 MB would be published. Is that intended?${NC}"
  echo "$big"
else
  echo -e "   ${GREEN}✓ nothing oversized${NC}"
fi

# ── 6. Personal attribution (informational) ────────────────────────────────
# Your name / email / GitHub handle in README and LICENSE is INTENDED public
# attribution, not a leak. This just lists where it appears so you can confirm
# it's intended and nothing new crept in. Edit the pattern to your own details.
echo ""
echo "6. Personal attribution (informational; accepted where intended)"
attr=$(gitscan -inE 'akannan2987|abhilash' -- ':!check-public-safe.sh' | cut -c1-100)
if [ -n "$attr" ]; then
  echo "$attr" | sed 's/^/     /'
  echo -e "   ${YELLOW}! confirm these are intended attribution (README/LICENSE), not new leaks${NC}"
else
  echo -e "   ${GREEN}✓ none${NC}"
fi

echo ""
if [ $fail -eq 0 ]; then
  echo -e "${GREEN}✓ SAFE TO PUSH to the public repository${NC}"
  exit 0
fi
echo -e "${RED}✗ NOT SAFE TO PUSH: fix the items marked ✗ above${NC}"
exit 1
