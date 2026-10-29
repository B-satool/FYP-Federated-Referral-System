# 16. Known limitations, risks and open decisions

> **Superseded in part by section 18 (spec v4, 2026-10-30).** The spec v4 limits (a compromised device, the platform serving the client code, visible metadata, the AI relay, client-reported decrypt events) are in docs/security-model.md.

## 16.1 Built differently from the SRS or not built

| Item | Status | Reference |
|---|---|---|
| Specialist response form | Replaced: the receiving doctor accepts or declines; response endpoints kept for old data | Decision 2026-10-28, no specialist response |
| Receiver gets a notification instead of the package (read-through access window) | Not built; the receiver still gets the package and removes it at expiry | Decisions 2026-10-28, access window and referral expiry |
| Forwarding test results to the receiving hospital | Contract, outbox kind and endpoint exist; nothing creates the message | Section 6.10 |
| List-then-fetch retrieval, cross-institution lab standardisation (LOINC and UCUM), merged medicine view for the AI | Planned | Decision 2026-10-28, retrieval from all sources |
| FHIR International Patient Summary per institution | Not adopted; future work | Same decision |
| Patient consent record | Not modelled, by team decision | Access-window decision |

## 16.2 Risks

| Risk | Impact | Current mitigation | Further action |
|---|---|---|---|
| DRAP register brands loaded without per-row pharmacist review | A wrong mapping gives the wrong interactions and rules | Strict matching, source note on the medicine, ambiguous names never guessed, veterinary products excluded where known | Clinical review of the register mappings; fetch details for the 5,434 rows not yet checked for veterinary use |
| Imported rules (DDInter, drug labels) are not clinically reviewed | Irrelevant or incomplete flags | Labelled "automatically generated, not clinically reviewed" with the source shown | A named clinical reviewer approves the rule sets |
| De-identification is pattern-based | A rare detail could identify someone | Synthetic data only; external models off by default | Agreement with the operating institution, or a local model, before real data |
| Page images to Google Vision cannot be de-identified | Names and CNICs on papers leave the computer | Off by default; synthetic papers only | Institutional agreement |
| No encryption at rest by the application | Disk theft exposes data | Temporary working set; separate databases | Encrypted volumes in any hosted deployment |
| A referral never sent, or sent but never accepted, keeps its working set indefinitely | Longer central storage than needed | Only on the platform; the referring side can cancel | A reminder or expiry for idle drafts and pending referrals |
| `dev-cli` password-grant client in the realm | Weakens sign-in policy if exposed | Development only | Remove or disable in hosted realms |
| Local realms imported before role templates | Role changes refused (`502 identity_provider_refused`) | — | Give `service-account-central-api` the `realm-management` role `view-realm` (as in the realm file), or re-import the realm |
| Single PostgreSQL server for all owners | Shared failure domain; separation is logical, not physical | Separate databases and logins | Separate servers for real institutions |
| The model's dosing-word filter rejects some harmless answers | AI recommendation unavailable more often | Default selection stands | Prompt asking the model not to mention doses |

## 16.3 Policy values awaiting confirmation

These are placeholders until the operating institution or a clinician confirms them:

- the history window per specialty (`SPECIALTY_HISTORY_YEARS`);
- the default selection window (183 days);
- the maximum number of sources (5);
- grant duration (14 and 30 days);
- the accepted-referral hold (30 days) and the grace period (72 hours);
- document retention (365 days);
- the wording of the flag disclaimer (`FLAG_DISCLAIMER`).

## 16.4 Documentation debt

`docs/architecture.md`, `docs/operations.md` and `docs/fhir-subset.md` still describe parts of version 1 (clinic, lab and specialist services). This SDS supersedes them for the current design. Those files should be updated or point here.
