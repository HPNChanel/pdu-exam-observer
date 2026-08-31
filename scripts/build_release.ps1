[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$WebProject = "apps/web",
    [string]$WebDist = "apps/web/dist",
    [string]$DemoDir = "demo",
    [string]$EntryScript = "src/pdu_exam_observer/__main__.py",
    [string]$ProductVersion = "0.2.0-m1",
    [string]$SourceRevision = "UNVERIFIED"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$webRoot = Join-Path $root $WebProject
$webDistPath = Join-Path $root $WebDist
$demoPath = Join-Path $root $DemoDir
$packagingRoot = Join-Path $root "packaging"
$staging = Join-Path $packagingRoot "release"
$workPath = Join-Path $packagingRoot "build"
$detached = Join-Path $packagingRoot "RELEASE_MANIFEST.json"
$metadataPath = Join-Path $packagingRoot "manifest-metadata.json"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm is required to build the frontend; install it or provide the integration build environment." }
if (-not (Test-Path -LiteralPath (Join-Path $webRoot "package-lock.json"))) { throw "Missing frontend package-lock.json under $webRoot; npm ci is intentionally fail-closed." }
if (-not (Test-Path -LiteralPath (Join-Path $demoPath "events.jsonl"))) { throw "Missing deterministic demo fixture: $demoPath\events.jsonl" }

Push-Location $webRoot
try {
    npm ci
    npm run build
} finally { Pop-Location }
if (-not (Test-Path -LiteralPath $webDistPath)) { throw "Frontend build did not produce $webDistPath" }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv is required for the pinned PyInstaller build: uv run --with pyinstaller==6.10.0" }

foreach ($target in @($staging, $workPath)) {
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}
New-Item -ItemType Directory -Path $staging -Force | Out-Null
$env:PDU_ENTRY_SCRIPT = $EntryScript
$env:PDU_WEB_DIST = $WebDist
$env:PDU_DEMO_DIR = $DemoDir
$env:PDU_RELEASE_DIR = $staging
uv run --with "pyinstaller==6.10.0" pyinstaller --noconfirm --clean --distpath $staging --workpath $workPath (Join-Path $packagingRoot "PDU-Exam-Observer.spec")

$bundle = Join-Path $staging "PDU-Exam-Observer"
if (-not (Test-Path -LiteralPath $bundle)) { throw "PyInstaller did not produce one-folder bundle: $bundle" }
Copy-Item -LiteralPath (Join-Path $packagingRoot "README.txt") -Destination (Join-Path $bundle "README.txt") -Force
Copy-Item -LiteralPath (Join-Path $root "THIRD_PARTY_NOTICES.txt") -Destination (Join-Path $bundle "THIRD_PARTY_NOTICES.txt") -Force

$forbidden = Get-ChildItem -LiteralPath $bundle -Recurse -Force -File | Where-Object {
    $relative = $_.FullName.Substring($bundle.Length + 1).Replace('\', '/')
    $relative -match '(^|/)(.git|_archive|data|runtime|exports|tests?|test-output|cache|coverage)(/|$)' -or
    $_.Name -match '(^|\.)((env|token|cookie|credential|identity|consent|pin|secret|key))' -or
    $_.Extension.ToLowerInvariant() -in @('.mp4','.db','.log','.partial','.pyc','.pem','.key')
}
if ($forbidden) { throw "Forbidden release payload detected: $($forbidden[0].FullName)" }

$hash = { param($path) (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
$pythonLock = Join-Path $root "uv.lock"
$frontendLock = Join-Path $webRoot "package-lock.json"
if (-not (Test-Path -LiteralPath $pythonLock)) { throw "Missing uv.lock; release manifest requires a Python lock hash." }
$metadata = [ordered]@{
    product_version = $ProductVersion
    schema_version = "release-manifest.v1"
    target_os = "Windows 11"
    target_architecture = "x64"
    build_time_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    source_revision = $SourceRevision
    python_lock_sha256 = & $hash $pythonLock
    frontend_lock_sha256 = & $hash $frontendLock
    known_limitations = @(
        "Unsigned trial package.",
        "M1 does not implement camera capture or real participant collection.",
        "Institutional approval, clean-machine portability, and physical two-monitor behavior are UNVERIFIED."
    )
    test_receipts = @()
}
$metadata | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $metadataPath -Encoding utf8
uv run --with "pyinstaller==6.10.0" python (Join-Path $root "scripts/release_manifest.py") build --bundle-root $bundle --metadata-json $metadataPath --detached $detached
Remove-Item -LiteralPath $metadataPath -Force
Write-Output "Release bundle staged at $bundle"
Write-Output "No signing or deployment was performed."
