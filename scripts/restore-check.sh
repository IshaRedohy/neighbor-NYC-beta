#!/bin/sh
# Demonstrate pg_dump/pg_restore on isolated synthetic data; never target the app DB.
set -eu
mkdir -p .artifacts
umask 077
docker compose -f compose.test.yaml exec -T postgres pg_dump -U neighbor -d neighborhub_test -Fc > .artifacts/restore-check.dump
docker compose -f compose.test.yaml exec -T postgres dropdb -U neighbor --if-exists neighborhub_restore_test
docker compose -f compose.test.yaml exec -T postgres createdb -U neighbor neighborhub_restore_test
docker compose -f compose.test.yaml exec -T postgres pg_restore -U neighbor -d neighborhub_restore_test --no-owner --no-acl --exit-on-error < .artifacts/restore-check.dump
docker compose -f compose.test.yaml exec -T postgres psql -U neighbor -d neighborhub_restore_test -v ON_ERROR_STOP=1 -c 'SELECT count(*) AS restored_members FROM members; SELECT count(*) AS restored_messages FROM messages;'
fingerprint_sql="SELECT md5(COALESCE(string_agg(row_to_json(m)::text, ',' ORDER BY id),'')) FROM members m; SELECT md5(COALESCE(string_agg(row_to_json(m)::text, ',' ORDER BY id),'')) FROM messages m;"
source_fingerprint=$(docker compose -f compose.test.yaml exec -T postgres psql -U neighbor -d neighborhub_test -At -c "$fingerprint_sql")
restored_fingerprint=$(docker compose -f compose.test.yaml exec -T postgres psql -U neighbor -d neighborhub_restore_test -At -c "$fingerprint_sql")
test "$source_fingerprint" = "$restored_fingerprint"
printf 'Member and message fingerprints match the source.\n'
