#!/usr/bin/env bash
# ============================================================================
# Clean Test Suite Runner — DeFiPy ecosystem
# ============================================================================
# Creates a fresh Python venv and runs pytest against each package in the
# dependency order: uniswappy → balancerpy → stableswappy → web3scout.
# Optionally runs defipy's own integration tests as a 5th stage.
#
# This script is the release gate: if it passes, the ecosystem is in a
# known-good state. If it fails, the first red package is where to fix.
#
# Exits 0 on full pass, 1 on test failure, 2 on setup failure.
# ============================================================================

set -u

# Require bash 4+ for reliable associative-array handling (macOS ships 3.2).
if (( BASH_VERSINFO[0] < 4 )); then
    echo "ERROR: this script requires bash 4 or newer." >&2
    echo "On macOS: brew install bash" >&2
    exit 2
fi

# ---- Paths -----------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFIPY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPOS_ROOT="$(cd "$DEFIPY_ROOT/.." && pwd)"
VENV_DIR="$DEFIPY_ROOT/.venv_ci"

# ---- Flags -----------------------------------------------------------------
KEEP_VENV=false
CONTINUE_ON_FAIL=false
INCLUDE_DEFIPY=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Create a fresh venv, install the DeFiPy ecosystem packages in editable mode,
and run each package's test suite in dependency order.

OPTIONS:
  --keep          Reuse existing .venv_ci (skip rebuild) for faster iteration
  --continue      Run all test suites even if one fails
  --with-defipy   Also run defipy's own tests as a 5th stage
  --help, -h      Print this usage and exit

EXIT CODES:
  0  All suites passed
  1  One or more suites had test failures
  2  Setup failure (venv creation, install, missing repo)
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --keep)         KEEP_VENV=true ;;
        --continue)     CONTINUE_ON_FAIL=true ;;
        --with-defipy)  INCLUDE_DEFIPY=true ;;
        --help|-h)      usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
    esac
    shift
done

# ---- Package list ----------------------------------------------------------
PACKAGES=(uniswappy balancerpy stableswappy web3scout)
if [ "$INCLUDE_DEFIPY" = true ]; then
    PACKAGES+=(defipy)
fi

# Editable-install order mirrors test order (upstream deps first).
INSTALL_ORDER=("${PACKAGES[@]}")

# ---- Output helpers --------------------------------------------------------
if [ -t 1 ]; then
    C_RESET=$'\033[0m';  C_BOLD=$'\033[1m'
    C_GREEN=$'\033[32m'; C_RED=$'\033[31m'
    C_YELLOW=$'\033[33m'; C_BLUE=$'\033[34m'
else
    C_RESET=""; C_BOLD=""
    C_GREEN=""; C_RED=""; C_YELLOW=""; C_BLUE=""
fi

SEP="=============================================================================="

banner() {
    echo
    printf "%s%s%s\n" "$C_BOLD$C_BLUE" "$SEP" "$C_RESET"
    printf "%s  %s%s\n" "$C_BOLD$C_BLUE" "$1" "$C_RESET"
    printf "%s%s%s\n" "$C_BOLD$C_BLUE" "$SEP" "$C_RESET"
    echo
}

# ---- Pre-flight ------------------------------------------------------------
for pkg in "${PACKAGES[@]}"; do
    if [ ! -d "$REPOS_ROOT/$pkg" ]; then
        printf "%sERROR%s: repo not found at %s\n" "$C_RED" "$C_RESET" "$REPOS_ROOT/$pkg" >&2
        exit 2
    fi
done

# ---- Venv setup ------------------------------------------------------------
banner "Venv Setup"

if [ "$KEEP_VENV" = true ] && [ -d "$VENV_DIR" ]; then
    echo "Reusing venv at $VENV_DIR"
