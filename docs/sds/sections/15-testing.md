# 15. Testing strategy

| Level | Location | Runs against | Command |
|---|---|---|---|
| Unit and component | `services/central/tests` | Nothing external: pure functions, fake HTTP endpoints for model and OCR providers, SQLite or in-memory where needed | `docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q` |
| Integration (API) | `tests/` | The full Compose stack after reseeding (set `SKIP_RESET=1` to keep data) | `.venv\Scripts\python -m pytest tests -q` |
| Browser end-to-end | `web/e2e/*.spec.ts` | The running stack through the web app | `cd web; npx playwright test e2e/smoke.spec.ts` |
| Type check and build | `web/` | — | `npm run typecheck; npm run build` |
| FHIR validation | `contracts/fhir-samples` | HL7 validator | `scripts/fhir-validate.ps1` |
| OCR evaluation | `evaluation/ocr` (dev and held-out sets) | Tesseract | `scripts/evaluate_ocr.py` |
| Load | — | Running stack | `scripts/loadtest.py` |
| SDS currency | `docs/sds` | The code | `python scripts/sds/build_sds.py check` |

**What the unit tests protect:**

- the evaluator's determinism and flag kinds;
- AI guardrails: selection validation, de-identification, the external-model switch, and that AI suggestions cannot change flags;
- provider request shapes and error handling (Anthropic, Ollama, OpenAI-compatible);
- the lifecycle rules for each expiry case;
- grant close-out;
- Google Vision request shape and fallback;
- DRAP register name matching.

**What the integration tests cover end to end:**

- the five synthetic patient scenarios and their expected flags;
- retrieval from every linked hospital;
- uploaded prescription merging;
- default selection against each seed's expected view;
- temporary grants, manifests, own-copy verification and purge;
- role templates;
- referral expiry at both the platform and the receiving hospital;
- DRAP brand handling.

Appendix O lists every test with its description, generated from the test files.

**Latest results** (2026-10-29, local stack):

- 136 unit tests pass, including `test_staff_view.py`: staff views carry no clinical values, consultation notes keep older package hashes, interaction label quotes.
- 21 of 22 integration tests pass. The failure is `test_admin_assigns_a_role_by_template`: Keycloak refused the role change (`502 identity_provider_refused`). The local realm was imported before the role-template change, so the `service-account-central-api` user lacks the `realm-management` role `view-realm`, which `infra/keycloak/import/referral-realm.json` now grants (Section 16).
- The web type check passes.
