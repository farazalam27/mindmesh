#!/bin/bash

# MindMesh Deployment Script
# This script automates the deployment of MindMesh services to Kubernetes

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${NAMESPACE:-mindmesh}"
ENVIRONMENT="${ENVIRONMENT:-production}"
VERSION="${VERSION:-latest}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-ghcr.io/farazalam27/mindmesh}"
KUBECTL_TIMEOUT="${KUBECTL_TIMEOUT:-300s}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
MindMesh Deployment Script

Usage: $0 [OPTIONS] [COMMAND]

Commands:
    deploy          Deploy all services (default)
    deploy-infra    Deploy infrastructure components only
    deploy-apps     Deploy application services only
    rollback        Rollback to previous version
    status          Check deployment status
    logs            View application logs
    cleanup         Clean up resources

Options:
    -e, --environment ENV    Environment (production, staging, development)
    -n, --namespace NS       Kubernetes namespace
    -v, --version VERSION    Application version to deploy
    -r, --registry REGISTRY  Docker registry URL
    -h, --help              Show this help message

Environment Variables:
    ENVIRONMENT      Target environment
    NAMESPACE        Kubernetes namespace
    VERSION          Application version
    DOCKER_REGISTRY  Docker registry URL
    KUBECTL_TIMEOUT  Kubectl operation timeout

Examples:
    $0 deploy --environment staging --version v1.2.3
    $0 rollback --namespace mindmesh-staging
    $0 status --environment production
    $0 logs --namespace mindmesh

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -v|--version)
                VERSION="$2"
                shift 2
                ;;
            -r|--registry)
                DOCKER_REGISTRY="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            deploy|deploy-infra|deploy-apps|rollback|status|logs|cleanup)
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

