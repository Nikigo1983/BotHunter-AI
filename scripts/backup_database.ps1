$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$BackupDir = Join-Path $RootDir "backups"
$Container = if ($env:POSTGRES_CONTAINER) { $env:POSTGRES_CONTAINER } else { "bothunter-postgres" }
$DbUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "bothunter" }
$DbName = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "bothunter" }
$Timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$Output = Join-Path $BackupDir "bothunter_$Timestamp.sql"

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$running = docker ps --format "{{.Names}}" 2>$null | Select-String -Pattern "^$([regex]::Escape($Container))$" -Quiet
if (-not $running) {
    Write-Error "Container '$Container' is not running. Start: docker compose -f docker/docker-compose.yml up -d"
}

docker exec $Container pg_dump -U $DbUser $DbName | Set-Content -Path $Output -Encoding utf8
Write-Host "Backup saved: $Output"
