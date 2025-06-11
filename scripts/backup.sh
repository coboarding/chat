#!/bin/bash
# scripts/backup.sh
# Comprehensive backup script for coBoarding platform

set -euo pipefail

# Configuration
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7
LOG_FILE="/var/log/coboarding_backup.log"

# Database configuration
DB_HOST="postgres"
DB_PORT="5432"
DB_NAME="coboarding"
DB_USER="coboarding"
DB_PASSWORD="secure_password_123"

# Redis configuration
REDIS_HOST="redis"
REDIS_PORT="6379"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Create backup directory
create_backup_dir() {
    local backup_path="$BACKUP_DIR/$DATE"
    mkdir -p "$backup_path"/{database,redis,uploads,config,logs}
    echo "$backup_path"
}

# Database backup
backup_database() {
    local backup_path="$1"
    log "Starting database backup..."

    # PostgreSQL dump
    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose \
        --clean \
        --if-exists \
        --format=custom \
        --no-owner \
        --no-privileges \
        > "$backup_path/database/coboarding_${DATE}.dump"

    if [ $? -eq 0 ]; then
        success "Database backup completed"

        # Compress the backup
        gzip "$backup_path/database/coboarding_${DATE}.dump"
        success "Database backup compressed"

        # Verify backup integrity
        if gunzip -t "$backup_path/database/coboarding_${DATE}.dump.gz" 2>/dev/null; then
            success "Database backup integrity verified"
        else
            error "Database backup integrity check failed"
            return 1
        fi
    else
        error "Database backup failed"
        return 1
    fi
}

# Redis backup
backup_redis() {
    local backup_path="$1"
    log "Starting Redis backup..."

    # Use redis-cli to save and copy RDB file
    docker exec coboarding_redis redis-cli BGSAVE

    # Wait for background save to complete
    while [ "$(docker exec coboarding_redis redis-cli LASTSAVE)" == "$(docker exec coboarding_redis redis-cli LASTSAVE)" ]; do
        sleep 1
    done

    # Copy RDB file
    docker cp coboarding_redis:/data/dump.rdb "$backup_path/redis/dump_${DATE}.rdb"

    if [ $? -eq 0 ]; then
        success "Redis backup completed"
        gzip "$backup_path/redis/dump_${DATE}.rdb"
        success "Redis backup compressed"
    else
        error "Redis backup failed"
        return 1
    fi
}

# File uploads backup
backup_uploads() {
    local backup_path="$1"
    log "Starting uploads backup..."

    if [ -d "./uploads" ] && [ "$(ls -A ./uploads 2>/dev/null)" ]; then
        tar -czf "$backup_path/uploads/uploads_${DATE}.tar.gz" -C . uploads/

        if [ $? -eq 0 ]; then
            success "Uploads backup completed"
        else
            error "Uploads backup failed"
            return 1
        fi
    else
        warning "No uploads directory found or empty, skipping"
    fi
}

# Configuration backup
backup_config() {
    local backup_path="$1"
    log "Starting configuration backup..."

    # Backup configuration files (excluding sensitive data)
    tar -czf "$backup_path/config/config_${DATE}.tar.gz" \
        --exclude="*.key" \
        --exclude="*.pem" \
        --exclude=".env" \
        docker-compose.yml \
        nginx/ \
        monitoring/ \
        scripts/ \
        data/job_listings.json \
        templates/ 2>/dev/null || true

    if [ $? -eq 0 ]; then
        success "Configuration backup completed"
    else
        warning "Some configuration files may be missing"
    fi
}

# Logs backup
backup_logs() {
    local backup_path="$1"
    log "Starting logs backup..."

    if [ -d "./logs" ] && [ "$(ls -A ./logs 2>/dev/null)" ]; then
        # Only backup logs from last 7 days to save space
        find ./logs -name "*.log" -mtime -7 -print0 | \
        tar -czf "$backup_path/logs/logs_${DATE}.tar.gz" --null -T -

        if [ $? -eq 0 ]; then
            success "Logs backup completed"
        else
            warning "Logs backup had issues"
        fi
    else
        warning "No logs directory found, skipping"
    fi
}

