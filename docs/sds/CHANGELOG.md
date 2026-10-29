# SDS changelog

Newest first. Each version is frozen in `versions/`.

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
