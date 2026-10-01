#!/bin/sh
# Creates one database and one login per owner. The central application never
# receives credentials for the clinic, lab, or specialist databases.
set -eu

create_db() {
  db="$1"; user="$2"; pass="$3"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE USER "$user" WITH PASSWORD '$pass';
    CREATE DATABASE "$db" OWNER "$user";
    REVOKE ALL ON DATABASE "$db" FROM PUBLIC;
EOSQL
}

create_db central_db central "$CENTRAL_DB_PASSWORD"
create_db clinic_db clinic "$CLINIC_DB_PASSWORD"
create_db lab_db lab "$LAB_DB_PASSWORD"
create_db specialist_db specialist "$SPECIALIST_DB_PASSWORD"
create_db keycloak keycloak "$KEYCLOAK_DB_PASSWORD"
