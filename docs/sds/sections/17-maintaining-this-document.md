# 17. Maintaining this document

## 17.1 Rule

**Every change to the system produces a new version of this SDS.** A change is anything that alters:

- the database schema;
- an endpoint or its access checks;
- a setting;
- a background job or its schedule;
- the state machine;
- a web route, role or role template;
- a migration or a dependency;
- a decision record;
- the written sections.

CI enforces this: the `sds` job runs `build_sds.py check`, which fails when the generated appendices or `SDS.md` are stale, or when the structure or written sections changed since the last released version. `check --strict` also fails on any source-file change.

## 17.2 Procedure for a change

1. Make the code change.
2. If behaviour, design or reasoning changed, edit the matching written section in `docs/sds/sections/`. For a significant decision, also add a record in `docs/decisions/`.
3. Release a new version:

   ```
   python scripts/sds/build_sds.py release --level minor --summary "Retrieval reads every linked institution"
   ```

   The level follows semantic versioning:
   - `major`: a new architecture or a breaking contract;
   - `minor`: new or changed capabilities, tables, endpoints or settings;
   - `patch`: corrections to the text only.
4. Commit `docs/sds/` together with the code change.

`release` does five things:

- regenerates the appendices;
- computes the structural differences from the previous version (tables, columns, endpoints, access checks, settings, jobs, routes, roles, migrations, dependencies, decisions);
- bumps the version;
- freezes the full document as `docs/sds/versions/SDS-v<version>.md`;
- adds a `CHANGELOG.md` entry with your summary and the detected changes.

Other commands:

| Command | Use |
|---|---|
| `build_sds.py build` | Regenerate the appendices and `SDS.md` while working (the header says "Working draft after vX") |
| `build_sds.py diff` | Show what changed structurally since the last release |
| `build_sds.py check [--strict]` | What CI runs |

## 17.3 Files

| Path | Content |
|---|---|
| `docs/sds/SDS.md` | The current document: written sections plus generated appendices |
| `docs/sds/sections/*.md` | Written sections (edit these) |
| `docs/sds/generated/*.md` | Generated appendices (never edit by hand) |
| `docs/sds/versions/SDS-v*.md` | Frozen released versions |
| `docs/sds/CHANGELOG.md` | Version history with detected structural changes |
| `docs/sds/manifest.json` | Current version, release date, fingerprints and the structural inventory of the released version |
| `scripts/sds/build_sds.py` | The generator (static analysis: no running services needed) |

## 17.4 How the generator reads the code

- **ERDs and data dictionary:** SQLAlchemy model classes (`mapped_column`, `ForeignKey`, `UniqueConstraint`, mixins, column comments).
- **API inventory:** FastAPI decorators and router prefixes. Access checks are the authorisation calls in each handler, following helpers in the same module up to two levels.
- **Contracts and request bodies:** pydantic models.
- **Configuration:** environment reads in the Python code, plus the Compose files and `.env.example` (secret values never shown).
- **State machine:** `TRANSITIONS` in `referrals/state.py`.
- **Jobs:** the Celery beat schedule and task decorators.
- **Web, roles and identity:** `App.tsx`, `rules/roles/templates.v1.json` and the Keycloak realm export (no credentials).
- **Migrations, dependencies, rule data, tests and decisions:** their files.

When a new kind of structure is added (for example a new service), extend `build_sds.py` so the appendices cover it, then release a new major or minor version.
