#!/usr/bin/env bash
# Verify documentation invariants: index consistency and operator-doc freshness.
#
# Turns the norms in docs/agent/documentation-policy.md §1 and §3 into
# a mechanical check so they cannot quietly rot. Intended to be fast,
# dependency-free, and small enough to read end-to-end.
#
# Portability:
#   - bash 3.2+ (macOS default included)
#   - `find`, `grep -E`, `sed -E`, `sort`, `comm`, `awk`, `date`,
#     `basename`, `xargs` — standard tools. The freshness check
#     accepts both GNU `date -d` and BSD `date -j -f` syntaxes
#     transparently, so the script works on Linux and macOS alike.
#   - The freshness thresholds use a 30-day-per-month approximation
#     (see the inline comment); calendar drift over a year is a few
#     days, well below the policy's resolution.
#
# Exit codes:
#   0  all checks passed (warnings allowed)
#   1  one or more checks failed
#
# Usage: bash scripts/check-docs.sh

set -euo pipefail

# Resolve the repository root as the directory containing this script's
# parent. This lets the script be invoked from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Emit ANSI colour only when stderr is a TTY. CI logs stay plain.
if [ -t 2 ]; then
    C_RED=$'\033[31m'; C_YEL=$'\033[33m'; C_GRN=$'\033[32m'; C_RST=$'\033[0m'
else
    C_RED=''; C_YEL=''; C_GRN=''; C_RST=''
fi

fail=0
warn=0

log_err() { printf '  %sERROR%s %s\n' "$C_RED" "$C_RST" "$*" >&2; fail=$((fail + 1)); }
log_warn() { printf '  %sWARN%s  %s\n' "$C_YEL" "$C_RST" "$*" >&2; warn=$((warn + 1)); }
log_ok() { printf '  %sOK%s    %s\n' "$C_GRN" "$C_RST" "$*"; }

# ---------------------------------------------------------------------------
# Check 1: index.md consistency.
#
# For every subdirectory of docs/ that contains an index.md, the set of
# .md files listed in the index must equal the set of .md files
# actually present (excluding index.md itself).
#
# The listing format is flexible: we extract any markdown link of the
# form [...](foo.md) or [...](./foo.md), tolerating an optional link
# title ([...](foo.md "title")). Links that include a slash are
# assumed to point into a subdirectory and ignored here — subdirectories
# get their own index.md.
# ---------------------------------------------------------------------------
echo "Checking docs/*/index.md consistency..."

if [ ! -d docs ]; then
    log_warn "docs/ does not exist yet; skipping index checks"
