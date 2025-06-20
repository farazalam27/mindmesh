#!/bin/bash

# MindMesh Backup Script
# This script creates backups of PostgreSQL database, Redis data, and application files

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${NAMESPACE:-mindmesh}"
ENVIRONMENT="${ENVIRONMENT:-production}"
BACKUP_DIR="${BACKUP_DIR:-/backups/mindmesh}"
S3_BUCKET="${S3_BUCKET:-mindmesh-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
ENCRYPTION_KEY="${ENCRYPTION_KEY:-}"
NOTIFICATION_WEBHOOK="${NOTIFICATION_WEBHOOK:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
    echo -e "${BLUE}${message}${NC}"
}

log_success() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS] $1"
    echo -e "${GREEN}${message}${NC}"
}

log_warning() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [WARNING] $1"
    echo -e "${YELLOW}${message}${NC}"
}

log_error() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1"
    echo -e "${RED}${message}${NC}"
}

# Help function
show_help() {
    cat << EOF
MindMesh Backup Script

Usage: $0 [OPTIONS] [COMMAND]

Commands:
    backup          Create full backup (default)
    restore         Restore from backup
    list            List available backups
    cleanup         Clean up old backups
    test            Test backup system
    schedule        Set up automated backup schedule

Options:
    -n, --namespace NS       Kubernetes namespace (default: mindmesh)
    -e, --environment ENV    Environment (default: production)
    -d, --backup-dir DIR     Local backup directory
    -b, --s3-bucket BUCKET   S3 bucket for remote backup storage
    -r, --retention DAYS     Backup retention in days (default: 30)
    -k, --encryption-key KEY Encryption key for backup files
    -w, --webhook URL        Notification webhook URL
    -c, --compress           Compress backup files
    -v, --verbose            Verbose output
    -h, --help              Show this help message

Environment Variables:
    NAMESPACE               Kubernetes namespace
    ENVIRONMENT            Target environment
    BACKUP_DIR             Local backup directory
    S3_BUCKET              S3 bucket name
    RETENTION_DAYS         Backup retention days
    ENCRYPTION_KEY         Encryption key
    NOTIFICATION_WEBHOOK   Webhook for notifications

Examples:
    $0 backup --compress --s3-bucket my-backups
    $0 restore --backup-id 20231201-120000
    $0 list --environment production
    $0 cleanup --retention 7

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -d|--backup-dir)
                BACKUP_DIR="$2"
                shift 2
                ;;
            -b|--s3-bucket)
                S3_BUCKET="$2"
                shift 2
                ;;
            -r|--retention)
                RETENTION_DAYS="$2"
                shift 2
                ;;
            -k|--encryption-key)
                ENCRYPTION_KEY="$2"
                shift 2
                ;;
            -w|--webhook)
                NOTIFICATION_WEBHOOK="$2"
                shift 2
                ;;
            -c|--compress)
                COMPRESS=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            --backup-id)
                BACKUP_ID="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            backup|restore|list|cleanup|test|schedule)
                COMMAND="$1"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Send notification
