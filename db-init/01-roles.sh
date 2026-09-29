#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_password="$DATATALK_APP_PASSWORD" \
  -v reader_password="$DATATALK_READER_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE datatalk_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'datatalk_app') \gexec
SELECT format('CREATE ROLE datatalk_reader LOGIN PASSWORD %L', :'reader_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'datatalk_reader') \gexec
ALTER ROLE datatalk_reader SET default_transaction_read_only = on;
ALTER ROLE datatalk_reader SET statement_timeout = '4s';
ALTER ROLE datatalk_reader SET idle_in_transaction_session_timeout = '8s';
GRANT CONNECT ON DATABASE datatalk TO datatalk_app, datatalk_reader;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
