# Decision: data lifecycle, AI packet selection and role screens (spec v3)

- **Date:** 2026-10-27
- **Status:** approved by the project lead (repository owner) in the working session; **pending written confirmation from the supervisor and the module owners** (AGENTS.md, "Module ownership").
- **Sources:** `architecture-spec-v3.md` and `data-lifecycle.patch` (both written for v1, ported onto the `v2` branch).

## What was decided

1. **Port onto v2.** The v1 patch does not apply to v2: the services, roles and send flow are different. The same behaviour was rebuilt on the v2 code.
2. **Staff finalise the packet.** In v2 staff gather and send, and the doctor reviews medication flags. So staff, not the doctor, make the final choice of what goes into the referral (`POST /evidence/{id}/select` is limited to `clinic_staff`). The spec says "clinician" because v1 had clinician approval.
3. **Language model.** The AI selection uses the existing `LLMProvider` (Anthropic API, `claude-opus-5-5`, structured JSON output, server-side refusal fallback). It runs only when `ANTHROPIC_API_KEY` is set. Without a key the rule-based default applies and the screen says "AI recommendation unavailable".
4. **Changes to the AGENTS.md invariants**, approved by the project lead:
   - **Invariant 4 (packages immutable and kept).** A package stays immutable: its SHA-256 and manifest never change. But its clinical content is removed from the platform when the working set ends. What lasts is the receiving institution's record and the sending clinic's own copy, and `POST .../packages/{v}/verify` checks either one against the kept hash.
   - **Invariant 5 (flags only from `evaluate_medications()`).** This is unchanged for flags. AI suggestions for medicine pairs with no DDInter entry now go **in the package** labelled "AI suggestion, not verified", with the doctor's Ignore/Research decision. They are not flags: they never block sending, they never remove or downgrade a flag, and silence reads "No rule or suggestion on file".
   - **Invariant 8 (never overwrite original data).** For the platform's own copies only: when the working set ends, the retrieved records are deleted from the platform. Source records are never touched, because sources keep every version. A later retrieval creates fresh rows.
5. **Invariant 6 stays as it is.** AI output is a recommendation only, it is validated in code, record text is data, and the model has no tools.

## Placeholders (need an institutional source before any hosted use)

| Setting | Value | Env var |
| --- | --- | --- |
| Grace after the specialist's answer or the end of the referral | 72 hours | `WORKING_SET_GRACE_HOURS` |
| Hard maximum for a working set | 60 days | `WORKING_SET_MAX_DAYS` |
| History retrieved per source | 3 years | `REFERRAL_HISTORY_YEARS` |
| Default-selection window | 183 days | `REFERRAL_WINDOW_DAYS` |
| Access grant default and maximum | 14 and 30 days | `DEFAULT_GRANT_DAYS`, `MAX_GRANT_DAYS` |

## Accepted risk

After the purge, the platform can show that a package existed, what it referred to (the manifest) and its fingerprint, but it cannot show the content again. If both the receiving institution's copy and the sending clinic's copy are lost, and access to the sources has ended, the content cannot be rebuilt.

## Still needed

- Written confirmation from the supervisor and the owners of `libs/common` (sourcekit, exchange), the provider service, the central migrations and the Keycloak role mapping.
- A decision on sending clinical history to an external model, rather than a self-hosted one, before using any real data.
