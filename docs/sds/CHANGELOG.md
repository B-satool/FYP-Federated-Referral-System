# SDS changelog

Newest first. Each version is frozen in `versions/`.

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
