# SDS changelog

Newest first. Each version is frozen in `versions/`.

## v2.0.0 (2026-10-30)

Architecture spec v4: end-to-end encrypted referrals. WP5 to WP11 finished on Sumaiya's WP0 to WP4: signed packages re-wrapped to the receiving department and the patient, titles-only notices, the receiving hospital's own records, the AI relay (de-identified, on request, no content logging), browser Layer 1 flags from a hash-checked bundle with Layer 2 AI suggestions and no drug-procedure table, papers read on the device, reminders and capped extensions with crypto-shredding and purge receipts, the patient's verified copy, and an append-only hash-chained audit trail. New section 18.

Structural changes found automatically:

- Table added (central): `consents`
- Table added (central): `encrypted_batches`
- Table added (central): `encrypted_items`
- Table added (central): `group_key_wraps`
- Table added (central): `key_directory`
- Table added (central): `package_manifests`
- Table added (central): `platform_keys`
- Table added (central): `purge_receipts`
- Table added (central): `record_requests`
- Table added (central): `seen_assertions`
- Table added (central): `wrapped_keys`
- Column added (central): `audit_events.chain_hash` String(64) null
- Column added (central): `audit_events.chain_seq` Integer null
- Column added (central): `audit_events.prev_hash` String(64) null
- Column added (central): `referrals.close_reminder_due_at` DateTime(timezone=True) null
- Column added (central): `referrals.escalated_at` DateTime(timezone=True) null
- Column added (central): `referrals.last_reminder_at` DateTime(timezone=True) null
- Column added (central): `referrals.reminders_sent` Integer
- Table added (institution): `doctor_keys`
- Table added (institution): `group_key_wraps`
- Table added (institution): `key_store`
- Table added (institution): `record_requests`
- Table added (institution): `seen_assertions`
- Table removed (institution): `access_grants`
- Column added (institution): `conditions.sensitive_category` String(40) null
- Column added (institution): `imaging_reports.sensitive_category` String(40) null
- Column added (institution): `lab_results.sensitive_category` String(40) null
- Column added (institution): `medications.sensitive_category` String(40) null
- Column added (institution): `visits.sensitive_category` String(40) null
- Endpoint added: `central GET /.well-known/jwks.json`
- Endpoint added: `central GET /admin/audit/chain`
- Endpoint added: `central GET /e2e/adapter/consents/{reference}`
- Endpoint added: `central GET /e2e/directory`
- Endpoint added: `central GET /e2e/directory/departments/{hospital_id}/{department}`
- Endpoint added: `central GET /e2e/directory/me`
- Endpoint added: `central GET /e2e/participants`
- Endpoint added: `central GET /e2e/received/{reference}/package`
- Endpoint added: `central GET /med-bundle`
- Endpoint added: `central GET /patient-access/consents`
- Endpoint added: `central GET /patient-access/referrals/{reference}/copy`
- Endpoint added: `central GET /referrals/{referral_id}/consents`
- Endpoint added: `central GET /referrals/{referral_id}/encrypted`
- Endpoint added: `central GET /referrals/{referral_id}/packages`
- Endpoint added: `central GET /referrals/{referral_id}/record-requests`
- Endpoint added: `central GET /referrals/{referral_id}/titles`
- Endpoint added: `central POST /ai/relay/flags`
- Endpoint added: `central POST /ai/relay/selection`
- Endpoint added: `central POST /e2e/adapter/directory`
- Endpoint added: `central POST /e2e/adapter/receiving-batches`
- Endpoint added: `central POST /e2e/adapter/record-responses`
- Endpoint added: `central POST /e2e/client-events`
- Endpoint added: `central POST /e2e/patient-keys`
- Endpoint added: `central POST /e2e/verify-manifest`
- Endpoint added: `central POST /patient-access/consents/{reference}/decision`
- Endpoint added: `central POST /patient-access/consents/{reference}/prepare`
- Endpoint added: `central POST /patient-access/consents/{reference}/revoke`
- Endpoint added: `central POST /patient-access/referrals/{reference}/papers`
- Endpoint added: `central POST /referrals/{referral_id}/consents`
- Endpoint added: `central POST /referrals/{referral_id}/encrypted-batches`
- Endpoint added: `central POST /referrals/{referral_id}/packages`
- Endpoint added: `central POST /referrals/{referral_id}/record-requests`
- Endpoint added: `institution POST /cases/{case_id}/own-records`
- Endpoint removed: `central GET /referrals/{referral_id}/brief-preview`
- Endpoint removed: `central GET /referrals/{referral_id}/packages/{version}`
- Endpoint removed: `central GET /referrals/{referral_id}/retrievals`
- Endpoint removed: `central GET /referrals/{referral_id}/selection`
- Endpoint removed: `central POST /referrals/{referral_id}/packages/{version}/verify`
- Endpoint removed: `central POST /referrals/{referral_id}/packages/{version}/verify-own-copy`
- Endpoint removed: `central POST /referrals/{referral_id}/packet-reviewed`
- Endpoint removed: `central POST /referrals/{referral_id}/prepared`
- Endpoint removed: `central POST /referrals/{referral_id}/recommend`
- Endpoint removed: `central POST /referrals/{referral_id}/retrieve`
- Endpoint removed: `institution GET /admin/grants`
- Endpoint removed: `institution POST /admin/grants`
- Endpoint removed: `institution POST /admin/grants/{grant_id}/extend`
- Endpoint removed: `institution POST /admin/grants/{grant_id}/revoke`
- Endpoint removed: `institution POST /grants/revoke-by-referral`
- Endpoint removed: `institution POST /sharing/grants`
- Setting added: `CLOSE_GRACE_DAYS='7'`
- Setting added: `DECLINE_GRACE_DAYS='1'`
- Setting added: `DOCTOR_KEY_VALID_DAYS='365'`
- Setting added: `ESCALATE_AFTER_REMINDERS='3'`
- Setting added: `HUB_URL=CENTRAL_URL`
- Setting added: `KEYSTORE_SECRET=''`
- Setting added: `MAX_REFERRAL_DAYS='180'`
- Setting added: `PARTICIPANTS_FILE='/etc/refx/participants/participants.json'`
- Setting added: `REMINDER_INTERVAL_DAYS='7'`
- Setting removed: `DEFAULT_GRANT_DAYS='14'`
- Setting removed: `MAX_GRANT_DAYS='30'`
- Background job added: `close_reminders`
- Background job added: `seal_audit`
- Background job removed: `close_referral_grants`
- Background job removed: `recommend_selection`
- Web route added: `/admin/keys`
- Web route added: `/keys`
- Web route added: `/release-requests`
- Web route removed: `/admin/access`
- Role template added: `patient`
- Access checks changed: `central POST /referrals/{referral_id}/documents`
- Access checks changed: `institution GET /admin/audit`
- Background job schedule changed
- Migration added (central): `c3e5a7b9d1f2`
- Migration added (central): `d4f6b8c0e2a3`
- Migration added (central): `e5a7c9d1f3b4`
- Migration added (central): `f6b8d0e2a4c5`
- Migration added (provider): `b2d4f6a8c0e1`
- Migration added (provider): `c4e6a8b0d2f3`
- Migration added (provider): `d5f7b9c1e3a4`
- Dependency added (`services/central/requirements.txt`): `cryptography==50.0.2`
- Dependency added (`services/provider/requirements.txt`): `cryptography==50.0.2`
- Web dependency added: `@tesseract.js-data/eng`
- Web dependency added: `tesseract.js`
- Written sections changed: 01-introduction.md, 02-system-overview.md, 03-architectural-drivers.md, 04-architecture.md, 05-data-architecture.md, 06-component-design.md, 07-workflows.md, 08-security.md, 09-ai-design.md, 10-medication-flagging.md, 11-interfaces.md, 12-reliability.md, 13-quality-attributes.md, 14-deployment-operations.md, 15-testing.md, 16-limitations-and-risks.md, 17-maintaining-this-document.md, 18-architecture-spec-v4.md