# Create backup metadata
create_metadata() {
    local backup_path="$1"
    log "Creating backup metadata..."

    cat > "$backup_path/backup_info.json" << EOF
{
    "backup_date": "$DATE",
    "platform_version": "1.0.0",
    "backup_type": "full",
    "components": [
        "database",
        "redis",
        "uploads",
        "config",
        "logs"
    ],
    "retention_policy": "${RETENTION_DAYS} days",
    "created_by": "automated_backup",
    "backup_size": "$(du -sh $backup_path | cut -f1)",
    "database_version": "$(docker exec coboarding_postgres psql -U $DB_USER -d $DB_NAME -t -c 'SELECT version();' | head -1 | xargs)",
    "redis_version": "$(docker exec coboarding_redis redis-cli INFO server | grep redis_version | cut -d: -f2 | tr -d '\r')"
}
EOF

    success "Backup metadata created"
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up old backups (older than $RETENTION_DAYS days)..."

    find "$BACKUP_DIR" -type d -name "20*" -mtime +$RETENTION_DAYS -exec rm -rf {} + 2>/dev/null || true

    local remaining_backups=$(find "$BACKUP_DIR" -type d -name "20*" | wc -l)
    success "Cleanup completed. $remaining_backups backups remaining"
}

# Verify backup completeness
verify_backup() {
    local backup_path="$1"
    log "Verifying backup completeness..."

    local errors=0

    # Check database backup
    if [ ! -f "$backup_path/database/coboarding_${DATE}.dump.gz" ]; then
        error "Database backup file missing"
        ((errors++))
    fi

    # Check Redis backup
    if [ ! -f "$backup_path/redis/dump_${DATE}.rdb.gz" ]; then
        error "Redis backup file missing"
        ((errors++))
    fi

    # Check metadata
    if [ ! -f "$backup_path/backup_info.json" ]; then
        error "Backup metadata missing"
        ((errors++))
    fi

    if [ $errors -eq 0 ]; then
        success "Backup verification passed"
        return 0
    else
        error "Backup verification failed with $errors errors"
        return 1
    fi
}

# Send notification (optional)
send_notification() {
    local status="$1"
    local backup_path="$2"

    if [ "$status" == "success" ]; then
        local backup_size=$(du -sh "$backup_path" | cut -f1)
        log "Backup completed successfully. Size: $backup_size"

        # Send success notification (implement webhook/email as needed)
        # curl -X POST "$WEBHOOK_URL" -d "Backup completed successfully. Size: $backup_size"
    else
        log "Backup failed"

        # Send failure notification
        # curl -X POST "$WEBHOOK_URL" -d "Backup failed. Check logs for details."
    fi
}

# Main backup function
main() {
    log "=== Starting coBoarding Platform Backup ==="

    # Check if Docker containers are running
    if ! docker ps | grep -q coboarding; then
        error "coBoarding containers are not running"
        exit 1
    fi

    # Create backup directory
    local backup_path
    backup_path=$(create_backup_dir)
    log "Backup location: $backup_path"

    # Perform backups
    local backup_success=true

    backup_database "$backup_path" || backup_success=false
    backup_redis "$backup_path" || backup_success=false
    backup_uploads "$backup_path" || backup_success=false
    backup_config "$backup_path" || backup_success=false
    backup_logs "$backup_path" || backup_success=false

    # Create metadata
    create_metadata "$backup_path"

    # Verify backup
    if ! verify_backup "$backup_path"; then
        backup_success=false
    fi

    # Cleanup old backups
    cleanup_old_backups

    # Send notification
    if [ "$backup_success" = true ]; then
        send_notification "success" "$backup_path"
        success "=== Backup completed successfully ==="
        exit 0
    else
        send_notification "failure" "$backup_path"
        error "=== Backup completed with errors ==="
        exit 1
    fi
}

# Script execution
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi

###########################################
# scripts/restore.sh
# Restore script for coBoarding platform
###########################################

#!/bin/bash
# scripts/restore.sh

set -euo pipefail

# Configuration
BACKUP_DIR="/backups"
LOG_FILE="/var/log/coboarding_restore.log"

# Database configuration
DB_HOST="postgres"
DB_PORT="5432"
DB_NAME="coboarding"
DB_USER="coboarding"
DB_PASSWORD="secure_password_123"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }
error() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"; }
info() { echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"; }

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS] BACKUP_DATE

Restore coBoarding platform from backup

OPTIONS:
    -h, --help          Show this help message
    -d, --database      Restore database only
    -r, --redis         Restore Redis only
    -u, --uploads       Restore uploads only
    -c, --config        Restore configuration only
    -f, --full          Restore everything (default)
    --dry-run          Show what would be restored without actually doing it
    --force            Skip confirmation prompts

