$ErrorActionPreference = "Stop"

$bundleRoot = Join-Path $PSScriptRoot "bundle"
$runtimeState = Join-Path $PSScriptRoot "runtime\state\kch_011_agent_shadow.sqlite3"
$registry = Join-Path $bundleRoot "config\KCH_REGISTRY_v0.11.0.json"
$python = "C:\Python314\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Pinned Python runtime unavailable: $python"
}

$wheelFiles = @(
    Get-ChildItem -LiteralPath (Join-Path $bundleRoot "dist") -Filter "*.whl" -File
    Get-ChildItem -LiteralPath (Join-Path $bundleRoot "vendor") -Filter "*.whl" -File
)
if ($wheelFiles.Count -ne 8) {
    throw "Expected 8 sealed wheels, observed $($wheelFiles.Count)"
}

$secretBytes = New-Object byte[] 32
$random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $random.GetBytes($secretBytes)
}
finally {
    $random.Dispose()
}
$env:KCH_011_HMAC_SECRET = ([BitConverter]::ToString($secretBytes)).Replace("-", "")
$env:KCH_011_BUNDLE_ROOT = $bundleRoot
$env:KCH_011_REGISTRY = $registry
$env:KCH_011_STATE = $runtimeState
$env:KCH_011_PROFILE = "agent-shadow"
$env:PYTHONPATH = (($wheelFiles | Sort-Object FullName | ForEach-Object FullName) -join [IO.Path]::PathSeparator)

& $python -m kwancode_harness.mcp_server
exit $LASTEXITCODE