## v1.3.0 (2026-10-29)

AI packet selection runs on Groq (openai/gpt-oss-120b): LLM_REASONING_EFFORT setting, LLM_BASE_URL/LLM_API_KEY passed to the containers, wider action-word check with advice reasons withheld per record (prompt packet-selection/4)

Structural changes found automatically:

- Setting added: `LLM_REASONING_EFFORT=''`
- Written sections changed: 01-introduction.md, 02-system-overview.md, 03-architectural-drivers.md, 04-architecture.md, 05-data-architecture.md, 06-component-design.md, 07-workflows.md, 08-security.md, 09-ai-design.md, 10-medication-flagging.md, 11-interfaces.md, 12-reliability.md, 13-quality-attributes.md, 14-deployment-operations.md, 15-testing.md, 16-limitations-and-risks.md, 17-maintaining-this-document.md

## v1.2.0 (2026-10-29)

Patient accounts and patient view: own referrals from the platform, own records read directly from each institution

Structural changes found automatically:

- Endpoint added: `central GET /patient-access/places`
- Endpoint added: `central GET /patient-access/referrals`
- Endpoint added: `institution GET /patient-access/records`
- Endpoint added: `institution GET /patient-access/summary`
- Realm role added: `patient`
- Decision record added: `[2026-10-29-patient-view](../decisions/2026-10-29-patient-view.md)`
- Written sections changed: 01-introduction.md, 02-system-overview.md, 03-architectural-drivers.md, 04-architecture.md, 05-data-architecture.md, 06-component-design.md, 07-workflows.md, 08-security.md, 09-ai-design.md, 10-medication-flagging.md, 11-interfaces.md, 12-reliability.md, 13-quality-attributes.md, 14-deployment-operations.md, 15-testing.md, 16-limitations-and-risks.md, 17-maintaining-this-document.md

