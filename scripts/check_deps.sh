#!/usr/bin/env bash
# Verify system dependencies before pip install (Linux)
set -euo pipefail

MISSING=""
check_pkg() {
    local name="$1" header="$2"
    if ! pkg-config --exists "$name" 2>/dev/null; then
        MISSING="$MISSING  - $name ($header)\n"
    fi
}

check_pkg "portaudio-2.0" "portaudio-devel / portaudio19-dev"

# Check Python version
PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$(python3 -c 'import sys; print(sys.version_info >= (3,10))')" != "True" ]]; then
    echo "ERROR: Python >= 3.10 required, found $PYVER"
    exit 1
fi

if [[ -n "$MISSING" ]]; then
    echo "ERROR: Missing system dependencies:"
    echo -e "$MISSING"
    echo ""
    echo "Install them first:"
    echo "  Fedora: sudo dnf install python3-devel gcc portaudio-devel"
    echo "  Debian/Ubuntu: sudo apt install python3-dev gcc portaudio19-dev"
    exit 1
fi

echo "All system dependencies satisfied."
