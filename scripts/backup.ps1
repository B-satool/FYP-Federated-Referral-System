<#
.SYNOPSIS
  Back up all four application databases, the Keycloak database and protected document storage.
.DESCRIPTION
  Dumps are written inside the postgres container and copied out (binary-safe).
  A manifest records the git commit, migration revisions, seed version and
  active rule versions so a restore can be matched to a release.
#>
param([string]$OutRoot = "backups")
$ErrorActionPreference = "Stop"
$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$dir = Join-Path $OutRoot $ts
New-Item -ItemType Directory -Force $dir | Out-Null
$dbs = "central_db", "clinic_db", "lab_db", "specialist_db", "keycloak"
foreach ($db in $dbs) {
    docker compose exec -T postgres pg_dump -U postgres -Fc -f "/tmp/$db.dump" $db
    if ($LASTEXITCODE -ne 0) { throw "pg_dump $db failed" }
    $cid = docker compose ps -q postgres
    docker cp "${cid}:/tmp/$db.dump" (Join-Path $dir "$db.dump") | Out-Null
    docker compose exec -T postgres rm -f "/tmp/$db.dump"
}
$abs = (Resolve-Path $dir).Path
docker run --rm -v referral_documents:/data:ro -v "${abs}:/backup" alpine tar czf /backup/documents.tgz -C /data .
if ($LASTEXITCODE -ne 0) { throw "document backup failed" }

$revisions = @{}
foreach ($db in "central_db", "clinic_db", "lab_db", "specialist_db") {
    $revisions[$db] = (docker compose exec -T postgres psql -U postgres -d $db -tAc "select version_num from alembic_version").Trim()
}
$rules = (docker compose exec -T postgres psql -U postgres -d central_db -tAc "select string_agg(rule_id || 'v' || rule_version || ':' || status, ',') from rule_approvals").Trim()
$manifest = [ordered]@{
    created_utc        = $ts
    git_commit         = (git rev-parse HEAD 2>$null)
    migration_revision = $revisions
    seed_version       = "synthetic-seed/1.0"
    rule_approvals     = $rules
    files              = (Get-ChildItem $dir | ForEach-Object { @{ name = $_.Name; bytes = $_.Length; sha256 = (Get-FileHash $_.FullName).Hash } })
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $dir "manifest.json")
Write-Host "Backup written to $dir"