send_notification() {
    local status="$1"
    local message="$2"
    
    if [[ -n "$NOTIFICATION_WEBHOOK" ]]; then
        local color=""
        local emoji=""
        
        case "$status" in
            "SUCCESS")
                color="good"
                emoji="✅"
                ;;
            "ERROR")
                color="danger"
                emoji="❌"
                ;;
            "WARNING")
                color="warning"
                emoji="⚠️"
                ;;
            *)
                color="warning"
                emoji="ℹ️"
                ;;
        esac
        
        local payload=$(cat <<EOF
{
    "attachments": [
        {
            "color": "$color",
            "title": "$emoji MindMesh Backup - $status",
            "text": "$message",
            "fields": [
                {
                    "title": "Environment",
                    "value": "$ENVIRONMENT",
                    "short": true
                },
                {
                    "title": "Namespace",
                    "value": "$NAMESPACE",
                    "short": true
                },
                {
                    "title": "Timestamp",
                    "value": "$(date '+%Y-%m-%d %H:%M:%S')",
                    "short": false
                }
            ]
        }
    ]
}
EOF
        )
        
        curl -s -X POST -H 'Content-type: application/json' \
             --data "$payload" "$NOTIFICATION_WEBHOOK" &>/dev/null || true
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    # Check if kubectl can connect to cluster
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Namespace '$NAMESPACE' does not exist"
        exit 1
    fi
    
    # Check if backup directory exists or create it
    if [[ ! -d "$BACKUP_DIR" ]]; then
        mkdir -p "$BACKUP_DIR" || {
            log_error "Cannot create backup directory: $BACKUP_DIR"
            exit 1
        }
    fi
    
    # Check if required tools are available
    local required_tools=("pg_dump" "redis-cli")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_warning "$tool is not installed, will use kubectl exec for database operations"
        fi
    done
    
    # Check AWS CLI if S3 backup is enabled
    if [[ -n "$S3_BUCKET" ]] && ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed but S3 backup is configured"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Generate backup ID
generate_backup_id() {
    echo "$(date '+%Y%m%d-%H%M%S')-${ENVIRONMENT}"
}

# Encrypt file if encryption key is provided
encrypt_file() {
    local file="$1"
    
    if [[ -n "$ENCRYPTION_KEY" ]]; then
        if command -v openssl &> /dev/null; then
            openssl enc -aes-256-cbc -salt -in "$file" -out "${file}.enc" -k "$ENCRYPTION_KEY"
            rm "$file"
            mv "${file}.enc" "$file"
            log_info "Encrypted backup file: $(basename "$file")"
        else
            log_warning "OpenSSL not available, backup not encrypted"
        fi
    fi
}

# Decrypt file if needed
decrypt_file() {
    local file="$1"
    
    if [[ -n "$ENCRYPTION_KEY" && "$file" =~ \.enc$ ]]; then
        if command -v openssl &> /dev/null; then
            local decrypted_file="${file%.enc}"
            openssl enc -aes-256-cbc -d -in "$file" -out "$decrypted_file" -k "$ENCRYPTION_KEY"
            log_info "Decrypted backup file: $(basename "$decrypted_file")"
            echo "$decrypted_file"
        else
            log_error "OpenSSL not available, cannot decrypt backup"
            return 1
        fi
    else
        echo "$file"
    fi
}

# Compress file if compression is enabled
compress_file() {
    local file="$1"
    
    if [[ "${COMPRESS:-false}" == "true" ]]; then
        if command -v gzip &> /dev/null; then
            gzip "$file"
            log_info "Compressed backup file: $(basename "${file}.gz")"
            echo "${file}.gz"
        else
            log_warning "gzip not available, backup not compressed"
            echo "$file"
        fi
    else
        echo "$file"
    fi
}

# Backup PostgreSQL database
backup_postgresql() {
    local backup_id="$1"
    local backup_file="${BACKUP_DIR}/postgresql-${backup_id}.sql"
    
    log_info "Starting PostgreSQL backup..."
    
    # Get PostgreSQL pod
    local postgres_pod=$(kubectl get pods -n "$NAMESPACE" -l app=postgresql -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -z "$postgres_pod" ]]; then
        log_error "PostgreSQL pod not found"
        return 1
    fi
    
    # Get database credentials from secrets
    local db_user=$(kubectl get secret mindmesh-secrets -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_USER}' | base64 -d 2>/dev/null || echo "mindmesh_user")
    local db_name=$(kubectl get configmap mindmesh-config -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_DB}' 2>/dev/null || echo "mindmesh")
    
    # Create backup using kubectl exec
    kubectl exec -n "$NAMESPACE" "$postgres_pod" -- pg_dump -U "$db_user" -d "$db_name" --no-password > "$backup_file"
    
    if [[ $? -eq 0 && -s "$backup_file" ]]; then
        log_success "PostgreSQL backup completed: $(basename "$backup_file")"
        
        # Compress and encrypt if configured
        backup_file=$(compress_file "$backup_file")
        encrypt_file "$backup_file"
        
        echo "$backup_file"
    else
        log_error "PostgreSQL backup failed"
        rm -f "$backup_file"
        return 1
    fi
}