BACKUP_DATE: Format YYYYMMDD_HHMMSS (e.g., 20241201_143022)

Examples:
    $0 20241201_143022                    # Full restore
    $0 -d 20241201_143022                 # Database only
    $0 --dry-run 20241201_143022          # Preview restore
    $0 --force -f 20241201_143022         # Full restore without prompts

EOF
}

# Parse command line arguments
parse_arguments() {
    RESTORE_DATABASE=false
    RESTORE_REDIS=false
    RESTORE_UPLOADS=false
    RESTORE_CONFIG=false
    RESTORE_FULL=true
    DRY_RUN=false
    FORCE=false
    BACKUP_DATE=""

    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -d|--database)
                RESTORE_DATABASE=true
                RESTORE_FULL=false
                shift
                ;;
            -r|--redis)
                RESTORE_REDIS=true
                RESTORE_FULL=false
                shift
                ;;
            -u|--uploads)
                RESTORE_UPLOADS=true
                RESTORE_FULL=false
                shift
                ;;
            -c|--config)
                RESTORE_CONFIG=true
                RESTORE_FULL=false
                shift
                ;;
            -f|--full)
                RESTORE_FULL=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            *)
                if [[ -z "$BACKUP_DATE" ]]; then
                    BACKUP_DATE="$1"
                else
                    error "Unknown option: $1"
                    usage
                    exit 1
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$BACKUP_DATE" ]]; then
        error "Backup date is required"
        usage
        exit 1
    fi

    # Set individual restore flags if full restore
    if [[ "$RESTORE_FULL" == true ]]; then
        RESTORE_DATABASE=true
        RESTORE_REDIS=true
        RESTORE_UPLOADS=true
        RESTORE_CONFIG=true
    fi
}

# List available backups
list_backups() {
    log "Available backups:"
    find "$BACKUP_DIR" -type d -name "20*" -exec basename {} \; | sort -r | head -10
}

# Validate backup exists
validate_backup() {
    local backup_path="$BACKUP_DIR/$BACKUP_DATE"

    if [[ ! -d "$backup_path" ]]; then
        error "Backup directory not found: $backup_path"
        log "Available backups:"
        list_backups
        exit 1
    fi

    if [[ ! -f "$backup_path/backup_info.json" ]]; then
        warning "Backup metadata not found, proceeding anyway"
    else
        info "Backup metadata:"
        cat "$backup_path/backup_info.json" | jq . 2>/dev/null || cat "$backup_path/backup_info.json"
    fi
}

# Confirm restore operation
confirm_restore() {
    if [[ "$FORCE" == true ]]; then
        return 0
    fi

    warning "This will restore coBoarding platform from backup $BACKUP_DATE"
    warning "Current data will be OVERWRITTEN and LOST!"

    echo -n "Are you sure you want to continue? (yes/no): "
    read -r confirmation

    if [[ "$confirmation" != "yes" ]]; then
        log "Restore cancelled by user"
        exit 0
    fi
}

# Stop services
stop_services() {
    log "Stopping coBoarding services..."

    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would stop Docker services"
        return 0
    fi

    docker-compose down || warning "Some services may not have stopped cleanly"
    success "Services stopped"
}

# Start services
start_services() {
    log "Starting coBoarding services..."

    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would start Docker services"
        return 0
    fi

    docker-compose up -d

    # Wait for services to be ready
    log "Waiting for services to be ready..."
    sleep 30

    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        success "Services started successfully"
    else
        error "Some services failed to start"
        return 1
    fi
}

# Restore database
restore_database() {
    local backup_path="$BACKUP_DIR/$BACKUP_DATE"
    local db_backup="$backup_path/database/coboarding_${BACKUP_DATE}.dump.gz"

    log "Restoring database..."

    if [[ ! -f "$db_backup" ]]; then
        error "Database backup file not found: $db_backup"
        return 1
    fi

    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would restore database from $db_backup"
        return 0
    fi

    # Extract backup file
    local temp_dump="/tmp/coboarding_restore_${BACKUP_DATE}.dump"
    gunzip -c "$db_backup" > "$temp_dump"

    # Drop existing database and recreate
    log "Recreating database..."
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres << EOF
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME;
EOF

    # Restore database
    log "Restoring database data..."
    PGPASSWORD="$DB_PASSWORD" pg_restore \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges \
        "$temp_dump"

    if [[ $? -eq 0 ]]; then
        success "Database restored successfully"
        rm -f "$temp_dump"
    else
        error "Database restore failed"
        rm -f "$temp_dump"
        return 1
    fi
}

