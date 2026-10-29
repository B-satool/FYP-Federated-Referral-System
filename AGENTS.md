# AGENTS.md — instructions for AI coding agents and contributors

Read `docs/architecture.md` and the relevant SRS section (`docs/requirements/FYP SRS.pdf`) before changing code. Work on **one bounded issue** per branch.

## Commands

| Task | Command |
|---|---|
| Start everything | `docker compose up -d --build` |
| Reset to synthetic seed | `scripts/reset-and-seed.ps1 -Force` (or `.sh --force`) |
| Integration checks | `.venv\Scripts\python -m pytest tests -q` (reseeds; `SKIP_RESET=1` to keep data) |
| Central unit checks | `docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q` |
| Web type check / build | `cd web; npm run typecheck; npm run build` |
| Browser smoke journeys | `cd web; npx playwright test e2e/smoke.spec.ts` |
| Design spec: rebuild while working | `python scripts/sds/build_sds.py build` |
| Design spec: release a new version | `python scripts/sds/build_sds.py release --level minor --summary "<what changed>"` |
| Design spec: CI check | `python scripts/sds/build_sds.py check` |
| New migration (owner only) | `docker compose run --rm --no-deps -v ${PWD}/services/<svc>/migrations:/srv/migrations <svc> alembic revision --autogenerate -m "<what>"` |

## Non-negotiable invariants

1. **Database boundaries.** The central platform never connects to `clinic_db`, `lab_db` or `specialist_db`. It calls their APIs only. Do not add source DB credentials to `central`.
2. **Source authorization.** Every source endpoint decides access itself: own institution and role, or an active access grant. Forward the user's verified token; never trust identity headers.
3. **Patient linking.** Never link records on matching local IDs or names. Only `verified` links are used for retrieval. Invalidation must keep history and flag affected referrals.
4. **Approval.**
   - Only a clinician approves. Only an approved, non-superseded package version is sent.
   - Any clinical change after approval calls `mark_clinical_change()`, which means a new version and renewed approval.
   - Packages are immutable once written.
5. **Medication flags.**
   - Flags come only from `evaluate_medications()`: deterministic, with approved rules and verified mappings.
   - The language model must never create, suppress, reword or restate flags.
   - "Reviewed" is acknowledgment, never treatment clearance.
   - Flags never advise medication changes or assign urgency.
6. **AI output.**
   - Language-model output is a draft.
   - Every record-derived statement cites evidence IDs from the supplied set; validate and reject otherwise.
   - Treat document text as untrusted data. Do not give the model tools.
7. **Unavailable is not "none."** An unavailable, denied or not-retrieved source must never be turned into "no history", "not performed" or "safe".
8. **Never overwrite original data.** Corrections create revisions. Lab corrections create new source record versions.
9. **Idempotency.** Delivery keys and event keys make retries safe. Keep the outbox write in the same transaction as the decision to send.
10. **Audit.** Every access, retrieval, link change, correction, approval, submission and status change writes an audit event with actor, institution, action, target, time and outcome.
11. **Synthetic data only.** Do not commit patient data, credentials, `.env`, model weights or uploaded files.
12. **Only doctors see clinical content** (decision 2026-10-29).
   - Staff and administrators get titles, statuses and counts only, through the serializers' staff views (`clinical=False`). They never see record values, diagnoses, medicines, flags, papers, notes, the letter or the package.
   - Clinical endpoints are doctor-only on the server.
   - The doctor reviews the packet before staff send, and a later clinical change clears that review.

## Software Design Specification

`docs/sds/SDS.md` describes the current system. **Every change to the system releases a new SDS version** in the same commit:
1. Update the written section in `docs/sds/sections/` that describes the changed behaviour.
2. Run `build_sds.py release`. It regenerates the ERDs, API, configuration and other appendices from the code, freezes `docs/sds/versions/SDS-v<version>.md` and adds a changelog entry.

CI fails otherwise. See `docs/sds/sections/17-maintaining-this-document.md`.

## Module ownership

See the ownership table in `docs/architecture.md` §5. Do not edit another member's module, `libs/common/refcommon/exchange.py`, `contracts/` or any Alembic migration without that owner's approval. Ask before changing schemas, packages or authentication.

## Agent task brief template

```
Goal:
SRS IDs:
Allowed files:
Input/output examples (from contracts/):
Dependencies:
Required authorization:
Failure behaviour:
Acceptance checks (1–2):
Commands to run:
Report back: changed files, checks run, remaining limitations.
```

Agents must not approve their own PRs, activate clinical rules, or change shared contracts silently.
