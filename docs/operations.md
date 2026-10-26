# Operations

## Environments

| Environment | How | Data |
|---|---|---|
| Local / demo (supported baseline) | `docker compose up -d --build` on one machine | Synthetic seed only |
| Private staging/demo host (optional) | Same Compose file on a VM behind a TLS reverse proxy (see below) | Synthetic seed only |

The services may run on one machine. Independence is a service and ownership boundary, not a hardware requirement.

### Hosted deployment checklist (TLS and secrets)

1. **Secrets.** Copy `.env.example` to `.env` on the host and generate every secret (`openssl rand -hex 24`). Never commit `.env`.
2. **TLS.** Put a TLS-terminating proxy (Caddy, nginx or Traefik) in front of `web` (port 3000) and `keycloak` (port 8080) on HTTPS hostnames.
3. **Keycloak.** Set `KC_HOSTNAME=https://id.example.org`, switch the command to `start` (production mode, not `start-dev`) and keep `sslRequired=external`.
4. **Redirect URIs.** In the realm, update `referral-web` redirect URIs and web origins to the HTTPS web hostname. Set `KEYCLOAK_PUBLIC_URL` and the web build arg `VITE_OIDC_AUTHORITY` accordingly.
5. **Exposed ports.** Do not publish ports 8000–8003 or 5432; only the proxy should be reachable.
6. **Release record.** Deploy a tagged release and record the commit, image IDs, migration revisions, seed version, rule/mapping versions and model configuration (`scripts/backup.ps1` writes most of these into its manifest).
7. **Smoke check.** After deployment run a smoke check: login, patient retrieval and one referral journey (`web/e2e/smoke.spec.ts` with `WEB_URL=https://…`).

## Account disabling and revocation policy (FR-05)

| Action | Effect |
|---|---|
| Administrator disables an account (Accounts screen) | Keycloak user disabled and all sessions logged out. Central `users.account_status = disabled`, so **every central request is rejected immediately**, including access to retained referral data. |
| Existing access tokens at source services | Each service introspects tokens (10 s cache). An ended session is inactive, so sources reject the token within about 10 s rather than at JWT expiry (5 min). |
| New sign-in | Refused by Keycloak |
| Source administrator revokes an access grant | The next request from that institution is denied by the source. On the next retrieval, central marks evidence previously retained from that source as `access_revoked`: values hidden, deselected, excluded from briefs and packages. Approved package snapshots are kept for history. |
| Queued jobs | Before running, each worker job re-checks that the requester is active and still belongs to the referral's institution. |

This behaviour is tested in `tests/test_t1_foundation.py::test_disabled_account_loses_access_immediately_and_at_sources`.

## Retention (provisional; confirm before hosted use)

| Data | Retention |
|---|---|
| Referral working set: retrieved records, papers and OCR, medicines, flag text, letter, package content, outbox payloads, responses, results | Removed `WORKING_SET_GRACE_HOURS` (72) after the answer is returned or the referral ends, or at the latest `WORKING_SET_MAX_DAYS` (60) after the first retrieval. Only once every package, order and the clinic's copy is delivered (worker `purge_working_sets`, every 10 minutes, audited `retention.purge_working_set`). See `docs/data-lifecycle.md`. |
| Uploaded document copies, page images, OCR text (referrals that end without a purge) | Also deleted `DOCUMENT_RETENTION_DAYS` (default 365) after the referral is closed (hourly `retention_sweep` task) |
| Sent packages | The manifest and SHA-256 are kept; the content stays with the receiving institution and in the sending clinic's `sent_copies` |
| Access grants | Expire (`DEFAULT_GRANT_DAYS` 14, at most `MAX_GRANT_DAYS` 30) and are revoked at every institution when the referral finishes (`close_referral_grants`, every minute). Grants made before expiry existed show as `legacy_no_expiry`. |
| Audit events, referral events | Retained (append-only) |
| Redis queue | Transient. Not a source of truth. |

Application logs record request metadata only. Clinical content and tokens are not logged.

## Backup and restore

```powershell
.\scripts\backup.ps1                                     # backups/<UTC timestamp>/{*.dump, documents.tgz, manifest.json}
.\scripts\restore-check.ps1 -BackupDir backups\<ts>      # restores into a DISPOSABLE network/DB/volume and verifies
```

`restore-check` restores all five databases and the document archive into containers that do not touch the running stack. It then runs the central code against the copy and confirms that the latest approved package and every document reopen with matching SHA-256 checksums.

Full disaster recovery into the live stack:
1. `docker compose stop central worker clinic lab specialist`.
2. For each database: `pg_restore --clean --if-exists -d <db>` from the dump.
3. Extract `documents.tgz` into the `referral_documents` volume.
4. Start the services; readiness checks must pass.

## Upgrades and rollback

1. Run `scripts/backup.ps1` first; it records migration revisions in the manifest.
2. Deploy the new tagged images. Each service runs `alembic upgrade head` on start; readiness (`/ready`) must pass.
3. Run the post-deploy smoke check.
4. Keep the previous release images. **Roll back application images only when the schema is compatible**; otherwise restore from the backup. Never blindly downgrade migrations or overwrite newer data.

## Health and monitoring

Every service exposes `/health` (process) and `/ready` (database reachable), and Compose health checks use them. Delivery problems appear in the clinic work queue (`delivery_problems`) and on the referral's *Specialist & follow-up* tab. The specialist's outbox status appears on the case page.
