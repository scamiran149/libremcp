# LibreMCP - Install missing Python dependencies for LibreOffice
# Downloads pysqlite3 wheel from PyPI (LO's Python on Windows lacks sqlite3)

param(
    [string]$LibDir = ""
)

$ErrorActionPreference = "Stop"

Write-Host "=== LibreMCP - Install Dependencies ===" -ForegroundColor Cyan
Write-Host ""

# --- Resolve target lib directory ---
if (-not $LibDir) {
    Write-Host "ERROR: -LibDir parameter is required." -ForegroundColor Red
    exit 1
}

$pysqlite3Dir = Join-Path $LibDir "pysqlite3"

if (Test-Path (Join-Path $pysqlite3Dir "__init__.py")) {
    Write-Host "[OK] pysqlite3 already installed at $pysqlite3Dir" -ForegroundColor Green
    Write-Host ""
    Write-Host "Done. Press Enter to close."
    Read-Host
    exit 0
}

# --- Detect Python version from LO ---
# Default to 3.12 (LO 24.x ships 3.12)
$pyVersion = "312"
Write-Host "Target: pysqlite3 for CPython $pyVersion win_amd64"
Write-Host ""

# --- Fetch wheel URL from PyPI ---
Write-Host "Fetching pysqlite3 info from PyPI..." -ForegroundColor Yellow
$pypiUrl = "https://pypi.org/pypi/pysqlite3/json"

try {
    $json = Invoke-RestMethod -Uri $pypiUrl -TimeoutSec 30
} catch {
    Write-Host "ERROR: Failed to reach PyPI: $_" -ForegroundColor Red
    Write-Host "Check your internet connection."
    Read-Host
    exit 1
}

$wheelUrl = $null
$tag = "cp$pyVersion"

# Search in latest release first
foreach ($file in $json.urls) {
    if ($file.filename -match $tag -and $file.filename -match "win_amd64" -and $file.filename -match "\.whl$") {
        $wheelUrl = $file.url
        break
    }
}

# Search all releases if not found
if (-not $wheelUrl) {
    foreach ($ver in $json.releases.PSObject.Properties) {
        foreach ($file in $ver.Value) {
            if ($file.filename -match $tag -and $file.filename -match "win_amd64" -and $file.filename -match "\.whl$") {
                $wheelUrl = $file.url
                break
            }
        }
        if ($wheelUrl) { break }
    }
}

if (-not $wheelUrl) {
    Write-Host "ERROR: No pysqlite3 wheel found for $tag win_amd64" -ForegroundColor Red
    Read-Host
    exit 1
}

Write-Host "Downloading: $wheelUrl"
$tempWhl = Join-Path $env:TEMP "pysqlite3.whl"

try {
    Invoke-WebRequest -Uri $wheelUrl -OutFile $tempWhl -TimeoutSec 60
} catch {
    Write-Host "ERROR: Download failed: $_" -ForegroundColor Red
    Read-Host
    exit 1
}

$size = [math]::Round((Get-Item $tempWhl).Length / 1024)
Write-Host "Downloaded ${size} KB" -ForegroundColor Green

# --- Extract pysqlite3/ from wheel (it's a zip) ---
Write-Host "Extracting to $LibDir ..."

# Clean up any partial previous install
if (Test-Path $pysqlite3Dir) {
    Remove-Item -Recurse -Force $pysqlite3Dir
}

try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($tempWhl)

    foreach ($entry in $zip.Entries) {
        if ($entry.FullName.StartsWith("pysqlite3/")) {
            $destPath = Join-Path $LibDir $entry.FullName
            $destDir = Split-Path $destPath -Parent
            if (-not (Test-Path $destDir)) {
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            }
            if (-not $entry.FullName.EndsWith("/")) {
                [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destPath, $true)
            }
        }
    }
    $zip.Dispose()
} catch {
    Write-Host "ERROR: Extraction failed: $_" -ForegroundColor Red
    Read-Host
    exit 1
}

Remove-Item -Force $tempWhl -ErrorAction SilentlyContinue

# --- Verify ---
if (Test-Path (Join-Path $pysqlite3Dir "__init__.py")) {
    Write-Host ""
    Write-Host "[OK] pysqlite3 installed successfully!" -ForegroundColor Green
    Write-Host "Please restart LibreOffice for changes to take effect."
} else {
    Write-Host ""
    Write-Host "ERROR: Installation verification failed." -ForegroundColor Red
}

Write-Host ""
Write-Host "Press Enter to close."
Read-Host
