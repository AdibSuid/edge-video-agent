# PowerShell script to download and setup MediaMTX for Windows
# Run this script to automatically download and configure MediaMTX

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MediaMTX RTSP Server Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$MEDIAMTX_VERSION = "v1.5.1"
$MEDIAMTX_URL = "https://github.com/bluenviron/mediamtx/releases/download/$MEDIAMTX_VERSION/mediamtx_${MEDIAMTX_VERSION}_windows_amd64.zip"
$DOWNLOAD_PATH = "mediamtx.zip"
$EXTRACT_PATH = "."

# Step 1: Download MediaMTX
Write-Host "[1/4] Downloading MediaMTX $MEDIAMTX_VERSION..." -ForegroundColor Yellow

if (Test-Path "mediamtx.exe") {
    Write-Host "  MediaMTX already exists. Skipping download." -ForegroundColor Green
} else {
    try {
        Invoke-WebRequest -Uri $MEDIAMTX_URL -OutFile $DOWNLOAD_PATH -UseBasicParsing
        Write-Host "  Download complete!" -ForegroundColor Green
    } catch {
        Write-Host "  Failed to download MediaMTX: $_" -ForegroundColor Red
        exit 1
    }

    # Step 2: Extract
    Write-Host "[2/4] Extracting MediaMTX..." -ForegroundColor Yellow
    try {
        Expand-Archive -Path $DOWNLOAD_PATH -DestinationPath $EXTRACT_PATH -Force
        Remove-Item $DOWNLOAD_PATH
        Write-Host "  Extraction complete!" -ForegroundColor Green
    } catch {
        Write-Host "  Failed to extract: $_" -ForegroundColor Red
        exit 1
    }
}

# Step 3: Configure Firewall
Write-Host "[3/4] Configuring Windows Firewall..." -ForegroundColor Yellow
try {
    # Check if rule exists
    $existingRule = Get-NetFirewallRule -DisplayName "RTSP Relay (MediaMTX)" -ErrorAction SilentlyContinue

    if ($existingRule) {
        Write-Host "  Firewall rule already exists." -ForegroundColor Green
    } else {
        New-NetFirewallRule -DisplayName "RTSP Relay (MediaMTX)" `
                            -Direction Inbound `
                            -Protocol TCP `
                            -LocalPort 8554 `
                            -Action Allow `
                            -Profile Any | Out-Null
        Write-Host "  Firewall rule created for port 8554!" -ForegroundColor Green
    }
} catch {
    Write-Host "  Warning: Could not configure firewall (may need admin rights)" -ForegroundColor Yellow
    Write-Host "  Please manually allow port 8554 in Windows Firewall" -ForegroundColor Yellow
}

# Step 4: Get Public IP
Write-Host "[4/4] Detecting public IP address..." -ForegroundColor Yellow
try {
    $publicIP = (Invoke-WebRequest -Uri "https://ifconfig.me/ip" -UseBasicParsing).Content.Trim()
    Write-Host "  Your public IP: $publicIP" -ForegroundColor Green
    Write-Host ""
    Write-Host "IMPORTANT: Update config.yaml with this IP:" -ForegroundColor Yellow
    Write-Host "  edge_public_ip: '$publicIP'" -ForegroundColor Cyan
} catch {
    Write-Host "  Could not detect public IP automatically" -ForegroundColor Yellow
    Write-Host "  Please find your IP at: https://whatismyipaddress.com/" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Update config.yaml with your public IP or domain" -ForegroundColor White
Write-Host "2. If behind router, configure port forwarding (8554 → this device)" -ForegroundColor White
Write-Host "3. Start MediaMTX: .\mediamtx.exe .\mediamtx_config.yml" -ForegroundColor White
Write-Host "4. Start Edge Agent: python app.py" -ForegroundColor White
Write-Host ""
Write-Host "For detailed instructions, see RTSP_RELAY_SETUP.md" -ForegroundColor Yellow
Write-Host ""
