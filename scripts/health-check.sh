#!/bin/bash

# MindMesh Health Check Script
# This script monitors the health of all MindMesh services and infrastructure

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${NAMESPACE:-mindmesh}"
ENVIRONMENT="${ENVIRONMENT:-production}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"
MAX_RETRIES="${MAX_RETRIES:-3}"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"
LOG_FILE="${LOG_FILE:-/var/log/mindmesh-health.log}"

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
    echo "$message" >> "$LOG_FILE" 2>/dev/null || true
}

log_success() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS] $1"
    echo -e "${GREEN}${message}${NC}"
    echo "$message" >> "$LOG_FILE" 2>/dev/null || true
}

log_warning() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [WARNING] $1"
    echo -e "${YELLOW}${message}${NC}"
    echo "$message" >> "$LOG_FILE" 2>/dev/null || true
}

log_error() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1"
    echo -e "${RED}${message}${NC}"
    echo "$message" >> "$LOG_FILE" 2>/dev/null || true
}

# Help function
show_help() {
    cat << EOF
MindMesh Health Check Script

Usage: $0 [OPTIONS] [COMMAND]

Commands:
    check           Run health checks once (default)
    monitor         Continuous monitoring mode
    report          Generate detailed health report
    test-alerts     Test alert notifications
    services        Check only application services
    infrastructure  Check only infrastructure components

Options:
    -n, --namespace NS       Kubernetes namespace (default: mindmesh)
    -e, --environment ENV    Environment (default: production)
    -i, --interval SECONDS   Check interval in seconds (default: 30)
    -r, --retries COUNT      Max retries for failed checks (default: 3)
    -w, --webhook URL        Alert webhook URL
    -l, --log-file FILE      Log file path
    -v, --verbose            Verbose output
    -h, --help              Show this help message

Environment Variables:
    NAMESPACE        Kubernetes namespace
    ENVIRONMENT      Target environment
    CHECK_INTERVAL   Monitoring interval in seconds
    MAX_RETRIES      Maximum retries for failed checks
    ALERT_WEBHOOK    Webhook URL for alerts
    LOG_FILE         Log file path

Examples:
    $0 check --namespace mindmesh-staging
    $0 monitor --interval 60 --webhook https://hooks.slack.com/...
    $0 report --verbose
    $0 services --namespace mindmesh

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
            -i|--interval)
                CHECK_INTERVAL="$2"
                shift 2
                ;;
            -r|--retries)
                MAX_RETRIES="$2"
                shift 2
                ;;
            -w|--webhook)
                ALERT_WEBHOOK="$2"
                shift 2
                ;;
            -l|--log-file)
                LOG_FILE="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            check|monitor|report|test-alerts|services|infrastructure)
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

# Send alert notification
send_alert() {
    local severity="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    if [[ -n "$ALERT_WEBHOOK" ]]; then
        local color=""
        local emoji=""
        
        case "$severity" in
            "CRITICAL")
                color="danger"
                emoji="🚨"
                ;;
            "WARNING")
                color="warning"
                emoji="⚠️"
                ;;
            "INFO")
                color="good"
                emoji="ℹ️"
                ;;
            "SUCCESS")
                color="good"
                emoji="✅"
                ;;
        esac
        
        local payload=$(cat <<EOF
{
    "attachments": [
        {
            "color": "$color",
            "title": "$emoji MindMesh Health Alert - $severity",
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
                    "value": "$timestamp",
                    "short": false
                }
            ]
        }
    ]
}
EOF
        )
        
        curl -s -X POST -H 'Content-type: application/json' \
             --data "$payload" "$ALERT_WEBHOOK" &>/dev/null || true
    fi
}

# Check if kubectl is available and configured
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        return 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        return 1
    fi
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Namespace '$NAMESPACE' does not exist"
        return 1
    fi
    
    return 0
}

# Check deployment health
check_deployment() {
    local deployment="$1"
    local retries=0
    
    while [[ $retries -lt $MAX_RETRIES ]]; do
        if kubectl get deployment "$deployment" -n "$NAMESPACE" &> /dev/null; then
            local ready=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
            local desired=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
            
            if [[ "$ready" == "$desired" && "$ready" != "0" ]]; then
                log_success "$deployment: $ready/$desired replicas ready"
                return 0
            else
                log_warning "$deployment: $ready/$desired replicas ready (attempt $((retries + 1))/$MAX_RETRIES)"
            fi
        else
            log_warning "$deployment: deployment not found (attempt $((retries + 1))/$MAX_RETRIES)"
        fi
        
        retries=$((retries + 1))
        if [[ $retries -lt $MAX_RETRIES ]]; then
            sleep 10
        fi
    done
    
    log_error "$deployment: health check failed after $MAX_RETRIES attempts"
    return 1
}