# Validation functions
validate_prerequisites() {
    log_info "Validating prerequisites..."
    
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
    
    # Check if required files exist
    local required_files=(
        "${PROJECT_ROOT}/infrastructure/kubernetes/namespace.yaml"
        "${PROJECT_ROOT}/infrastructure/kubernetes/configmap.yaml"
        "${PROJECT_ROOT}/infrastructure/kubernetes/secrets.yaml"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Required file not found: $file"
            exit 1
        fi
    done
    
    log_success "Prerequisites validated"
}

# Update image tags in deployment files
update_image_tags() {
    log_info "Updating image tags to version: $VERSION"
    
    local temp_dir=$(mktemp -d)
    local k8s_dir="${PROJECT_ROOT}/infrastructure/kubernetes"
    
    # Copy kubernetes files to temp directory
    cp -r "$k8s_dir" "$temp_dir/"
    
    # Update image tags in deployment files
    local services=("ideas" "voting" "analytics" "decision")
    
    for service in "${services[@]}"; do
        local file="${temp_dir}/kubernetes/${service}-service.yaml"
        if [[ -f "$file" ]]; then
            sed -i.bak "s|image: mindmesh/${service}-service:latest|image: ${DOCKER_REGISTRY}/${service}-service:${VERSION}|g" "$file"
            log_info "Updated ${service}-service image tag"
        fi
    done
    
    export TEMP_K8S_DIR="${temp_dir}/kubernetes"
}

# Deploy infrastructure components
deploy_infrastructure() {
    log_info "Deploying infrastructure components..."
    
    # Create or update namespace
    kubectl apply -f "${TEMP_K8S_DIR}/namespace.yaml"
    
    # Apply configmaps and secrets
    kubectl apply -f "${TEMP_K8S_DIR}/configmap.yaml" -n "$NAMESPACE"
    kubectl apply -f "${TEMP_K8S_DIR}/secrets.yaml" -n "$NAMESPACE"
    
    # Deploy PostgreSQL
    log_info "Deploying PostgreSQL..."
    kubectl apply -f "${TEMP_K8S_DIR}/postgresql.yaml" -n "$NAMESPACE"
    kubectl rollout status deployment/postgresql -n "$NAMESPACE" --timeout="$KUBECTL_TIMEOUT"
    
    # Deploy Redis
    log_info "Deploying Redis..."
    kubectl apply -f "${TEMP_K8S_DIR}/redis.yaml" -n "$NAMESPACE"
    kubectl rollout status deployment/redis -n "$NAMESPACE" --timeout="$KUBECTL_TIMEOUT"
    
    log_success "Infrastructure components deployed successfully"
}

# Deploy application services
deploy_applications() {
    log_info "Deploying application services..."
    
    local services=("ideas-service" "voting-service" "analytics-service" "decision-service")
    
    for service in "${services[@]}"; do
        log_info "Deploying $service..."
        kubectl apply -f "${TEMP_K8S_DIR}/${service}.yaml" -n "$NAMESPACE"
    done
    
    # Wait for all deployments to be ready
    for service in "${services[@]}"; do
        log_info "Waiting for $service to be ready..."
        kubectl rollout status deployment/"$service" -n "$NAMESPACE" --timeout="$KUBECTL_TIMEOUT"
    done
    
    # Deploy ingress and HPA
    kubectl apply -f "${TEMP_K8S_DIR}/ingress.yaml" -n "$NAMESPACE"
    kubectl apply -f "${TEMP_K8S_DIR}/hpa.yaml" -n "$NAMESPACE"
    
    log_success "Application services deployed successfully"
}

# Full deployment
deploy_all() {
    log_info "Starting full deployment of MindMesh..."
    log_info "Environment: $ENVIRONMENT"
    log_info "Namespace: $NAMESPACE"
    log_info "Version: $VERSION"
    log_info "Registry: $DOCKER_REGISTRY"
    
    validate_prerequisites
    update_image_tags
    deploy_infrastructure
    deploy_applications
    
    log_success "MindMesh deployment completed successfully!"
    
    # Show deployment status
    show_status
}

# Rollback deployment
rollback_deployment() {
    log_info "Rolling back MindMesh deployment..."
    
    local services=("ideas-service" "voting-service" "analytics-service" "decision-service")
    
    for service in "${services[@]}"; do
        log_info "Rolling back $service..."
        kubectl rollout undo deployment/"$service" -n "$NAMESPACE"
        kubectl rollout status deployment/"$service" -n "$NAMESPACE" --timeout="$KUBECTL_TIMEOUT"
    done
    
    log_success "Rollback completed successfully"
}

# Show deployment status
show_status() {
    log_info "Deployment Status for namespace: $NAMESPACE"
    
    echo
    echo "=== Pods ==="
    kubectl get pods -n "$NAMESPACE" -o wide
    
    echo
    echo "=== Services ==="
    kubectl get svc -n "$NAMESPACE"
    
    echo
    echo "=== Ingress ==="
    kubectl get ingress -n "$NAMESPACE"
    
    echo
    echo "=== HPA ==="
    kubectl get hpa -n "$NAMESPACE"
    
    echo
    echo "=== PVC ==="
    kubectl get pvc -n "$NAMESPACE"
    
    # Check if all deployments are ready
    local services=("ideas-service" "voting-service" "analytics-service" "decision-service" "postgresql" "redis")
    local all_ready=true
    
    echo
    echo "=== Deployment Status ==="
    for service in "${services[@]}"; do
        if kubectl get deployment "$service" -n "$NAMESPACE" &> /dev/null; then
            local ready=$(kubectl get deployment "$service" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
            local desired=$(kubectl get deployment "$service" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
            
            if [[ "$ready" == "$desired" ]]; then
                log_success "$service: $ready/$desired replicas ready"
            else
                log_warning "$service: $ready/$desired replicas ready"
                all_ready=false
            fi
        else
            log_warning "$service: deployment not found"
            all_ready=false
        fi
    done
    
    if [[ "$all_ready" == true ]]; then
        log_success "All services are healthy and ready!"
    else
        log_warning "Some services are not fully ready"
    fi
}

# View logs
view_logs() {
    log_info "Application Logs for namespace: $NAMESPACE"
    
    local services=("ideas-service" "voting-service" "analytics-service" "decision-service")
    
    for service in "${services[@]}"; do
        echo
        echo "=== $service Logs ==="
        kubectl logs -l app="$service" -n "$NAMESPACE" --tail=50 --prefix=true || true
    done
}

# Cleanup resources
cleanup_resources() {
    local force="${1:-false}"
    
    if [[ "$force" != "true" ]]; then
        read -p "Are you sure you want to delete all resources in namespace '$NAMESPACE'? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Cleanup cancelled"
            return 0
        fi
    fi
    
    log_warning "Cleaning up resources in namespace: $NAMESPACE"
    
    # Delete application resources
    kubectl delete all --all -n "$NAMESPACE" || true
    
    # Delete PVCs
    kubectl delete pvc --all -n "$NAMESPACE" || true
    
    # Delete secrets and configmaps
    kubectl delete secrets --all -n "$NAMESPACE" || true
    kubectl delete configmaps --all -n "$NAMESPACE" || true
    
    # Delete namespace if it's not default namespaces
    if [[ "$NAMESPACE" != "default" && "$NAMESPACE" != "kube-system" && "$NAMESPACE" != "kube-public" ]]; then
        kubectl delete namespace "$NAMESPACE" || true
    fi
    
    log_success "Cleanup completed"
}

# Health check
health_check() {
    log_info "Performing health check..."
    
    local services=("ideas-service" "voting-service" "analytics-service" "decision-service")
    local healthy=true
    
    for service in "${services[@]}"; do
        if kubectl get deployment "$service" -n "$NAMESPACE" &> /dev/null; then
            local ready=$(kubectl get deployment "$service" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
            local desired=$(kubectl get deployment "$service" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
            
            if [[ "$ready" != "$desired" ]]; then
                log_warning "$service is not healthy: $ready/$desired replicas ready"
                healthy=false
            fi
        else
            log_error "$service deployment not found"
            healthy=false
        fi
    done
    
    if [[ "$healthy" == true ]]; then
        log_success "All services are healthy"
        return 0
    else
        log_error "Some services are unhealthy"
        return 1
    fi
}

# Cleanup function for temp files
cleanup_temp() {
    if [[ -n "${TEMP_K8S_DIR:-}" ]]; then
        rm -rf "$(dirname "$TEMP_K8S_DIR")"
    fi
}

# Trap to cleanup temp files on exit
trap cleanup_temp EXIT

# Main execution
main() {
    local command="${1:-deploy}"
    
    case "$command" in
        "deploy")
            deploy_all
            ;;
        "deploy-infra")
            validate_prerequisites
            update_image_tags
            deploy_infrastructure
            ;;
        "deploy-apps")
            validate_prerequisites
            update_image_tags
            deploy_applications
            ;;
        "rollback")
            rollback_deployment
            ;;
        "status")
            show_status
            ;;
        "logs")
            view_logs
            ;;
        "cleanup")
            cleanup_resources
            ;;
        "health")
            health_check
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Parse arguments and run main function
COMMAND="deploy"
parse_args "$@"
main "$COMMAND"