# Backup Redis data
backup_redis() {
    local backup_id="$1"
    local backup_file="${BACKUP_DIR}/redis-${backup_id}.rdb"
    
    log_info "Starting Redis backup..."
    
    # Get Redis pod
    local redis_pod=$(kubectl get pods -n "$NAMESPACE" -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -z "$redis_pod" ]]; then
        log_error "Redis pod not found"
        return 1
    fi
    
    # Trigger Redis BGSAVE and copy RDB file
    kubectl exec -n "$NAMESPACE" "$redis_pod" -- redis-cli BGSAVE
    
    # Wait for background save to complete
    local save_in_progress=true
    local attempts=0
    while [[ "$save_in_progress" == true && $attempts -lt 30 ]]; do
        local last_save=$(kubectl exec -n "$NAMESPACE" "$redis_pod" -- redis-cli LASTSAVE)
        sleep 2
        local current_save=$(kubectl exec -n "$NAMESPACE" "$redis_pod" -- redis-cli LASTSAVE)
        
        if [[ "$last_save" != "$current_save" ]]; then
            save_in_progress=false
        fi
        
        attempts=$((attempts + 1))
    done
    
    if [[ "$save_in_progress" == true ]]; then
        log_warning "Redis background save may not have completed"
    fi
    
    # Copy RDB file
    kubectl cp -n "$NAMESPACE" "$redis_pod:/data/dump.rdb" "$backup_file"
    
    if [[ $? -eq 0 && -s "$backup_file" ]]; then
        log_success "Redis backup completed: $(basename "$backup_file")"
        
        # Compress and encrypt if configured
        backup_file=$(compress_file "$backup_file")
        encrypt_file "$backup_file"
        
        echo "$backup_file"
    else
        log_error "Redis backup failed"
        rm -f "$backup_file"
        return 1
    fi
}

# Backup Kubernetes manifests and configs
backup_kubernetes_config() {
    local backup_id="$1"
    local backup_file="${BACKUP_DIR}/kubernetes-${backup_id}.yaml"
    
    log_info "Starting Kubernetes configuration backup..."
    
    {
        echo "# MindMesh Kubernetes Configuration Backup"
        echo "# Generated: $(date)"
        echo "# Environment: $ENVIRONMENT"
        echo "# Namespace: $NAMESPACE"
        echo ""
        
        echo "---"
        echo "# Namespace"
        kubectl get namespace "$NAMESPACE" -o yaml
        
        echo "---"
        echo "# ConfigMaps"
        kubectl get configmaps -n "$NAMESPACE" -o yaml
        
        echo "---"
        echo "# Secrets (data removed for security)"
        kubectl get secrets -n "$NAMESPACE" -o yaml | sed 's/data:.*/data: {}/g'
        
        echo "---"
        echo "# Deployments"
        kubectl get deployments -n "$NAMESPACE" -o yaml
        
        echo "---"
        echo "# Services"
        kubectl get services -n "$NAMESPACE" -o yaml
        
        echo "---"
        echo "# Ingress"
        kubectl get ingress -n "$NAMESPACE" -o yaml 2>/dev/null || echo "# No ingress found"
        
        echo "---"
        echo "# HPA"
        kubectl get hpa -n "$NAMESPACE" -o yaml 2>/dev/null || echo "# No HPA found"
        
        echo "---"
        echo "# PVCs"
        kubectl get pvc -n "$NAMESPACE" -o yaml
        
    } > "$backup_file"
    
    if [[ -s "$backup_file" ]]; then
        log_success "Kubernetes configuration backup completed: $(basename "$backup_file")"
        
        # Compress and encrypt if configured
        backup_file=$(compress_file "$backup_file")
        encrypt_file "$backup_file"
        
        echo "$backup_file"
    else
        log_error "Kubernetes configuration backup failed"
        rm -f "$backup_file"
        return 1
    fi
}