## v1.1.0 (2026-10-29)

Only doctors see clinical content and the doctor reviews the referral packet before staff send (both institutions); consultation notes under the reason; drug-interaction flags quote the US drug label sentence when one exists; realistic seed visit wording.

Structural changes found automatically:

- Column added (central): `drug_interactions.label_quote` Text null
- Column added (central): `drug_interactions.label_section` String(60) null
- Column added (central): `drug_interactions.label_source` String(200) null
- Column added (central): `referrals.consultation_notes` Text
- Column added (central): `referrals.packet_reviewed_at` DateTime(timezone=True) null
- Column added (central): `referrals.packet_reviewed_by` String(200) null
- Endpoint added: `central POST /referrals/{referral_id}/packet-reviewed`
- Decision record added: `[2026-10-29-doctor-only-clinical-content](../decisions/2026-10-29-doctor-only-clinical-content.md)`
- Access checks changed: `central POST /referrals/{referral_id}/evidence/manual`
- Access checks changed: `central POST /referrals/{referral_id}/medications/checked`
- Access checks changed: `central POST /referrals/{referral_id}/medications/manual`
- Access checks changed: `central POST /referrals/{referral_id}/medications/{entry_id}/exclude`
- Access checks changed: `central POST /referrals/{referral_id}/medications/{entry_id}/mapping`
- Access checks changed: `central POST /referrals/{referral_id}/medications/{entry_id}/restore`
- Access checks changed: `institution GET /cases/{case_id}`
- Access checks changed: `institution GET /outbound-copies`
- Migration added (central): `a1c3e5f7b9d2`
- Written sections changed: 01-introduction.md, 02-system-overview.md, 03-architectural-drivers.md, 04-architecture.md, 05-data-architecture.md, 06-component-design.md, 07-workflows.md, 08-security.md, 09-ai-design.md, 10-medication-flagging.md, 11-interfaces.md, 12-reliability.md, 13-quality-attributes.md, 14-deployment-operations.md, 15-testing.md, 16-limitations-and-risks.md, 17-maintaining-this-document.md

## v1.0.1 (2026-10-29)

Docker Compose inventory now included in Appendix J (it was skipped in v1.0.0 because PyYAML was not visible to the generator); PyYAML is now required and Compose's own YAML tags are accepted.

Structural changes found automatically:

- Compose service added (`docker-compose.dbaccess.yml`): `postgres`
- Compose service added (`docker-compose.prod.yml`): `akuh`
- Compose service added (`docker-compose.prod.yml`): `caddy`
- Compose service added (`docker-compose.prod.yml`): `central`
- Compose service added (`docker-compose.prod.yml`): `chughtai`
- Compose service added (`docker-compose.prod.yml`): `drali`
- Compose service added (`docker-compose.prod.yml`): `keycloak`
- Compose service added (`docker-compose.prod.yml`): `postgres`
- Compose service added (`docker-compose.prod.yml`): `web`
- Compose service added (`docker-compose.prod.yml`): `worker`
- Compose service added (`docker-compose.prod.yml`): `ziauddin`
- Compose service added (`docker-compose.yml`): `akuh`
- Compose service added (`docker-compose.yml`): `central`
- Compose service added (`docker-compose.yml`): `chughtai`
- Compose service added (`docker-compose.yml`): `drali`
- Compose service added (`docker-compose.yml`): `keycloak`
- Compose service added (`docker-compose.yml`): `postgres`
- Compose service added (`docker-compose.yml`): `redis`
- Compose service added (`docker-compose.yml`): `web`
- Compose service added (`docker-compose.yml`): `worker`
- Compose service added (`docker-compose.yml`): `ziauddin`

## v1.0.0 (2026-10-29)

First complete Software Design Specification of the v2 code base: architecture, components, data model, workflows, security, AI, medication flagging, interfaces, reliability, operations, testing and limitations, with generated ERDs, API, contracts, configuration and inventories.

Structural changes found automatically:

- First release: the whole system is described.
