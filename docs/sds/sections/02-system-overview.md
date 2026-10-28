# 2. System overview

## 2.1 Context

Patients in Karachi are commonly treated at several unconnected places: a neighbourhood clinic, one or more hospitals, and a private laboratory. When a doctor refers a patient, the receiving specialist usually sees a short handwritten note. The patient's history at the other places, the current medicines and the results are missing. This platform assembles that information from the institutions that hold it, with each institution keeping control of its own records, and delivers it as a checked, versioned referral.

```mermaid
flowchart LR
    subgraph People
        D["Referring doctor"]
        S["Referring staff"]
        RD["Receiving doctor"]
        RS["Receiving staff"]
        DX["Laboratory / imaging staff"]
        AD["Institution administrator"]
        CR["Clinical rule reviewer"]
    end
    W["Web application (browser)"]
    C["Central referral platform"]
    I1["Dr Ali's Clinic system"]
    I2["Ziauddin Hospital system"]
    I3["AKUH system"]
    I4["Chughtai Lab system"]
    KC["Keycloak (identity provider)"]
    LLM["Language model (optional): Ollama local or cloud, Anthropic, OpenAI-compatible"]
    OCR["Google Cloud Vision (optional, handwriting)"]

    People --> W
    W -->|"OIDC sign-in"| KC
    W -->|"REST, user token"| C
    W -->|"REST, user token (own institution's system)"| I1 & I2 & I3 & I4
    C -->|"REST, forwarded user token or service token"| I1 & I2 & I3 & I4
    I1 & I2 & I3 & I4 -->|"events, service token"| C
    C -->|"de-identified text, only if allowed"| LLM
    C -->|"page images, only if configured"| OCR
    C & I1 & I2 & I3 & I4 -->|"token verification, introspection"| KC
```

## 2.2 Actors and roles

| Actor | Realm role | What they do |
|---|---|---|
| Doctor | `clinician` | Requests referrals and test requests, reviews medication flags, receives referrals for their department, accepts or declines them, marks them complete, extends the records hold |
| Staff (referral coordinator) | `clinic_staff` | Requests and approves patient links, retrieves records, checks uploaded papers, confirms medicines (including over-the-counter), marks a referral ready, sends it, takes in incoming referrals and assigns a doctor, records that the patient was told, closes referrals |
| Laboratory, radiology or ECG staff | `diagnostics_staff` | Confirms arriving patients, accepts or rejects orders, schedules them, reports results with images |
| Institution administrator | `institution_admin` | Accounts and role templates, source access grants and their expiry, audit log. No clinical record access |
| Clinical rule reviewer | `rule_reviewer` | Approves medication rule versions and medicine names; sees the imported interaction data, label rules and AI model figures |
| Central platform service | `svc_central` | Machine identity: delivers packages, orders and copies; closes grants |
| Institution service | `svc_provider` | Machine identity: sends acknowledgement, decision, completion and order events to the platform |

A user's institution is their top-level Keycloak group, and their department is the subgroup (Appendix K).

## 2.3 Main capabilities

| Capability | Where it is built |
|---|---|
| Referral and test requests, status and timeline | `central/app/referrals`, `diagnostics` |
| Patient linking confirmed by the other institution | `central/app/identity`, institution `/identity/*`, `/sharing/grants` |
| Retrieval of history from every linked institution | `central/app/integration` |
| Uploaded papers: OCR and field extraction | `central/app/documents` |
| Evidence review: verify, correct, exclude, manual entry | `central/app/evidence_router.py` |
| Current-medicine list, name mapping (incl. DRAP brands) | `central/app/medications/service.py`, `mapping.py` |
| Deterministic medication flags | `central/app/medications/evaluator.py` |
| Packet selection (default, AI, staff) | `central/app/selection` |
| Referral letter (brief), package, hash, delivery | `central/app/sending`, `delivery` |
| Receiving side: intake, assignment, decision, completion | institution service `/cases/*` |
| Test and scan orders and reports | `central/app/diagnostics`, institution `/orders/*` |
| Follow-through: patient informed, tasks, closure | `central/app/followup` |
| Temporary working set and grant close-out | `central/app/lifecycle`, `integration/grant_closeout.py`, `tasks.py` |
| Notifications and work queue | `central/app/notifications.py`, `workqueue.py` |
| Audit | every service (`audit_events`) |

## 2.4 End-to-end flow (referral)

```mermaid
flowchart TD
    A["Doctor creates a referral (draft), states reason, destination, urgency, procedure"] --> B["Doctor submits the request (requested)"]
    B --> C["Staff request patient links to places the patient has been"]
    C --> D["Other institution's staff confirm the patient: link verified, grant created"]
    D --> E["Staff retrieve records from every linked institution (up to 5)"]
    E --> F["Rule-based default selection, then optional AI recommendation"]
    B --> G["Staff upload the patient's papers: OCR, fields proposed, staff verify"]
    E & G --> H["Current-medicine list built, duplicates grouped, names mapped"]
    H --> I["Deterministic evaluator raises medication flags"]
    I --> J["Staff confirm medicines checked with the patient, mark ready"]
    J --> K["Doctor reviews each flag: reviewed / ignore / research"]
    K --> L["Staff send: brief built, package hashed, outbox written (submitted)"]
    L --> M["Receiving hospital: staff acknowledge, confirm the patient, assign a doctor"]
    M --> N{"Receiving doctor decides"}
    N -->|"accept"| O["accepted: records kept 30 days, extendable"]
    N -->|"decline (with reason)"| P["declined: shared records removed at once, referring side notified"]
    O --> Q["Referring staff tell the patient, optional tasks, close"]
    O --> R["Receiving doctor marks complete: records removed 72 h later"]
```

Test requests follow a shorter path: the doctor lists the tests, staff send each one as its own order, and the laboratory or imaging department accepts, schedules, performs and reports it. Results return to the referral (Section 7.10).
