<#
.SYNOPSIS
  Reset every owner's database to the deterministic synthetic seed.
.DESCRIPTION
  Each service seeds its own database through its own code (the central
  platform never writes source databases). Refuses to run without -Force so a
  shared environment is never wiped silently.
#>
param([switch]$Force)
$ErrorActionPreference = "Stop"
if (-not $Force) { Write-Error "This wipes ALL demo data (referrals, uploads, source records). Re-run with -Force." }
foreach ($svc in "drali", "chughtai", "ziauddin", "akuh", "central") {
    Write-Host "Seeding $svc ..."
    docker compose exec -T $svc python -m app.seed --reset --yes
    if ($LASTEXITCODE -ne 0) { throw "Seeding $svc failed" }
}
Write-Host "Done. Seed version: synthetic-seed/2.0 (seed-data/patients)"
