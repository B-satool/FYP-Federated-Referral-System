# Approvals

Changes that touch schemas, authentication, packages or the AGENTS.md invariants need the project owner's approval (AGENTS.md). This file records them.

| Date | Approved by | Scope | Reference |
|---|---|---|---|
| 2026-10-29 | Project owner (project lead), for the team | Every change in section 13 of the architecture spec v4 (A1 to A11). New tables and columns: key directory, wrapped keys, signed package manifests, consent, adapter policy, purge receipts, reminders and extensions, patient keys. Machine-to-machine authentication between the platform and the institution adapters, the hospital-signed key directory and patient login. Consent and adapter policy replace per-patient sharing grants. Encrypted packages with signed manifests (no plaintext at the platform). New and changed AGENTS.md invariants. Purge of package content and wrapped keys on close. Medication flags evaluated in the browser. Doctor, staff and patient clients hold keys. | `e2e-architecture-spec-v4.md` (2026-10-29), sections 0.2 and 13 |
| 2026-10-29 | Project owner | Only doctors see clinical content; the doctor reviews the packet | `docs/decisions/2026-10-29-doctor-only-clinical-content.md` |
| 2026-10-29 | Project owner | Patient accounts and a patient view | `docs/decisions/2026-10-29-patient-view.md` |

Anything not in this table still needs the owner's approval first.