# Upload backup to S3
upload_to_s3() {
    local file="$1"
    local backup_id="$2"
    
    if [[ -z "$S3_BUCKET" ]]; then
        return 0
    fi
    
    log_info "Uploading backup to S3: s3://$S3_BUCKET/"
    
    local s3_key="mindmesh/${ENVIRONMENT}/${backup_id}/$(basename "$file")"
    
    if aws s3 cp "$file" "s3://$S3_BUCKET/$s3_key" --storage-class STANDARD_IA; then
        log_success "Uploaded to S3: s3://$S3_BUCKET/$s3_key"
    else
        log_error "Failed to upload to S3: $file"
        return 1
    fi
}

# Create backup manifest
create_backup_manifest() {
    local backup_id="$1"
    local files=("${@:2}")
    local manifest_file="${BACKUP_DIR}/manifest-${backup_id}.json"
    
    local file_list=""
    for file in "${files[@]}"; do
        local file_size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo "0")
        local file_hash=$(sha256sum "$file" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "$file" | cut -d' ' -f1)
        
        if [[ -n "$file_list" ]]; then
            file_list="$file_list,"
        fi
        
        file_list="$file_list
        {
            \"name\": \"$(basename "$file")\",
            \"path\": \"$file\",
            \"size\": $file_size,
            \"hash\": \"$file_hash\"
        }"
    done
    
    cat > "$manifest_file" <<EOF
{
    "backup_id": "$backup_id",
    "environment": "$ENVIRONMENT",
    "namespace": "$NAMESPACE",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)",
    "version": "1.0",
    "files": [$file_list
    ]
}
EOF
    
    log_success "Created backup manifest: $(basename "$manifest_file")"
    echo "$manifest_file"
}

# Perform full backup
perform_backup() {
    local backup_id=$(generate_backup_id)
    local backup_files=()
    local start_time=$(date +%s)
    
    log_info "Starting full backup with ID: $backup_id"
    
    check_prerequisites
    
    # Backup PostgreSQL
    if postgres_backup=$(backup_postgresql "$backup_id"); then
        backup_files+=("$postgres_backup")
    else
        send_notification "ERROR" "PostgreSQL backup failed for backup ID: $backup_id"
        return 1
    fi
    
    # Backup Redis
    if redis_backup=$(backup_redis "$backup_id"); then
        backup_files+=("$redis_backup")
    else
        send_notification "ERROR" "Redis backup failed for backup ID: $backup_id"
        return 1
    fi
    
    # Backup Kubernetes configuration
    if k8s_backup=$(backup_kubernetes_config "$backup_id"); then
        backup_files+=("$k8s_backup")
    else
        send_notification "ERROR" "Kubernetes configuration backup failed for backup ID: $backup_id"
        return 1
    fi
    
    # Create manifest
    if manifest_file=$(create_backup_manifest "$backup_id" "${backup_files[@]}"); then
        backup_files+=("$manifest_file")
    fi
    
    # Upload to S3 if configured
    if [[ -n "$S3_BUCKET" ]]; then
        for file in "${backup_files[@]}"; do
            upload_to_s3 "$file" "$backup_id"
        done
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local total_size=0
    
    for file in "${backup_files[@]}"; do
        local file_size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo "0")
        total_size=$((total_size + file_size))
    done
    
    local human_size=$(numfmt --to=iec-i --suffix=B "$total_size" 2>/dev/null || echo "${total_size} bytes")
    
    log_success "Backup completed successfully!"
    log_info "Backup ID: $backup_id"
    log_info "Files: ${#backup_files[@]}"
    log_info "Total size: $human_size"
    log_info "Duration: ${duration}s"
    log_info "Location: $BACKUP_DIR"
    
    send_notification "SUCCESS" "Backup completed successfully. ID: $backup_id, Size: $human_size, Duration: ${duration}s"
}

