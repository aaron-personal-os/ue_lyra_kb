# OA Pages deploy script
# Usage: run deploy.bat or powershell -File deploy.ps1
# Uploads dist/ directly to OA Pages

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# === Config ===
$cname = "ue-lyra-kb.pages.woa.com"
$description = "Lyra UE Knowledge Base"
$maxBatchSize = 3 * 1024 * 1024  # 3MB per batch (JSON serialization adds ~30-50% overhead, server limit is 5MB)

# === Get API Key ===
$apiKey = [Environment]::GetEnvironmentVariable('OA_PAGES_API_KEY', 'User')
if (-not $apiKey) { $apiKey = [Environment]::GetEnvironmentVariable('OA_PAGES_API_KEY', 'Machine') }
if (-not $apiKey) { $apiKey = $env:OA_PAGES_API_KEY }
if (-not $apiKey) {
    Write-Error "OA_PAGES_API_KEY not set. Please set environment variable first."
    exit 1
}

# === Paths ===
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$distDir = Join-Path $scriptDir 'dist'
$tmpFile = Join-Path $scriptDir '_tmp_body.json'

# === Check dist ===
if (-not (Test-Path $distDir)) {
    Write-Error "dist/ not found. Run build.bat first."
    exit 1
}

if (-not (Get-ChildItem -Path $distDir -Recurse -File)) {
    Write-Error "dist/ is empty. Run build.bat first."
    exit 1
}

Write-Host ""
Write-Host "=== Lyra KB - Deploy to OA Pages ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Source:  $distDir" -ForegroundColor Cyan
Write-Host "Target:  https://$cname" -ForegroundColor Cyan
Write-Host ""

# Binary file extensions (need base64 encoding)
$binaryExts = @('.png','.jpg','.jpeg','.gif','.webp','.ico','.woff','.woff2','.ttf','.eot','.otf',
    '.pf_fragment','.pf_index','.pf_meta','.pagefind','.wasm')

# === Collect files ===
$excludeNames = @('serve.bat', 'serve.sh')
$allFiles = Get-ChildItem -Path $distDir -Recurse -File | Where-Object { $excludeNames -notcontains $_.Name }
Write-Host "Files to upload: $($allFiles.Count)" -ForegroundColor Cyan

# === Check if site exists ===
$checkResult = curl.exe -s -w "`nHTTP_CODE:%{http_code}" -H "X-Api-Key: $apiKey" "https://pages.woa.com/api/repos/$cname"
$checkCode = ($checkResult -split "`n" | Where-Object { $_ -match 'HTTP_CODE:' }) -replace 'HTTP_CODE:', ''
$siteExists = ($checkCode.Trim() -eq '200')

if ($siteExists) {
    Write-Host "Site exists, updating..." -ForegroundColor Yellow
} else {
    Write-Host "Site not found, creating..." -ForegroundColor Yellow
}

# === Build file entries ===
$fileEntries = @()
foreach ($file in $allFiles) {
    $relativePath = $file.FullName.Substring($distDir.Length + 1).Replace('\', '/')
    $ext = $file.Extension.ToLower()
    
    if ($binaryExts -contains $ext) {
        $content = [Convert]::ToBase64String([IO.File]::ReadAllBytes($file.FullName))
    } else {
        $content = [IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)
    }
    
    $size = [System.Text.Encoding]::UTF8.GetByteCount($relativePath) + [System.Text.Encoding]::UTF8.GetByteCount($content) + 50
    $fileEntries += @{ path = $relativePath; content = $content; size = $size }
}

# === Split into batches ===
$batches = @()
$currentBatch = [ordered]@{}
$currentSize = 0

foreach ($entry in $fileEntries) {
    if ($currentSize + $entry.size -gt $maxBatchSize -and $currentBatch.Count -gt 0) {
        $batches += ,$currentBatch
        $currentBatch = [ordered]@{}
        $currentSize = 0
    }
    $currentBatch[$entry.path] = $entry.content
    $currentSize += $entry.size
}
if ($currentBatch.Count -gt 0) {
    $batches += ,$currentBatch
}

Write-Host "Batches: $($batches.Count)" -ForegroundColor Cyan
Write-Host ""

# === Upload ===
$failedBatches = @()

for ($i = 0; $i -lt $batches.Count; $i++) {
    $batch = $batches[$i]
    
    if ($i -eq 0 -and -not $siteExists) {
        $body = @{ cname = $cname; description = $description; files = $batch }
        $url = "https://pages.woa.com/api/sites"
        $method = "POST"
    } else {
        $body = @{ files = $batch }
        $url = "https://pages.woa.com/api/sites/$cname"
        $method = "PUT"
    }
    
    $json = $body | ConvertTo-Json -Depth 5 -Compress
    $jsonBytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    [IO.File]::WriteAllBytes($tmpFile, $jsonBytes)
    
    $fileSizeMB = [math]::Round($jsonBytes.Length / 1MB, 2)
    Write-Host ("Batch {0}/{1}: {2} files ({3} MB)..." -f ($i+1), $batches.Count, $batch.Count, $fileSizeMB) -NoNewline
    
    $result = curl.exe -s -w "`nHTTP_CODE:%{http_code}" -X $method $url -H "X-Api-Key: $apiKey" -H "Content-Type: application/json" --data-binary "@$tmpFile" --max-time 120
    
    $httpCode = ($result -split "`n" | Where-Object { $_ -match 'HTTP_CODE:' }) -replace 'HTTP_CODE:', ''
    
    if ($httpCode.Trim() -eq '200') {
        Write-Host " OK" -ForegroundColor Green
    } else {
        $responseBody = ($result -split "`n" | Where-Object { $_ -notmatch 'HTTP_CODE:' }) -join ""
        Write-Host (" FAILED ({0}): {1}" -f $httpCode.Trim(), $responseBody) -ForegroundColor Red
        $failedBatches += ($i + 1)
    }
    
    if ($i -lt $batches.Count - 1) { Start-Sleep -Seconds 1 }
}

# === Cleanup ===
if (Test-Path $tmpFile) { Remove-Item $tmpFile }

# === Result ===
Write-Host ""
if ($failedBatches.Count -eq 0) {
    Write-Host "=== Deploy SUCCESS ===" -ForegroundColor Green
    Write-Host "Uploaded $($allFiles.Count) files in $($batches.Count) batches" -ForegroundColor Green
    Write-Host "URL: https://$cname" -ForegroundColor Cyan
} else {
    Write-Host ("=== Deploy PARTIAL FAILURE (Batch: {0}) ===" -f ($failedBatches -join ', ')) -ForegroundColor Red
    Write-Host "Re-run to retry (PUT is idempotent)" -ForegroundColor Yellow
}