# Restore Redis
restore_redis() {
    local backup_path="$BACKUP_DIR/$BACKUP_DATE"
    local redis_backup="$backup_path/redis/dump_${BACKUP_DATE}.rdb.gz"

    log "Restoring Redis..."

    if [[ ! -f "$redis_backup" ]]; then
        error "Redis backup file not found: $redis_backup"
        return 1
    fi

    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would restore Redis from $redis_backup"
        return 0
    fi

    # Stop Redis service
    docker-compose stop redis

    # Extract and restore RDB file
    local temp_rdb="/tmp/dump_restore_${BACKUP_DATE}.rdb"
    gunzip -c "$redis_backup" > "$temp_rdb"

    # Copy RDB file to Redis container
    docker cp "$temp_rdb" coboarding_redis:/data/dump.rdb

    # Start Redis service
    docker-compose start redis

    # Wait for Redis to load data
    sleep 10

    # Verify Redis is working
    if docker exec coboarding_redis redis-cli ping | grep -q PONG; then
        success "Redis restored successfully"
        rm -f "$temp_rdb"
    else
        error "Redis restore failed"
        rm -f "$temp_rdb"
        return 1
    fi
}

# Restore uploads
restore_uploads() {
    local backup_path="$BACKUP_DIR/$BACKUP_DATE"
    local uploads_backup="$backup_path/uploads/uploads_${BACKUP_DATE}.tar.gz"

    log "Restoring uploads..."

    if [[ ! -f "$uploads_backup" ]]; then
        warning "Uploads backup file not found: $uploads_backup"
        return 0
    fi

    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would restore uploads from $uploads_backup"
        return 0
    fi

    # Backup current uploads if they exist
    if [[ -d "./uploads" ]]; then
        mv ./uploads "./uploads.backup.$(date +%s)" || true
    fi

    # Extract uploads
    tar -xzf "$uploads_backup" -C .

    if [[ $? -eq 0 ]]; then
        success "Uploads restored successfully"
    else
        error "Uploads restore failed"
        return 1
    fi
}

# Restore configuration
restore_config() {
    local backup_path="$BACKUP_DIR/$BACKUP_DATE"
    local config_backup="$backup_path/config/config_${BACKUP_DATE}.tar.gz"

    log "Restoring configuration..."

    if [[ ! -f "$config_backup" ]]; then
        warning "Configuration backup file not found: $config_backup"
        return 0
    fi

    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would restore configuration from $config_backup"
        return 0
    fi

    # Create backup of current config
    local config_backup_dir="./config.backup.$(date +%s)"
    mkdir -p "$config_backup_dir"

    # Backup important current configs
    cp -r nginx/ "$config_backup_dir/" 2>/dev/null || true
    cp -r monitoring/ "$config_backup_dir/" 2>/dev/null || true
    cp docker-compose.yml "$config_backup_dir/" 2>/dev/null || true

    # Extract configuration
    tar -xzf "$config_backup" -C .

    if [[ $? -eq 0 ]]; then
        success "Configuration restored successfully"
        info "Previous configuration backed up to: $config_backup_dir"
    else
        error "Configuration restore failed"
        return 1
    fi
}

# Verify restore
verify_restore() {
    log "Verifying restore..."

    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would verify restore"
        return 0
    fi

    local errors=0

    # Check database connection
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        success "Database connection verified"
    else
        error "Database connection failed"
        ((errors++))
    fi

    # Check Redis connection
    if docker exec coboarding_redis redis-cli ping | grep -q PONG; then
        success "Redis connection verified"
    else
        error "Redis connection failed"
        ((errors++))
    fi

    # Check application health
    sleep 30  # Give app time to start
    if curl -sf http://localhost:8501/healthz > /dev/null 2>&1; then
        success "Application health check passed"
    else
        warning "Application health check failed (may need more time to start)"
    fi

    if [[ $errors -eq 0 ]]; then
        success "Restore verification passed"
        return 0
    else
        error "Restore verification failed with $errors errors"
        return 1
    fi
}