# List available backups
list_backups() {
    log_info "Available backups in $BACKUP_DIR:"
    
    local manifests=($(find "$BACKUP_DIR" -name "manifest-*.json" 2>/dev/null | sort -r))
    
    if [[ ${#manifests[@]} -eq 0 ]]; then
        log_info "No backups found"
        return 0
    fi
    
    printf "%-20s %-12s %-10s %-15s %-10s\n" "BACKUP_ID" "ENVIRONMENT" "NAMESPACE" "TIMESTAMP" "FILES"
    printf "%-20s %-12s %-10s %-15s %-10s\n" "--------" "-----------" "---------" "---------" "-----"
    
    for manifest in "${manifests[@]}"; do
        if command -v jq &> /dev/null; then
            local backup_id=$(jq -r '.backup_id' "$manifest")
            local environment=$(jq -r '.environment' "$manifest")
            local namespace=$(jq -r '.namespace' "$manifest")
            local timestamp=$(jq -r '.timestamp' "$manifest" | cut -d'T' -f1)
            local file_count=$(jq '.files | length' "$manifest")
            
            printf "%-20s %-12s %-10s %-15s %-10s\n" "$backup_id" "$environment" "$namespace" "$timestamp" "$file_count"
        else
            local backup_id=$(basename "$manifest" .json | sed 's/manifest-//')
            printf "%-20s %-12s %-10s %-15s %-10s\n" "$backup_id" "unknown" "unknown" "unknown" "unknown"
        fi
    done
}

# Clean up old backups
cleanup_backups() {
    log_info "Cleaning up backups older than $RETENTION_DAYS days..."
    
    local deleted_count=0
    local cutoff_date=$(date -d "${RETENTION_DAYS} days ago" +%Y%m%d 2>/dev/null || date -v-${RETENTION_DAYS}d +%Y%m%d)
    
    # Find and delete old backup files
    while IFS= read -r -d '' file; do
        local file_date=$(basename "$file" | grep -o '^[0-9]\{8\}' || echo "99999999")
        
        if [[ "$file_date" < "$cutoff_date" ]]; then
            log_info "Deleting old backup: $(basename "$file")"
            rm -f "$file"
            deleted_count=$((deleted_count + 1))
        fi
    done < <(find "$BACKUP_DIR" -name "*-${ENVIRONMENT}.sql*" -o -name "*-${ENVIRONMENT}.rdb*" -o -name "*-${ENVIRONMENT}.yaml*" -o -name "manifest-*-${ENVIRONMENT}.json" -print0 2>/dev/null)
    
    # Clean up S3 if configured
    if [[ -n "$S3_BUCKET" ]] && command -v aws &> /dev/null; then
        log_info "Cleaning up S3 backups older than $RETENTION_DAYS days..."
        
        local s3_cutoff=$(date -d "${RETENTION_DAYS} days ago" -u +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -v-${RETENTION_DAYS}d -u +%Y-%m-%dT%H:%M:%S)
        
        aws s3api list-objects-v2 --bucket "$S3_BUCKET" --prefix "mindmesh/${ENVIRONMENT}/" --query "Contents[?LastModified<='${s3_cutoff}'].Key" --output text | \
        while read -r key; do
            if [[ -n "$key" && "$key" != "None" ]]; then
                log_info "Deleting S3 object: s3://$S3_BUCKET/$key"
                aws s3 rm "s3://$S3_BUCKET/$key"
                deleted_count=$((deleted_count + 1))
            fi
        done
    fi
    
    log_success "Cleanup completed. Deleted $deleted_count files."
}

# Restore from backup
restore_backup() {
    local backup_id="${BACKUP_ID:-}"
    
    if [[ -z "$backup_id" ]]; then
        log_error "Backup ID not specified. Use --backup-id option"
        return 1
    fi
    
    log_info "Restoring from backup ID: $backup_id"
    
    local manifest_file="${BACKUP_DIR}/manifest-${backup_id}.json"
    
    if [[ ! -f "$manifest_file" ]]; then
        log_error "Backup manifest not found: $manifest_file"
        return 1
    fi
    
    log_warning "Restore operation will overwrite existing data. Continue? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled"
        return 0
    fi
    
    # TODO: Implement restore logic
    log_warning "Restore functionality is not yet implemented"
    log_info "Manual restore steps:"
    log_info "1. Stop application services"
    log_info "2. Restore PostgreSQL from: postgresql-${backup_id}.sql*"
    log_info "3. Restore Redis from: redis-${backup_id}.rdb*"
    log_info "4. Apply Kubernetes config from: kubernetes-${backup_id}.yaml*"
    log_info "5. Start application services"
}

# Test backup system
test_backup_system() {
    log_info "Testing backup system..."
    
    check_prerequisites
    
    # Test database connections
    local postgres_pod=$(kubectl get pods -n "$NAMESPACE" -l app=postgresql -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    local redis_pod=$(kubectl get pods -n "$NAMESPACE" -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -n "$postgres_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$postgres_pod" -- pg_isready &>/dev/null; then
            log_success "PostgreSQL connection test passed"
        else
            log_error "PostgreSQL connection test failed"
        fi
    else
        log_error "PostgreSQL pod not found"
    fi
    
    if [[ -n "$redis_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$redis_pod" -- redis-cli ping | grep -q PONG; then
            log_success "Redis connection test passed"
        else
            log_error "Redis connection test failed"
        fi
    else
        log_error "Redis pod not found"
    fi
    
    # Test S3 access if configured
    if [[ -n "$S3_BUCKET" ]]; then
        if aws s3 ls "s3://$S3_BUCKET/" &>/dev/null; then
            log_success "S3 access test passed"
        else
            log_error "S3 access test failed"
        fi
    fi
    
    # Test notification webhook if configured
    if [[ -n "$NOTIFICATION_WEBHOOK" ]]; then
        send_notification "INFO" "Backup system test notification"
        log_success "Notification test sent"
    fi
    
    log_success "Backup system test completed"
}

# Set up automated backup schedule
setup_schedule() {
    log_info "Setting up automated backup schedule..."
    
    local cron_job="0 2 * * * $SCRIPT_DIR/backup.sh backup --environment $ENVIRONMENT --namespace $NAMESPACE"
    
    if [[ -n "$S3_BUCKET" ]]; then
        cron_job="$cron_job --s3-bucket $S3_BUCKET"
    fi
    
    if [[ -n "$NOTIFICATION_WEBHOOK" ]]; then
        cron_job="$cron_job --webhook '$NOTIFICATION_WEBHOOK'"
    fi
    
    log_info "Add this line to your crontab (crontab -e):"
    echo "$cron_job"
    
    log_info "This will run backups daily at 2:00 AM"
    log_info "Also add cleanup job:"
    echo "0 3 * * 0 $SCRIPT_DIR/backup.sh cleanup --environment $ENVIRONMENT --retention $RETENTION_DAYS"
}

# Main execution function
main() {
    local command="${1:-backup}"
    
    case "$command" in
        "backup")
            perform_backup
            ;;
        "restore")
            restore_backup
            ;;
        "list")
            list_backups
            ;;
        "cleanup")
            cleanup_backups
            ;;
        "test")
            test_backup_system
            ;;
        "schedule")
            setup_schedule
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Parse arguments and run main function
COMMAND="backup"
VERBOSE=false
COMPRESS=false
parse_args "$@"
main "$COMMAND"