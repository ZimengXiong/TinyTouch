#!/bin/sh
set -eu
umask 077

container=tinytouch-api
backup_dir=/srv/backups/tinytouch
repository=zimengxiong/alpacaengineer-backups
stamp=$(date -u +%Y-%m-%dT%H-%M-%SZ)
backup_name="tinytouch-$stamp.db"
backup_path="$backup_dir/$backup_name"
partial_path="$backup_path.partial"
checksum_path="$backup_path.sha256"

mkdir -p "$backup_dir"
exec 9>"$backup_dir/.backup.lock"
flock -n 9
trap 'rm -f "$partial_path"' EXIT

docker exec "$container" python -c "import sqlite3; s=sqlite3.connect('/data/tinytouch.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d); d.close(); s.close()"
docker cp "$container:/data/backup.db" "$partial_path"
mv "$partial_path" "$backup_path"
test "$(sqlite3 -readonly "$backup_path" 'PRAGMA integrity_check;')" = ok
(
  cd "$backup_dir"
  sha256sum "$backup_name" >"$backup_name.sha256"
)

gh release create "backup-$stamp" "$backup_path" "$checksum_path" \
  --repo "$repository" \
  --title "TinyTouch backup $stamp" \
  --notes "Automated SQLite backup."

find "$backup_dir" -maxdepth 1 -type f -name 'tinytouch-*.db*' -mtime +30 -delete
trap - EXIT