else
    # Walk every directory under docs/ that has an index.md, not
    # just the top level. This catches sub-divided audiences like
    # docs/upstream/{prd,design,adr}/, each of which carries its own
    # index. `find` produces paths like "docs/upstream/adr/index.md";
    # we derive the directory from it.
    while IFS= read -r -d '' index; do
        dir="${index%/index.md}"

        # Actual files: .md files directly under $dir, excluding
        # index.md. We read `find -print0` into a bash array and
        # take basenames ourselves, which avoids two xargs
        # portability pitfalls:
        #   (1) GNU xargs's `-r` / `--no-run-if-empty` is a GNU
        #       extension; without it, xargs on empty input exits
        #       123 and `set -euo pipefail` kills the script. macOS
        #       xargs skips empty input silently but does not
        #       understand `-r`, so there is no portable flag that
        #       works on both.
        #   (2) `find -printf '%f\n'` is GNU-only.
        # The pure-bash loop below is portable across the Dev
        # Container image, bash-on-macOS (3.2+), and CI runners.
        actual_files=()
        while IFS= read -r -d '' f; do
            actual_files+=("${f##*/}")
        done < <(find "$dir" -maxdepth 1 -name '*.md' ! -name 'index.md' -print0)
        if [ ${#actual_files[@]} -gt 0 ]; then
            actual=$(printf '%s\n' "${actual_files[@]}" | sort)
        else
            actual=""
        fi

        # Listed files: extract the href of any markdown link to a
        # .md file, drop an optional leading "./", drop a trailing
        # " \"title\"" if present, then keep only same-directory
        # references (no slashes). `|| true` protects against
        # `set -e` when grep finds no matches, which is legitimate
        # for an empty index.
        #
        # Before extracting links we strip HTML comments
        # (`<!-- ... -->`) so that example rows written as inline
        # documentation inside an otherwise-empty index do not get
        # parsed as real references. The awk pass below removes
        # comments even when multiple pairs appear on a single line,
        # without the greedy-match pitfall of a naive
        # `sed 's/<!--.*-->//'` (which would merge two adjacent
        # comments and consume the non-comment text between them).
        # Multi-line comments are handled by joining the whole file
        # into one "record" (awk's RS='\0').
        #
        # Scope: this parser currently recognises only inline
        # markdown links of the form `[text](path.md)` or
        # `[text](path.md "title")`. Reference-style links
        # (`[text][ref]` with `[ref]: path.md` at the bottom) and
        # HTML `<a href="...">` are not detected. If you use those
        # forms in an index, extend this regex. For typical index
        # files written by hand or by Prettier, inline links are
        # the norm.
        listed=$(awk 'BEGIN{RS="\0"} {
                while (match($0, /<!--/)) {
                    start = RSTART
                    rest = substr($0, start + 4)
                    if (match(rest, /-->/) == 0) break
                    end = start + 4 + RSTART + 2
                    $0 = substr($0, 1, start - 1) substr($0, end)
                }
                print
            }' "$index" 2>/dev/null \
            | grep -oE '\]\([^)]+\.md([[:space:]]+"[^"]*")?\)' \
            | sed -E 's/^\]\(//; s/\)$//; s/[[:space:]]+"[^"]*"$//; s|^\./||' \
            | grep -v '/' \
            | sort -u || true)

        # Use printf rather than echo to avoid an extra blank line
        # when either side is empty, which would confuse comm.
        missing=$(comm -23 <(printf '%s\n' "$actual") <(printf '%s\n' "$listed"))
        orphaned=$(comm -13 <(printf '%s\n' "$actual") <(printf '%s\n' "$listed"))

        if [ -n "$missing" ]; then
            while IFS= read -r f; do
                [ -z "$f" ] && continue
                log_err "$dir/$f exists but is not listed in $index"
            done <<< "$missing"
        fi

        if [ -n "$orphaned" ]; then
            while IFS= read -r f; do
                [ -z "$f" ] && continue
                log_err "$index references $f, which does not exist"
            done <<< "$orphaned"
        fi

        if [ -z "$missing" ] && [ -z "$orphaned" ]; then
            log_ok "$index is consistent"
        fi
    done < <(find docs -name 'index.md' -print0 | sort -z)
fi

# ---------------------------------------------------------------------------
# Check 2: operator-doc freshness.
#
# Every .md file under docs/operator/ (except index.md) must carry a
# footer of the form
#   Last reviewed: YYYY-MM-DD
# within the last 10 lines of the file.
#
# Thresholds:
#   0–6 months:   OK
#   6–12 months:  warning
#   > 12 months:  error
# Missing or malformed date: error.
# ---------------------------------------------------------------------------
echo
echo "Checking docs/operator/ freshness..."

if [ ! -d docs/operator ]; then
    log_warn "docs/operator/ does not exist yet; skipping freshness checks"
else
    today_epoch=$(date +%s)
    # Thresholds are expressed as "approximately N months" using a
    # flat 30-day month. This is close enough for the policy ("6
    # months" / "12 months" in documentation-policy.md §3) — the
    # drift from calendar months is at most a few days over a year,
    # well inside the resolution anyone cares about for runbook
    # freshness. If you need calendar-accurate behaviour, replace
    # with `date -d "$date_str + 6 months"` and compare epochs.
    warn_seconds=$(( 60 * 60 * 24 * 30 * 6 ))
    err_seconds=$(( 60 * 60 * 24 * 30 * 12 ))

    found_any=0
    while IFS= read -r -d '' f; do
        [ "$(basename "$f")" = "index.md" ] && continue
        found_any=1

        date_str=$(tail -n 10 "$f" \
            | grep -iEo 'last[[:space:]]*reviewed[[:space:]]*:[[:space:]]*[0-9]{4}-[0-9]{2}-[0-9]{2}' \
            | tail -n 1 \
            | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' || true)

        if [ -z "$date_str" ]; then
            log_err "$f has no 'Last reviewed: YYYY-MM-DD' footer"
            continue
        fi

        # Parse YYYY-MM-DD into epoch seconds. GNU date and BSD/macOS
        # date have mutually incompatible syntaxes for this, so we
        # try GNU first and fall back to BSD. Both are silent on
        # success; malformed input fails both and hits the error
        # branch below.
        if doc_epoch=$(date -d "$date_str" +%s 2>/dev/null); then
            :
        elif doc_epoch=$(date -j -f '%Y-%m-%d' "$date_str" +%s 2>/dev/null); then
            :
        else
            log_err "$f has a malformed Last reviewed date: $date_str"
            continue
        fi

        age=$(( today_epoch - doc_epoch ))
        if [ "$age" -gt "$err_seconds" ]; then
            log_err "$f was last reviewed $date_str (>12 months ago)"
        elif [ "$age" -gt "$warn_seconds" ]; then
            log_warn "$f was last reviewed $date_str (>6 months ago)"
        else
            log_ok "$f reviewed $date_str"
        fi
    done < <(find docs/operator -name '*.md' -print0)

    if [ "$found_any" = 0 ]; then
        log_ok "no operator docs to check yet"
    fi
fi

# ---------------------------------------------------------------------------
# Summary.
# ---------------------------------------------------------------------------
echo
if [ "$fail" -gt 0 ]; then
    printf '%s%d error(s)%s, %d warning(s)\n' "$C_RED" "$fail" "$C_RST" "$warn" >&2
    exit 1
elif [ "$warn" -gt 0 ]; then
    printf '%s%d warning(s)%s, no errors\n' "$C_YEL" "$warn" "$C_RST"
    exit 0
else
    printf '%sAll documentation checks passed.%s\n' "$C_GRN" "$C_RST"
    exit 0
fi
