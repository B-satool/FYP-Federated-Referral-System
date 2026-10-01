"""Create the four application databases on a hosted PostgreSQL server (e.g. Neon) for the team.

Each database gets its own login with a strong random password (same ownership model as local).
Writes:
  * .env                      - adds/updates CLINIC_/LAB_/SPECIALIST_/CENTRAL_DATABASE_URL
  * shared-db-credentials.md  - connection details to share privately with teammates (git-ignored)

Run (inside the central image, which has psycopg):
  docker compose run --rm --no-deps -v ${PWD}:/repo central python /repo/scripts/setup_shared_db.py "postgresql://ADMIN:PASS@HOST/neondb?sslmode=require"
Use the DIRECT (non "-pooler") host from Neon; CREATE DATABASE does not work through a pooler.
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg

REPO = Path("/repo")
OWNERS = ["central", "clinic", "lab", "specialist"]
PREFIX = "ref_"  # avoid clashing with any existing roles on the hosted server


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    admin_url = sys.argv[1].replace("postgresql+psycopg://", "postgresql://")
    u = urlparse(admin_url)
    host, port = u.hostname, u.port or 5432
    query = u.query or "sslmode=require"
    creds: dict[str, tuple[str, str, str]] = {}
    with psycopg.connect(admin_url, autocommit=True) as conn:
        for owner in OWNERS:
            role, db, pw = f"{PREFIX}{owner}", f"{owner}_db", secrets.token_urlsafe(24)
            exists = conn.execute("select 1 from pg_roles where rolname=%s", (role,)).fetchone()
            if exists:
                conn.execute(f"ALTER ROLE \"{role}\" WITH LOGIN PASSWORD '{pw}'")  # token_urlsafe: no quotes
            else:
                conn.execute(f"CREATE ROLE \"{role}\" WITH LOGIN PASSWORD '{pw}'")
            conn.execute(f'GRANT "{role}" TO CURRENT_USER')
            if not conn.execute("select 1 from pg_database where datname=%s", (db,)).fetchone():
                conn.execute(f'CREATE DATABASE "{db}" OWNER "{role}"')
            conn.execute(f'REVOKE ALL ON DATABASE "{db}" FROM PUBLIC')
            creds[owner] = (role, db, pw)
            print(f"ready: database {db} owned by {role}")

    env_lines = {f"{o.upper()}_DATABASE_URL": f"postgresql+psycopg://{r}:{p}@{host}:{port}/{d}?{query}"
                 for o, (r, d, p) in creds.items()}
    env_path = REPO / ".env"
    lines = [ln for ln in env_path.read_text().splitlines() if ln.split("=", 1)[0] not in env_lines]
    lines += ["", "# Shared hosted database (written by scripts/setup_shared_db.py)"]
    lines += [f"{k}={v}" for k, v in env_lines.items()]
    env_path.write_text("\n".join(lines) + "\n")

    sheet = ["# Shared database credentials (PRIVATE - share only with the team, never commit)", "",
             f"Host: `{host}`  Port: `{port}`  SSL: required", "",
             "| Database | Username | Password | Owned by |", "|---|---|---|---|"]
    for o, (r, d, p) in creds.items():
        sheet.append(f"| `{d}` | `{r}` | `{p}` | {o} service |")
    sheet += ["", "## For teammates running the app", "Add these lines to your `.env`, then `docker compose up -d`:", "", "```"]
    sheet += [f"{k}={v}" for k, v in env_lines.items()]
    sheet += ["```", "", "Do NOT run `scripts/reset-and-seed.ps1` on the shared database without agreeing with the team: it wipes everyone's data.",
              "Uploaded document files stay on the computer that uploaded them; other teammates see their metadata but not the file."]
    (REPO / "shared-db-credentials.md").write_text("\n".join(sheet) + "\n")
    print("wrote .env database URLs and shared-db-credentials.md")


if __name__ == "__main__":
    main()
