#!/bin/sh
set -eu
umask 077
mkdir -p backups
backup_file="backups/neighborhub-$(date +%Y%m%d-%H%M%S).dump"
docker compose exec -T postgres pg_dump -U neighbor -d neighborhub -Fc > "$backup_file"
printf 'Private PostgreSQL backup written to %s\n' "$backup_file"
