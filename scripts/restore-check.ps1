<#
.SYNOPSIS
  Restore a backup into a DISPOSABLE environment and confirm an approved referral and its documents reopen.
.DESCRIPTION
  Creates an isolated network, PostgreSQL container and document volume (nothing
  touches the running stack), restores every dump, then runs the central code
  against the restored copy to load the latest approved package and verify each
  of its documents by SHA-256. Everything is removed afterwards.
#>
param([Parameter(Mandatory = $true)][string]$BackupDir)
$ErrorActionPreference = "Stop"
$abs = (Resolve-Path $BackupDir).Path
$net = "referral-restore-net"; $db = "referral-restore-db"; $vol = "referral-restore-docs"
$pw = "restore-check"
try {
    docker network create $net | Out-Null
    docker volume create $vol | Out-Null
    docker run -d --name $db --network $net -e POSTGRES_PASSWORD=$pw -v "${abs}:/backup:ro" postgres:16-alpine | Out-Null
    for ($i = 0; $i -lt 30; $i++) { docker exec $db pg_isready -U postgres 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { break }; Start-Sleep 1 }
    Start-Sleep 2
    foreach ($name in "central_db", "clinic_db", "lab_db", "specialist_db", "keycloak") {
        $owner = @{ central_db = "central"; clinic_db = "clinic"; lab_db = "lab"; specialist_db = "specialist"; keycloak = "keycloak" }[$name]
        docker exec $db psql -U postgres -qc "CREATE USER $owner WITH PASSWORD '$pw'" | Out-Null
        docker exec $db psql -U postgres -qc "CREATE DATABASE $name OWNER $owner" | Out-Null
        docker exec $db pg_restore -U postgres -d $name --no-owner --role=$owner "/backup/$name.dump"
        if ($LASTEXITCODE -ne 0) { throw "restore of $name failed" }
    }
    docker run --rm -v "${vol}:/data" -v "${abs}:/backup:ro" alpine tar xzf /backup/documents.tgz -C /data
    $check = @'
import hashlib, sys
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Document, Referral, ReferralPackage
from app.documents.storage import storage
with SessionLocal() as db:
    pkg = db.scalars(select(ReferralPackage).order_by(ReferralPackage.id.desc())).first()
    if pkg is None:
        sys.exit("no approved package in backup")
    ref = db.get(Referral, pkg.referral_id)
    print(f"approved package {ref.reference} v{pkg.version} hash {pkg.content_hash[:16]} restored; status {ref.status}")
    docs = db.scalars(select(Document).where(Document.deleted_at.is_(None))).all()
    bad = 0
    for d in docs:
        data = storage.path(d.storage_key).read_bytes()
        ok = hashlib.sha256(data).hexdigest() == d.sha256
        bad += not ok
    print(f"{len(docs)} documents reopened, {bad} checksum mismatches")
    sys.exit(1 if bad else 0)
'@
    docker run --rm --network $net -v "${vol}:/data/documents" -e "DATABASE_URL=postgresql+psycopg://central:${pw}@${db}:5432/central_db" referral-central python -c $check
    if ($LASTEXITCODE -ne 0) { throw "restore verification failed" }
    Write-Host "Restore check PASSED"
}
finally {
    docker rm -f $db 2>$null | Out-Null
    docker volume rm $vol 2>$null | Out-Null
    docker network rm $net 2>$null | Out-Null
}
