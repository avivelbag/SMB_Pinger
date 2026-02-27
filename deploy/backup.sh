#!/usr/bin/env bash
# SMB Pinger — SQLite Backup Script
# Run daily via cron: 0 3 * * * /usr/local/bin/smb-pinger-backup

set -euo pipefail

DB_PATH="/var/lib/smb-pinger/smb_pinger.db"
BACKUP_DIR="/var/lib/smb-pinger/backups"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/smb_pinger_${TIMESTAMP}.db"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Checkpoint WAL to ensure all data is in the main database file
sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint(TRUNCATE);"

# Create backup using SQLite's .backup command (safe, consistent)
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

# Compress the backup
gzip "$BACKUP_FILE"

# Verify backup integrity
gunzip -c "${BACKUP_FILE}.gz" | sqlite3 ":memory:" "PRAGMA integrity_check;" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: Backup integrity check failed for ${BACKUP_FILE}.gz" >&2
    exit 1
fi

# Remove backups older than retention period
find "$BACKUP_DIR" -name "smb_pinger_*.db.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup complete: ${BACKUP_FILE}.gz ($(du -h "${BACKUP_FILE}.gz" | cut -f1))"
