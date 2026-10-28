# 7. Key workflows

Each diagram shows the calls that happen in the code. Names in `code` are the endpoints or functions involved. Every request carries a Keycloak access token that the receiving service verifies (Section 8.1); the diagrams omit this for brevity.

## 7.1 Sign-in and request authentication

```mermaid
sequenceDiagram
    actor U as User
    participant W as Web app
    participant K as Keycloak
    participant C as Central or institution service
    U->>W: open the site
    W->>K: authorization code request with PKCE (client referral-web)
    U->>K: username and password
    K-->>W: authorization code
    W->>K: exchange code and verifier for tokens
    K-->>W: access token (5 min) and refresh token
    W->>C: API call with Authorization Bearer token
    C->>K: JWKS (cached), verify signature, issuer, audience
    C->>K: token introspection (cached 10 s)
    K-->>C: active, roles, groups
    C->>C: central only: users row upserted, account_status must be active
    C-->>W: response, or 401 or 403 (denials audited)
```

## 7.2 Patient link confirmation and access grant

```mermaid
sequenceDiagram
    actor SA as Staff, referring clinic
    participant C as Central
    actor SB as Staff, hospital B
    participant B as Hospital B service
    SA->>C: POST /referrals/{id}/links (target B)
    C->>C: patient_links row (requested), patient_link_events, audit
    C-->>SB: appears under Records requests (work queue)
    SB->>C: POST /patient-links/{id}/lookup
    C->>B: POST /identity/lookup (staff token)
    B-->>C: candidates with field-by-field comparison
    SB->>C: POST /patient-links/{id}/approve (local id, note)
    C->>C: refuse if that record is linked to another patient
    C->>B: POST /sharing/grants (grantee A, patient, referral reference)
    B->>B: access_grants row, expires in 14 days, audit
    C->>C: link verified, event, audit, notify requester
    Note over SA,B: Records at B are now readable by A's doctors and staff for this patient until the grant expires or is revoked
```

## 7.3 Retrieval across linked institutions

```mermaid
sequenceDiagram
    actor S as Staff
    participant C as Central
    participant I as Each linked institution (parallel)
    participant Wk as Worker
    S->>C: POST /referrals/{id}/retrieve
    C->>C: working_set.start, sources = own record + verified records links
    par for every linked institution
        C->>I: GET /patients/{id}/activity (user token, X-Referral-Id)
        I->>I: decide_access (own staff or live grant), audit
        I-->>C: last activity, or 403 denied or expired, or timeout
    end
    C->>C: order by last activity, keep up to MAX_RETRIEVAL_SOURCES, mark the rest skipped
    par for every chosen institution
        C->>I: GET /fhir/patients/{id}/records?since=specialty window
        I-->>C: FHIR searchset Bundle (OperationOutcome lists withheld categories)
    end
    C->>C: importer validates resources, evidence rows, dedupe by source version
    C->>C: source_retrievals rows (successful, partial, empty, denied, expired, unavailable, invalid, skipped)
    C->>C: default selection, medication re-evaluation, audit per source
    C->>Wk: enqueue recommend_selection (if a model is configured)
    C-->>S: per-source results
```

## 7.4 AI packet recommendation

```mermaid
sequenceDiagram
    participant Wk as Worker
    participant P as privacy.py
    participant M as Language model
    participant DB as central_db
    Wk->>DB: candidates (at most 150, older non-default dropped first)
    Wk->>P: check_destination(provider)
    alt external model and LLM_EXTERNAL_ALLOWED is false, or remote without https
        P-->>Wk: refused (ProviderUnavailable)
        Wk->>DB: selection_runs status unavailable, default stands
    else allowed
        Wk->>P: de-identify (no name, CNIC, IDs, birth date, institution or doctor names, dates as days before)
        Wk->>M: system prompt, JSON schema, untrusted data payload (no tools)
        M-->>Wk: JSON answer
        Wk->>Wk: check_schema, validate ids, values, reason length, no advice or dosing words
        alt valid
            Wk->>DB: apply: may add records and mark low relevance, never removes defaults or staff choices
            Wk->>DB: selection_runs completed, audit (destination, deidentified, counts)
        else invalid
            Wk->>DB: selection_runs rejected with the reason, default stands
        end
    end
```

## 7.5 Uploaded paper: OCR and field review

```mermaid
sequenceDiagram
    actor S as Staff
    participant C as Central
    participant Wk as Worker
    participant V as OCR engine (Tesseract, or Google Vision)
    participant M as Language model (optional)
    S->>C: POST /referrals/{id}/documents (file, type)
    C->>C: content-type detection, size and page limits, store with SHA-256
    C->>Wk: jobs row, enqueue process_document
    Wk->>Wk: re-check requester is active and in the referral's institution
    Wk->>Wk: embedded text, or rasterise and preprocess pages
    Wk->>V: page image
    V-->>Wk: lines with positions and confidence
    alt model configured and EXTRACTION_MODE auto or llm
        Wk->>M: de-identified lines (dates kept), strict schema
        M-->>Wk: medicines and labs, each citing line ids
        Wk->>Wk: reject the answer if any id is unknown, fall back to rules (auto)
    else
        Wk->>Wk: rules-extractor/2
    end
    Wk->>C: evidence rows proposed and unverified, linked to page regions
    S->>C: review against the page image: verify, correct, unresolve or exclude
    C->>C: evidence_revisions, medicine list and flags re-evaluated
```

## 7.6 Medicines, flags and the doctor's review

