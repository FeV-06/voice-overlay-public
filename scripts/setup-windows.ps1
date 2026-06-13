# VoiceOverlay Windows Setup
# Run after: uv tool install "voice-overlay[windows]"
# Open a fresh PowerShell as a normal user (no admin needed for most steps).

Write-Host "=== VoiceOverlay Windows Setup ===" -ForegroundColor Cyan
Write-Host ""

# --- Python version ---
$pyVer = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found. Install Python 3.10+ from python.org" -ForegroundColor Red
    exit 1
}
Write-Host "✓ $pyVer"

# --- VC++ Redistributable check ---
$vcRedist = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" -ErrorAction SilentlyContinue
if (-not $vcRedist) {
    Write-Host ""
    Write-Host "WARNING: Microsoft Visual C++ Redistributable not detected." -ForegroundColor Yellow
    Write-Host "  Required by faster-whisper (CTranslate2 native DLLs)."
    Write-Host "  Download: https://aka.ms/vs/17/release/vc_redist.x64.exe" -ForegroundColor Yellow
    Write-Host ""
}
else {
    Write-Host "✓ Visual C++ Redistributable found (version $($vcRedist.Bld))"
}

# --- uv check ---
$uvCheck = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCheck) {
    Write-Host "ERROR: uv not found. Install it: https://docs.astral.sh/uv/" -ForegroundColor Red
    exit 1
}
Write-Host "✓ uv found"

# --- voice-overlay install ---
$installed = uv tool list 2>&1 | Select-String "voice-overlay"
if (-not $installed) {
    Write-Host "Installing voice-overlay[windows]..."
    uv tool install "voice-overlay[windows]"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: uv tool install failed" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "✓ voice-overlay already installed"
}

# --- Microphone check ---
Write-Host ""
Write-Host "--- Audio Devices ---"
try {
    $devices = python -c "import sounddevice; print('\n'.join(f'{d[\"index\"]}: {d[\"name\"]}' for d in sounddevice.query_devices() if d['max_input_channels'] > 0))" 2>&1
    if ($devices) {
        Write-Host "Input devices found:"
        $devices
    }
    else {
        Write-Host "No input devices found. Connect a microphone." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Could not query audio devices." -ForegroundColor Yellow
}

# --- Autostart directory ---
$configDir = "$env:APPDATA\voice-overlay"
if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
}
Write-Host "✓ Config directory: $configDir"

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Run: voice-overlay"
Write-Host ""
Write-Host "If you see DLL load errors, install the VC++ Redistributable:"
Write-Host "  https://aka.ms/vs/17/release/vc_redist.x64.exe"