# Main restore function
main() {
    parse_arguments "$@"

    log "=== Starting coBoarding Platform Restore ==="
    log "Backup date: $BACKUP_DATE"
    log "Components to restore:"
    [[ "$RESTORE_DATABASE" == true ]] && log "  - Database"
    [[ "$RESTORE_REDIS" == true ]] && log "  - Redis"
    [[ "$RESTORE_UPLOADS" == true ]] && log "  - Uploads"
    [[ "$RESTORE_CONFIG" == true ]] && log "  - Configuration"

    # Validate backup
    validate_backup

    # Confirm operation
    confirm_restore

    # Stop services
    stop_services

    # Perform restore operations
    local restore_success=true

    if [[ "$RESTORE_DATABASE" == true ]]; then
        restore_database || restore_success=false
    fi

    if [[ "$RESTORE_REDIS" == true ]]; then
        restore_redis || restore_success=false
    fi

    if [[ "$RESTORE_UPLOADS" == true ]]; then
        restore_uploads || restore_success=false
    fi

    if [[ "$RESTORE_CONFIG" == true ]]; then
        restore_config || restore_success=false
    fi

    # Start services
    start_services || restore_success=false

    # Verify restore
    if [[ "$restore_success" == true ]]; then
        verify_restore || restore_success=false
    fi

    # Final status
    if [[ "$restore_success" == true ]]; then
        success "=== Restore completed successfully ==="

        if [[ "$DRY_RUN" == false ]]; then
            log "Next steps:"
            log "1. Verify application functionality"
            log "2. Check logs for any issues"
            log "3. Test key features (CV upload, matching, chat)"
            log "4. Monitor system performance"
        fi

        exit 0
    else
        error "=== Restore completed with errors ==="
        log "Check logs and manual intervention may be required"
        exit 1
    fi
}

# Script execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

###########################################
# scripts/backup_cleanup.sh
# Automated cleanup script for old backups
###########################################

#!/bin/bash
# scripts/backup_cleanup.sh

set -euo pipefail

BACKUP_DIR="/backups"
DEFAULT_RETENTION_DAYS=30
LOG_FILE="/var/log/coboarding_cleanup.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Cleanup old coBoarding backups

OPTIONS:
    -h, --help              Show this help message
    -d, --days DAYS         Retention period in days (default: $DEFAULT_RETENTION_DAYS)
    -f, --force             Skip confirmation prompt
    --dry-run              Show what would be deleted without actually deleting

Examples:
    $0                      # Interactive cleanup with default retention
    $0 -d 7 -f             # Force cleanup of backups older than 7 days
    $0 --dry-run           # Preview what would be cleaned up

EOF
}

main() {
    local retention_days=$DEFAULT_RETENTION_DAYS
    local force=false
    local dry_run=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -d|--days)
                retention_days="$2"
                shift 2
                ;;
            -f|--force)
                force=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                echo "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    log "Starting backup cleanup (retention: $retention_days days)"

    # Find old backups
    local old_backups
    old_backups=$(find "$BACKUP_DIR" -type d -name "20*" -mtime +$retention_days 2>/dev/null || true)

    if [[ -z "$old_backups" ]]; then
        log "No old backups found to clean up"
        exit 0
    fi

    log "Found backups to clean up:"
    echo "$old_backups" | while read -r backup; do
        local size=$(du -sh "$backup" 2>/dev/null | cut -f1 || echo "unknown")
        log "  - $(basename "$backup") ($size)"
    done

    local total_size=$(echo "$old_backups" | xargs du -sc 2>/dev/null | tail -1 | cut -f1 || echo "0")
    log "Total size to be freed: $(numfmt --to=iec --suffix=B $total_size 2>/dev/null || echo "$total_size bytes")"

    if [[ "$dry_run" == true ]]; then
        log "DRY RUN: No files were actually deleted"
        exit 0
    fi

    if [[ "$force" == false ]]; then
        echo -n "Proceed with cleanup? (yes/no): "
        read -r confirmation
        if [[ "$confirmation" != "yes" ]]; then
            log "Cleanup cancelled by user"
            exit 0
        fi
    fi

    # Remove old backups
    local removed_count=0
    echo "$old_backups" | while read -r backup; do
        rm -rf "$backup"
        log "Removed: $(basename "$backup")"
        ((removed_count++))
    done

    log "Cleanup completed: $removed_count backups removed"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi