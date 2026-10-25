#!/bin/sh
# Creates one database and one login per owner. The central application never
# receives credentials for any institution's database.
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
create_db drali_db drali "$DRALI_DB_PASSWORD"
create_db chughtai_db chughtai "$CHUGHTAI_DB_PASSWORD"
create_db ziauddin_db ziauddin "$ZIAUDDIN_DB_PASSWORD"
create_db akuh_db akuh "$AKUH_DB_PASSWORD"
create_db keycloak keycloak "$KEYCLOAK_DB_PASSWORD"
