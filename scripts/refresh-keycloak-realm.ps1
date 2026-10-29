<#
.SYNOPSIS
  Re-import the Keycloak realm from infra/keycloak/import/referral-realm.json (local development only).
.DESCRIPTION
  Keycloak imports the realm file only on its very first start. After the realm file changes (new roles, patient
  accounts, client permissions), run this to delete the local realm and let Keycloak import it again.
  It removes every local account and session in the realm and recreates the demo accounts from the file.
  Never run this against a hosted deployment.
#>
param([switch]$Force)
$ErrorActionPreference = "Stop"
if (-not $Force) { Write-Error "This deletes the local 'referral' realm and re-imports it. Re-run with -Force." }
$admin = (Get-Content .env | Where-Object { $_ -match '^KEYCLOAK_ADMIN_PASSWORD=' }) -replace '^KEYCLOAK_ADMIN_PASSWORD=', ''
$kc = "/opt/keycloak/bin/kcadm.sh"
docker compose exec -T keycloak $kc config credentials --server http://localhost:8080 --realm master --user admin --password $admin | Out-Null
docker compose exec -T keycloak $kc delete realms/referral
docker compose restart keycloak
Write-Host "Keycloak restarted; it imports the realm from the repository on start. Restart the services afterwards:"
Write-Host "  docker compose restart central worker drali chughtai ziauddin akuh"
