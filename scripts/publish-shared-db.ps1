<#
.SYNOPSIS
  Publish a copy of the local demo databases to the team's shared hosted database (Neon).
.DESCRIPTION
  The app keeps running on the fast local PostgreSQL. This script copies the current local
  central and institution databases to the shared server so teammates can inspect the
  data from anywhere. Each run REPLACES the shared copy. Keycloak (logins) and uploaded files
  are not copied. Requires the *_SHARED_DATABASE_URL lines written by scripts/setup_shared_db.py.
#>
$ErrorActionPreference = "Stop"
$env_ = @{}
Get-Content (Join-Path (Split-Path -Parent $PSScriptRoot) ".env") | Where-Object { $_ -match '^\s*([A-Z_]+)=(.*)$' } | ForEach-Object {
    $null = $_ -match '^\s*([A-Z_]+)=(.*)$'; $env_[$Matches[1]] = $Matches[2]
}
foreach ($owner in "central", "drali", "chughtai", "ziauddin", "akuh") {
    $key = "$($owner.ToUpper())_SHARED_DATABASE_URL"
    if (-not $env_[$key]) { throw "$key missing in .env; run scripts/setup_shared_db.py --copy-only first" }
    $target = $env_[$key] -replace '^postgresql\+psycopg://', 'postgresql://'
    $role = ([Uri]($target -replace '^postgresql://', 'http://')).UserInfo.Split(':')[0]
    Write-Host "Publishing ${owner}_db ..."
    docker compose exec -T postgres pg_dump -U postgres -Fc --no-owner --no-privileges -f "/tmp/$owner.dump" "${owner}_db"
    if ($LASTEXITCODE -ne 0) { throw "dump of $owner failed" }
    docker compose exec -T postgres pg_restore --clean --if-exists --no-owner --no-privileges --role=$role -d $target "/tmp/$owner.dump"
    if ($LASTEXITCODE -ne 0) { Write-Warning "pg_restore reported warnings for $owner (usually harmless on the first publish)" }
    docker compose exec -T postgres rm -f "/tmp/$owner.dump"
}
Write-Host "Shared copy updated at $((Get-Date).ToString('u')). Credentials: shared-db-credentials.md"