else
    if [ -d "$VENV_DIR" ]; then
        echo "Removing existing venv..."
        rm -rf "$VENV_DIR"
    fi
    echo "Creating fresh venv at $VENV_DIR..."
    python3 -m venv "$VENV_DIR" || { echo "venv creation failed" >&2; exit 2; }
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Python: $(python --version)"
echo "Pip:    $(pip --version | awk '{print $1, $2}')"

# ---- Install packages ------------------------------------------------------
banner "Installing Packages (editable mode)"

pip install --quiet --upgrade pip || { echo "pip upgrade failed" >&2; exit 2; }
pip install --quiet pytest        || { echo "pytest install failed" >&2; exit 2; }

for pkg in "${INSTALL_ORDER[@]}"; do
    printf "Installing %-14s " "$pkg"
    if pip install --quiet -e "$REPOS_ROOT/$pkg"; then
        printf "%sok%s\n" "$C_GREEN" "$C_RESET"
    else
        printf "%sfailed%s\n" "$C_RED" "$C_RESET"
        exit 2
    fi
done

# ---- Run test suites -------------------------------------------------------
declare -A RESULTS
declare -A DURATIONS
FIRST_FAILURE=""

for pkg in "${PACKAGES[@]}"; do
    banner "Testing: $pkg"

    start=$(date +%s)
    set +e
    pytest -v "$REPOS_ROOT/$pkg"
    exit_code=$?
    set -e
    end=$(date +%s)

    DURATIONS[$pkg]=$((end - start))

    case $exit_code in
        0)
            RESULTS[$pkg]="passed"
            ;;
        1)
            RESULTS[$pkg]="failed"
            [ -z "$FIRST_FAILURE" ] && FIRST_FAILURE="$pkg"
            if [ "$CONTINUE_ON_FAIL" = false ]; then
                echo
                printf "%s%sStopping at first failure (%s). Use --continue to run all.%s\n" \
                    "$C_RED" "$C_BOLD" "$pkg" "$C_RESET" >&2
                break
            fi
            ;;
        5)
            RESULTS[$pkg]="notests"
            printf "%sWarning: no tests collected for %s%s\n" \
                "$C_YELLOW" "$pkg" "$C_RESET"
            ;;
        *)
            RESULTS[$pkg]="error($exit_code)"
            [ -z "$FIRST_FAILURE" ] && FIRST_FAILURE="$pkg"
            if [ "$CONTINUE_ON_FAIL" = false ]; then
                echo
                printf "%s%sStopping: pytest error in %s (exit %d).%s\n" \
                    "$C_RED" "$C_BOLD" "$pkg" "$exit_code" "$C_RESET" >&2
                break
            fi
            ;;
    esac
done

# ---- Summary ---------------------------------------------------------------
banner "Summary"

printf "%-18s %-14s %s\n" "PACKAGE" "RESULT" "DURATION"
printf '%.0s-' {1..48}; echo

for pkg in "${PACKAGES[@]}"; do
    status="${RESULTS[$pkg]:-skipped}"
    dur="${DURATIONS[$pkg]:--}"
    if [ "$dur" = "-" ]; then
        dur_display="-"
    else
        dur_display="${dur}s"
    fi

    case "$status" in
        passed)   color="$C_GREEN" ;;
        failed)   color="$C_RED";    status="FAILED" ;;
        notests)  color="$C_YELLOW"; status="no tests" ;;
        skipped)  color="$C_YELLOW" ;;
        *)        color="$C_RED" ;;
    esac
    printf "%-18s %s%-14s%s %s\n" "$pkg" "$color" "$status" "$C_RESET" "$dur_display"
done

echo
if [ -n "$FIRST_FAILURE" ]; then
    printf "%s%s✗ Release gate FAILED at: %s%s\n" "$C_RED" "$C_BOLD" "$FIRST_FAILURE" "$C_RESET"
    exit 1
else
    printf "%s%s✓ All test suites passed.%s\n" "$C_GREEN" "$C_BOLD" "$C_RESET"
    exit 0
fi