```mermaid
sequenceDiagram
    actor S as Staff
    actor D as Doctor
    participant C as Central
    participant E as evaluate_medications (pure)
    Note over C: any change to records, papers, medicines or the procedure calls workflow.after_change
    C->>C: rebuild the medicine list, group duplicates, map names (DRAP brands, ambiguity)
    C->>E: medicines, procedure tags, conditions, approved rules, DDInter pairs, label rules
    E-->>C: flag candidates (deterministic)
    C->>C: evaluation_runs row, new flag versions, supersede changed flags
    S->>C: POST /medications/manual, /medications/checked (asked the patient, incl. OTC)
    S->>C: resolve dose differences, mark the referral ready
    D->>C: POST /referrals/{id}/flags/{flag}/acknowledge (reviewed, ignore or research, note)
    C->>C: flag_reviews row for that flag version, audit
    D->>C: POST /referrals/{id}/ai-suggestions/review (ignore or research)
```

## 7.7 Sending a version and delivery

```mermaid
sequenceDiagram
    actor S as Staff
    participant C as Central
    participant Wk as Worker (deliver_outbox, every 5 s)
    participant B as Receiving hospital
    participant A as Referring institution
    S->>C: POST /referrals/{id}/send
    C->>C: readiness: every blocking item done
    C->>C: brief (deterministic), PackageEnvelope, SHA-256, manifest
    C->>C: one transaction: referral_packages + outbox deliver_package + outbox sender_copy
    Wk->>B: POST /inbound/referrals (delivery key, service token)
    B->>B: verify hash, store case and package (idempotent by delivery key)
    B-->>Wk: received or already_received
    Wk->>C: referral submitted, delivery_status delivered
    Wk->>A: POST /outbound-copies (copy key)
    A-->>Wk: stored
    Note over Wk,B: on failure the same key is retried, 2^n s up to 120 s, 8 attempts, then delivery problem shown to staff
```

## 7.8 Receiving side: intake, decision, completion and expiry

```mermaid
sequenceDiagram
    actor RS as Receiving staff
    actor RD as Receiving doctor
    participant B as Hospital B service
    participant C as Central
    participant Wk as Worker
    RS->>B: POST /cases/{id}/acknowledge
    B->>C: event acknowledged (outbox thread)
    RS->>C: confirm the arriving patient (intake link approve or register new)
    C->>B: POST /intake/patient
    RS->>B: POST /cases/{id}/assign (doctor)
    alt accept
        RD->>B: POST /cases/{id}/decision accept
        B->>C: event accepted
        C->>C: status accepted, expiry = now + 30 days, notify doctor and staff
        opt needs longer
            RD->>B: POST /cases/{id}/extend-hold (reason)
            B->>C: event hold_extended, expiry = now + 30 days
        end
        RD->>B: POST /cases/{id}/complete
        B->>C: event completed, expiry = now + 72 h, notify both sides
    else decline
        RD->>B: POST /cases/{id}/decision decline (reason)
        B->>C: event declined
        C->>C: status declined, expiry = now, notify doctor and staff
        C->>Wk: enqueue purge_working_sets
    end
    Wk->>C: purge_due: blockers? then remove content, keep manifest and hash
    Wk->>B: outbox expire_shared to POST /inbound/referral-expired
    B->>B: remove packages and forwarded results, keep own decision and notes
```

## 7.9 Referring side follow-through

```mermaid
sequenceDiagram
    actor S as Referring staff
    actor D as Referring doctor
    participant C as Central
    C-->>S: notification: accepted, tell the patient
    S->>C: POST /referrals/{id}/patient-informed (note)
    opt follow-up needed
        S->>C: POST /referrals/{id}/tasks
        S->>C: POST /tasks/{id}/outcome
    end
    alt answer to an information request
        S->>C: POST /clarifications/{id}/answer
        C->>C: outbox clarification_answer to the hospital
    end
    D->>C: POST /referrals/{id}/close (or staff)
    C->>C: requires accepted, patient informed, no open tasks
    Note over C: close-out sweep (every 60 s) asks each institution to revoke grants opened for this referral
```

## 7.10 Test and scan request

```mermaid
sequenceDiagram
    actor D as Doctor
    actor S as Staff
    participant C as Central
    participant L as Laboratory or imaging department
    D->>C: POST /referrals (kind test) and POST /referrals/{id}/diagnostics
    D->>C: POST /referrals/{id}/submit
    S->>C: POST /diagnostics/{dx}/send
    C->>C: outbox deliver_order (DiagnosticOrder with patient identity)
    C->>L: POST /inbound/orders
    L->>L: confirm the patient (match or register new)
    L->>C: events order_accepted or order_rejected (reason), order_scheduled, order_done
    L->>C: event order_reported (text, values, findings, impression, images)
    C->>C: report and attachments stored, doctor notified
    D->>C: POST /diagnostics/{dx}/seen
    D->>C: close once every result is seen (records removed 72 h later)
```

## 7.11 Account disabling and grant close-out

```mermaid
sequenceDiagram
    actor AD as Institution administrator
    participant C as Central
    participant K as Keycloak
    participant I as Institution services
    participant Wk as Worker
    AD->>C: POST /admin/users/{id}/disable (reason)
    C->>C: only an administrator of the same institution, never their own account
    C->>K: admin API: user enabled=false, then logout (ends sessions)
    C->>C: users.account_status disabled, token cache cleared, audit
    Note over C: every later request by that user gets 401 account_disabled at once, and queued jobs fail the permission re-check
    Note over K,I: introspection reports the token inactive, so every institution service refuses it within 10 s
    Wk->>C: close_referral_grants (every 60 s): referrals in closed, declined or cancelled
    Wk->>I: POST /grants/revoke-by-referral (service token)
    I->>I: revoke grants with that referral_ref, audit
    Wk->>C: grants_closed event, audit (retried next sweep on failure, expiry is the backstop)
```
