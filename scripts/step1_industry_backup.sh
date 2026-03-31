#!/usr/bin/env bash
set -euo pipefail

# Linux用: vnm.industry をバックアップ（任意で復元も可能）。
# 認証は ~/.my.cnf などの MySQL 設定を利用する前提。

DB_NAME="${DB_NAME:-portfolio_db}"
TABLE_NAME="${TABLE_NAME:-vietnam_research_industry}"
BACKUP_DIR="${BACKUP_DIR:-./scripts/backups}"
MY_CNF="${MY_CNF:-./scripts/.my.cnf}"
RESET_CMD="${RESET_CMD:-}"

if ! command -v mysqldump >/dev/null 2>&1; then
  echo "mysqldump が見つかりません。" >&2
  exit 1
fi
if ! command -v mysql >/dev/null 2>&1; then
  echo "mysql が見つかりません。" >&2
  exit 1
fi

mysql_args=()
if [[ -f "$MY_CNF" ]]; then
  mysql_args+=( "--defaults-extra-file=$MY_CNF" )
fi

mkdir -p "$BACKUP_DIR"

timestamp="$(date +"%Y%m%d_%H%M%S")"
backup_file="${BACKUP_DIR}/${DB_NAME}.${TABLE_NAME}.${timestamp}.sql"

echo "Backup: ${DB_NAME}.${TABLE_NAME} -> ${backup_file}"
mysqldump \
  "${mysql_args[@]}" \
  --single-transaction \
  --quick \
  --skip-lock-tables \
  "$DB_NAME" "$TABLE_NAME" > "$backup_file"

if [[ -n "$RESET_CMD" ]]; then
  echo "Reset command: $RESET_CMD"
  bash -c "$RESET_CMD"
else
  echo "DBリセットを実行してください。完了したら Enter で復元を開始します。"
  read -r
fi

echo "Restore: ${DB_NAME}.${TABLE_NAME} <- ${backup_file}"
mysql "${mysql_args[@]}" --database="$DB_NAME" < "$backup_file"

echo "Done."