# Check service health
check_service() {
    local service="$1"
    local port="$2"
    local path="${3:-/health}"
    
    # Check if service exists
    if ! kubectl get service "$service" -n "$NAMESPACE" &> /dev/null; then
        log_error "$service: service not found"
        return 1
    fi
    
    # Port forward and check endpoint
    local local_port=$((8000 + RANDOM % 1000))
    kubectl port-forward svc/"$service" "$local_port:$port" -n "$NAMESPACE" &>/dev/null &
    local pf_pid=$!
    
    sleep 2
    
    local http_code=""
    if command -v curl &> /dev/null; then
        http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$local_port$path" 2>/dev/null || echo "000")
    else
        http_code=$(wget -qO- --server-response "http://localhost:$local_port$path" 2>&1 | awk '/^  HTTP/{print $2}' | tail -1 || echo "000")
    fi
    
    kill $pf_pid 2>/dev/null || true
    wait $pf_pid 2>/dev/null || true
    
    if [[ "$http_code" == "200" ]]; then
        log_success "$service: endpoint $path responded with HTTP $http_code"
        return 0
    else
        log_error "$service: endpoint $path responded with HTTP $http_code"
        return 1
    fi
}

# Check persistent volume claims
check_pvcs() {
    local pvcs=("postgresql-pvc" "redis-pvc")
    local all_healthy=true
    
    for pvc in "${pvcs[@]}"; do
        if kubectl get pvc "$pvc" -n "$NAMESPACE" &> /dev/null; then
            local status=$(kubectl get pvc "$pvc" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
            if [[ "$status" == "Bound" ]]; then
                log_success "$pvc: $status"
            else
                log_error "$pvc: $status"
                all_healthy=false
            fi
        else
            log_warning "$pvc: not found"
        fi
    done
    
    return $([[ "$all_healthy" == true ]] && echo 0 || echo 1)
}

# Check resource usage
check_resource_usage() {
    log_info "Checking resource usage..."
    
    # Check node resources
    if kubectl top nodes &> /dev/null; then
        log_info "Node resource usage:"
        kubectl top nodes
    else
        log_warning "Metrics server not available for node metrics"
    fi
    
    # Check pod resources
    if kubectl top pods -n "$NAMESPACE" &> /dev/null; then
        log_info "Pod resource usage in namespace $NAMESPACE:"
        kubectl top pods -n "$NAMESPACE"
    else
        log_warning "Metrics server not available for pod metrics"
    fi
}

# Check infrastructure components
check_infrastructure() {
    log_info "Checking infrastructure components..."
    
    local infra_components=("postgresql" "redis")
    local all_healthy=true
    
    for component in "${infra_components[@]}"; do
        if ! check_deployment "$component"; then
            all_healthy=false
        fi
    done
    
    # Check PVCs
    if ! check_pvcs; then
        all_healthy=false
    fi
    
    return $([[ "$all_healthy" == true ]] && echo 0 || echo 1)
}

# Check application services
check_application_services() {
    log_info "Checking application services..."
    
    local services=(
        "ideas-service:3001"
        "voting-service:3002"
        "analytics-service:3003"
        "decision-service:3004"
    )
    
    local all_healthy=true
    
    for service_info in "${services[@]}"; do
        local service_name=$(echo "$service_info" | cut -d':' -f1)
        local service_port=$(echo "$service_info" | cut -d':' -f2)
        
        if ! check_deployment "$service_name"; then
            all_healthy=false
            continue
        fi
        
        if ! check_service "$service_name" "$service_port"; then
            all_healthy=false
        fi
    done
    
    return $([[ "$all_healthy" == true ]] && echo 0 || echo 1)
}

# Check ingress and networking
check_networking() {
    log_info "Checking networking components..."
    
    # Check ingress
    if kubectl get ingress -n "$NAMESPACE" &> /dev/null; then
        local ingress_count=$(kubectl get ingress -n "$NAMESPACE" --no-headers | wc -l)
        if [[ $ingress_count -gt 0 ]]; then
            log_success "Ingress controllers: $ingress_count found"
            kubectl get ingress -n "$NAMESPACE"
        else
            log_warning "No ingress controllers found"
        fi
    else
        log_warning "Cannot access ingress resources"
    fi
    
    # Check services
    local service_count=$(kubectl get svc -n "$NAMESPACE" --no-headers | wc -l)
    log_info "Services in namespace: $service_count"
    
    # Check network policies
    if kubectl get networkpolicy -n "$NAMESPACE" &> /dev/null; then
        local netpol_count=$(kubectl get networkpolicy -n "$NAMESPACE" --no-headers | wc -l)
        if [[ $netpol_count -gt 0 ]]; then
            log_success "Network policies: $netpol_count found"
        else
            log_info "No network policies found"
        fi
    fi
}

# Check HPA status
check_hpa() {
    log_info "Checking Horizontal Pod Autoscaler status..."
    
    if kubectl get hpa -n "$NAMESPACE" &> /dev/null; then
        local hpa_list=$(kubectl get hpa -n "$NAMESPACE" --no-headers)
        if [[ -n "$hpa_list" ]]; then
            log_success "HPA configurations found:"
            kubectl get hpa -n "$NAMESPACE"
        else
            log_info "No HPA configurations found"
        fi
    else
        log_warning "Cannot access HPA resources"
    fi
}

# Generate comprehensive health report
generate_health_report() {
    log_info "Generating comprehensive health report..."
    
    local report_file="/tmp/mindmesh-health-report-$(date +%Y%m%d-%H%M%S).txt"
    
    {
        echo "MindMesh Health Report"
        echo "====================="
        echo "Generated: $(date)"
        echo "Environment: $ENVIRONMENT"
        echo "Namespace: $NAMESPACE"
        echo ""
        
        echo "=== Cluster Information ==="
        kubectl cluster-info
        echo ""
        
        echo "=== Namespace Status ==="
        kubectl get namespace "$NAMESPACE" -o wide
        echo ""
        
        echo "=== Deployments ==="
        kubectl get deployments -n "$NAMESPACE" -o wide
        echo ""
        
        echo "=== Pods ==="
        kubectl get pods -n "$NAMESPACE" -o wide
        echo ""
        
        echo "=== Services ==="
        kubectl get svc -n "$NAMESPACE" -o wide
        echo ""
        
        echo "=== Ingress ==="
        kubectl get ingress -n "$NAMESPACE" -o wide 2>/dev/null || echo "No ingress found"
        echo ""
        
        echo "=== PersistentVolumeClaims ==="
        kubectl get pvc -n "$NAMESPACE" -o wide
        echo ""
        
        echo "=== HPA ==="
        kubectl get hpa -n "$NAMESPACE" -o wide 2>/dev/null || echo "No HPA found"
        echo ""
        
        echo "=== Events (Last 1 hour) ==="
        kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' | grep -E "$(date -d '1 hour ago' '+%Y-%m-%d %H')" || echo "No recent events"
        echo ""
        
        if kubectl top nodes &> /dev/null; then
            echo "=== Node Resource Usage ==="
            kubectl top nodes
            echo ""
        fi
        
        if kubectl top pods -n "$NAMESPACE" &> /dev/null; then
            echo "=== Pod Resource Usage ==="
            kubectl top pods -n "$NAMESPACE"
            echo ""
        fi
        
    } > "$report_file"
    
    log_success "Health report generated: $report_file"
    
    if [[ "${VERBOSE:-false}" == "true" ]]; then
        cat "$report_file"
    fi
}

# Run single health check
run_health_check() {
    log_info "Starting health check for MindMesh ($ENVIRONMENT environment)"
    
    local overall_health=true
    local start_time=$(date +%s)
    
    # Check prerequisites
    if ! check_kubectl; then
        send_alert "CRITICAL" "Cannot connect to Kubernetes cluster"
        return 1
    fi
    
    # Check infrastructure
    if ! check_infrastructure; then
        overall_health=false
        send_alert "CRITICAL" "Infrastructure components are unhealthy"
    fi
    
    # Check applications
    if ! check_application_services; then
        overall_health=false
        send_alert "CRITICAL" "Application services are unhealthy"
    fi
    
    # Check networking
    check_networking
    
    # Check HPA
    check_hpa
    
    # Check resource usage
    if [[ "${VERBOSE:-false}" == "true" ]]; then
        check_resource_usage
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [[ "$overall_health" == true ]]; then
        log_success "All health checks passed! (completed in ${duration}s)"
        send_alert "SUCCESS" "All MindMesh services are healthy"
        return 0
    else
        log_error "Some health checks failed! (completed in ${duration}s)"
        return 1
    fi
}

# Continuous monitoring mode
monitoring_mode() {
    log_info "Starting continuous monitoring mode (interval: ${CHECK_INTERVAL}s)"
    
    local consecutive_failures=0
    local max_consecutive_failures=3
    
    while true; do
        log_info "Running health check cycle..."
        
        if run_health_check; then
            consecutive_failures=0
        else
            consecutive_failures=$((consecutive_failures + 1))
            
            if [[ $consecutive_failures -ge $max_consecutive_failures ]]; then
                send_alert "CRITICAL" "Health checks have failed $consecutive_failures consecutive times"
                log_error "Health checks have failed $consecutive_failures consecutive times"
            fi
        fi
        
        log_info "Waiting ${CHECK_INTERVAL} seconds before next check..."
        sleep "$CHECK_INTERVAL"
    done
}

# Test alert notifications
test_alerts() {
    log_info "Testing alert notifications..."
    
    if [[ -z "$ALERT_WEBHOOK" ]]; then
        log_error "No alert webhook configured. Use --webhook option or set ALERT_WEBHOOK environment variable"
        return 1
    fi
    
    send_alert "INFO" "This is a test alert from MindMesh health check system"
    log_success "Test alert sent to webhook: $ALERT_WEBHOOK"
}

# Main execution function
main() {
    local command="${1:-check}"
    
    # Create log directory if it doesn't exist
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    
    case "$command" in
        "check")
            run_health_check
            ;;
        "monitor")
            monitoring_mode
            ;;
        "report")
            generate_health_report
            ;;
        "test-alerts")
            test_alerts
            ;;
        "services")
            check_kubectl && check_application_services
            ;;
        "infrastructure")
            check_kubectl && check_infrastructure
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Signal handling for graceful shutdown
cleanup() {
    log_info "Shutting down health check..."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Parse arguments and run main function
COMMAND="check"
VERBOSE=false
parse_args "$@"
main "$COMMAND"