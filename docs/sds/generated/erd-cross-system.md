## References across system boundaries

These identifiers point into another service's database. They are never joined: each service owns its database, and the values travel only in authenticated API calls (AGENTS.md invariant 1).

| Held in | Column | Points to | Target | How it is set |
|---|---|---|---|---|
| institution | `cases.central_referral_id` | central | `referrals.reference` | set from the package envelope |
| institution | `cases.link_request_id` | central | `patient_links.id` | intake link request for the arriving patient |
| institution | `orders.central_referral_id` | central | `referrals.reference` | set from the diagnostic order |
| institution | `orders.order_ref` | central | `diagnostic_requests.reference` | the order reference |
| institution | `orders.link_request_id` | central | `patient_links.id` | intake link request |
| institution | `sent_copies.central_referral_id` | central | `referrals.reference` | the sender's own copy |
| institution | `access_grants.referral_ref` | central | `referrals.reference` | grant opened for a referral |
| central | `referrals.patient_local_id` | institution | `patients.local_id` | the referring institution's record |
| central | `patient_links.requester_local_id / target_local_id` | institution | `patients.local_id` | confirmed by the target institution's staff |
| central | `evidence_items.source_record_id + version` | institution | `conditions / visits / medications / lab_results / imaging_reports .id` | FHIR resource id and version |
| central | `users.id` | keycloak | `user subject (sub)` | Keycloak is the account authority |
