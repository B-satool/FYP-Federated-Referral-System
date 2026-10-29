# Supported FHIR R4 (4.0.1) subset

> **v2:** every institution runs the same service (`services/provider`). Records come from `GET {institution}/fhir/patients/{local_id}/records` as a searchset `Bundle` (Patient, Encounter, Condition, Procedure, MedicationRequest, Observation, DiagnosticReport), filtered by category and date and by that institution's access decision. The v1 endpoint table below is kept for reference.

The project exchanges a **deliberately limited** FHIR subset. Sources expose *custom project endpoints* that return FHIR content. These are not a FHIR server.

| Endpoint | Returns |
|---|---|
| `GET {clinic}/fhir/patients/{id}/records?categories=…` | `Bundle` (searchset): Patient, Encounter, Condition, MedicationRequest, MedicationStatement, DocumentReference |
| `GET {lab}/fhir/patients/{id}/results` | `Bundle` (searchset): Patient, Observation, DiagnosticReport |
| `GET {specialist}/fhir/patients/{id}/records` | `Bundle` (searchset): Patient, Encounter (consultations), Condition |

When categories are withheld by source authorization, the bundle contains an `OperationOutcome` entry (`search.mode = outcome`). The central platform reports such a result as **partial**.

## Supported elements

| Information | Resource | Elements used |
|---|---|---|
| Patient and institution identity | Patient | `identifier` (system `urn:referral-demo:institution:{inst}:patient-id`), `name`, `gender`, `birthDate`, `meta.versionId`, `meta.source` |
| Encounter | Encounter | `status`, `class` (v3 ActCode AMB), `type.text`, `reasonCode.text`, `period.start`, `participant.individual.display` |
| Documented diagnosis | Condition | `code` (SNOMED CT where known, plus text), `clinicalStatus`, `onsetDateTime`, `recordedDate` |
| Lab value | Observation | `status`, `category` laboratory, `code` (LOINC), `valueQuantity` (value + unit as recorded) / `valueString` / `dataAbsentReason`, `effectiveDateTime` (collection), `issued`, `referenceRange.text`, `specimen.display` |
| Grouped report | DiagnosticReport | `status`, `code` (LOINC), `effectiveDateTime`, `issued`, `result`, `conclusion` |
| Prescription | MedicationRequest | `status`, `intent`, `medicationCodeableConcept.text` (original name), `dosageInstruction` (`text`, `route.text`, `timing.code.text`, `doseAndRate.doseQuantity`), `dispenseRequest.validityPeriod`, `authoredOn`, `requester.display`, `note` |
| Reported medication use | MedicationStatement | `status`, `medicationCodeableConcept.text`, `dosage.text`, `dateAsserted`, `informationSource`, `note` |
| Document metadata | DocumentReference | `status`, `type`, `date`, `author.display`, `description`, `content.attachment` (metadata only) |
| Referral | ServiceRequest | `identifier` (referral ID), `status`, `intent`, `priority`, `code.text`, `subject`, `requester`, `performer`, `reasonCode`, `supportingInfo` |
| Fulfilment work | Task | `status`, `intent`, `focus`, `for`, `owner`, `output.valueString` (returned consultation) |
| Collection | Bundle | `searchset` (source results), `collection` (package) |

Every clinical resource carries `meta.versionId`, which is the source record version. Together with `id`, it is the deduplication key (FR-20).

## Status mapping (explicit)

| Application status | ServiceRequest.status | Task.status |
|---|---|---|
| draft / awaiting information / awaiting approval | draft | — |
| approved, submitted | active | requested |
| acknowledged | active | received |
| accepted | active | accepted |
| response returned / follow-up pending | active | completed |
| closed | completed | completed |
| declined / cancelled | revoked | rejected / cancelled |

The mapping lives in `libs/common/refcommon/fhir.py`.

## Project envelopes (not standard FHIR)

`referral-package/1.0` and `specialist-event/1.0` (`libs/common/refcommon/exchange.py`) carry the approved brief, structured medication flags, rule and mapping versions, acknowledgments and the approval hash. They sit **alongside** the FHIR Bundle, and no extra fields are inserted into standard resources. Each envelope has `contract_note: "Project API contract (not a standard FHIR resource)"`.

## Validation

- **Structural checks.** `refcommon.fhir.validate_resource` checks required elements, R4 status codes and numeric values before import. Invalid resources are excluded and counted, giving a *partial* or *invalid* retrieval result. This is **not** a conformance claim.
- **Conformance check.** `scripts/fhir-validate.ps1` exports one representative resource per implemented type and runs the official **HL7 FHIR validator** (`-version 4.0.1`). The latest report is in `contracts/fhir-samples/`.
