# Verify system dependencies before pip install (Windows)
Write-Host "VoiceOverlay Dependency Check (Windows)" -ForegroundColor Cyan

# Check Python version
try {
    $pyVer = [System.Version](python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if ($pyVer -lt [System.Version]"3.10") {
        Write-Host "ERROR: Python >= 3.10 required, found $pyVer" -ForegroundColor Red
        exit 1
    }
    Write-Host "Python $pyVer OK" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found. Install Python >= 3.10 from https://python.org" -ForegroundColor Red
    exit 1
}

# Check pip
try {
    $pipVer = pip --version
    Write-Host "pip available: $pipVer" -ForegroundColor Green
} catch {
    Write-Host "WARNING: pip not found. Ensure it is installed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Notes:" -ForegroundColor Cyan
Write-Host "  - PortAudio is bundled with the sounddevice package on Windows (no separate install needed)." -ForegroundColor White
Write-Host "  - If using faster-whisper, you may need the Microsoft Visual C++ Redistributable:" -ForegroundColor White
Write-Host "    https://aka.ms/vs/17/release/vc_redist.x64.exe" -ForegroundColor White
Write-Host ""
Write-Host "All system dependencies satisfied." -ForegroundColor Green
