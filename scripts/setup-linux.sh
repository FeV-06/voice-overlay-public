#!/usr/bin/env bash
# Post-install setup for VoiceOverlay on Linux
# Run after: uv tool install "voice-overlay[linux]"
set -euo pipefail

if [[ "$EUID" -eq 0 ]]; then
    echo "Do not run this script as root. It will call sudo when needed."
    exit 1
fi

echo "=== VoiceOverlay Linux Setup ==="
echo ""

# --- Groups ---
NEED_LOGOUT=false

if ! groups | grep -q "\binput\b"; then
    echo "Adding user to 'input' group (/dev/input/event* access)..."
    sudo usermod -a -G input "$USER"
    NEED_LOGOUT=true
else
    echo "✓ Already in 'input' group"
fi

if ! groups | grep -q "\buinput\b"; then
    echo "Adding user to 'uinput' group (/dev/uinput access)..."
    sudo usermod -a -G uinput "$USER"
    NEED_LOGOUT=true
else
    echo "✓ Already in 'uinput' group"
fi

# --- udev rule for /dev/uinput ---
UDEV_RULE="/etc/udev/rules.d/99-voice-overlay-uinput.rules"
if [[ ! -f "$UDEV_RULE" ]]; then
    echo "Creating udev rule for /dev/uinput permissions..."
    echo 'KERNEL=="uinput", GROUP="uinput", MODE="0660"' | sudo tee "$UDEV_RULE" > /dev/null
    sudo udevadm control --reload-rules
    sudo udevadm trigger
else
    echo "✓ udev rule already exists"
fi

# --- Kernel module ---
if ! lsmod | grep -q "^uinput"; then
    echo "Loading uinput kernel module..."
    sudo modprobe uinput
fi

# --- evdev check ---
echo ""
echo "--- Checking Python dependencies ---"
if python3 -c "import evdev" 2>/dev/null; then
    echo "✓ evdev package found"
else
    echo "WARNING: evdev not found."
    echo "  Install it: uv tool install --force --reinstall 'voice-overlay[linux]'"
fi

echo ""
echo "=== Setup complete ==="
if $NEED_LOGOUT; then
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  LOG OUT and log back in for group changes to apply.   ║"
    echo "║  After that, 'voice-overlay' will work without sudo.   ║"
    echo "╚══════════════════════════════════════════════════════════╝"
else
    echo "All permissions already configured. Ready to run."
fi
