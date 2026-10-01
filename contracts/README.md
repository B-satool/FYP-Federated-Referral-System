# Shared contracts

Agreed before parallel coding (Roadmap §5). Implementations are in `libs/common/refcommon/exchange.py` (envelopes), `services/central/app/models` (entities) and `services/central/app/serializers.py` (API shapes). Generated API documentation is available at each service's `/docs` (OpenAPI).

| Contract | Fields | Example |
|---|---|---|
| PatientRef | `institution_id` + `local_patient_id`, never one alone | `examples/PatientRef.json` |
| PatientLink | status (pending/verified/invalidated/rejected), verifier, basis, timestamps, match check, event history | `examples/PatientLink.json` |
| EvidenceItem | evidence_id, patient ref, source institution/record/version, clinical time, retrieval/upload time, original and current values, review state, verification status, document page/region | `examples/EvidenceItem.json` |
| RetrievalResult | source, status (successful/empty/partial/denied/unavailable/invalid), counts, user-facing message, retryable, attempts | `examples/RetrievalResult.json` |
| MedicationEntry | original name, ingredient/class with codes, mapping source/version/status, current-use state and verifier, dates, dose, evidence reference | `examples/MedicationEntry.json` |
| MedicationFlag | flag ID and version, kind, rule ID/version, medication/evidence references, message, review history | `examples/MedicationFlag.json` |
| ReferralPackage | `referral-package/1.0` envelope: immutable version, brief, selected evidence snapshot, structured flags, evaluation summary, limitations, approver, approval time, content hash, delivery key, FHIR Bundle | `examples/ReferralPackage.envelope.json` |
| SpecialistEvent | `specialist-event/1.0`: event key, type, actor, time, data | see `refcommon/exchange.py` |
| ReviewItem / Clarification / Job | separate status models | `examples/*.json` |

Examples are exported from a running stack with `scripts/export_contract_examples.py`. FHIR samples and the HL7 validator report are in `fhir-samples/`.

**Change rule.** A contract change needs an issue or PR approved by the consuming member before implementation. Update these examples and the affected checks in the same merge.
