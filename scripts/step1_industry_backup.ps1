Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Windows (PowerShell) for backup vnm.industry (and optional restore).
# Uses ~/.my.cnf (or %USERPROFILE%\.my.cnf) for MySQL credentials.

$DB_NAME = if ($env:DB_NAME) { $env:DB_NAME } else { "portfolio_db" }
$TABLE_NAME = if ($env:TABLE_NAME) { $env:TABLE_NAME } else { "vietnam_research_industry" }
$BACKUP_DIR = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { ".\scripts\backups" }
$MY_CNF = if ($env:MY_CNF) { $env:MY_CNF } else { ".\scripts\.my.cnf" }
$RESET_CMD = $env:RESET_CMD

if (-not (Get-Command mysqldump -ErrorAction SilentlyContinue)) {
    throw "mysqldump not found. Please check your PATH."
}
if (-not (Get-Command mysql -ErrorAction SilentlyContinue)) {
    throw "mysql not found. Please check your PATH."
}

$mysql_args = @()
if (Test-Path $MY_CNF) {
    $mysql_args += "--defaults-extra-file=$MY_CNF"
}

if (-not (Test-Path $BACKUP_DIR)) {
    New-Item -Path $BACKUP_DIR -ItemType Directory | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup_file = Join-Path $BACKUP_DIR "${DB_NAME}.${TABLE_NAME}.${timestamp}.sql"
$backup_file_abs = Resolve-Path $backup_file -ErrorAction SilentlyContinue
if ($null -eq $backup_file_abs) { $backup_file_abs = $backup_file }

Write-Host "Backup: ${DB_NAME}.${TABLE_NAME} -> ${backup_file}"
# Use --result-file to avoid encoding issues with redirection
& mysqldump @mysql_args `
  --single-transaction `
  --quick `
  --skip-lock-tables `
  --result-file="$backup_file" `
  "$DB_NAME" "$TABLE_NAME"

if ($RESET_CMD) {
    Write-Host "Executing reset command: $RESET_CMD"
    Invoke-Expression $RESET_CMD
} else {
    Write-Host "Please reset the database (e.g. migrate). Press Enter to continue restore..."
    Read-Host
}

Write-Host "Restore: ${DB_NAME}.${TABLE_NAME} <- ${backup_file}"
# Use mysql -e "source file" for restore. 
# Replace backslashes with forward slashes for MySQL source command if needed
$restore_path = $backup_file_abs.ToString().Replace('\', '/')
& mysql @mysql_args --database="$DB_NAME" -e "source $restore_path"

Write-Host "Done."
