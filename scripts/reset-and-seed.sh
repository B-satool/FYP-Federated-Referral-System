#!/bin/sh
# Reset every owner's database to the deterministic synthetic seed. Requires --force.
set -eu
if [ "${1:-}" != "--force" ]; then
  echo "This wipes ALL demo data. Re-run with --force." >&2
  exit 1
fi
for svc in clinic lab specialist central; do
  echo "Seeding $svc ..."
  docker compose exec -T "$svc" python -m app.seed --reset --yes
done
echo "Done. Seed version: synthetic-seed/1.0"
