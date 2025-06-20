#!/bin/bash

# MindMesh Database Initialization Script
# This script initializes the PostgreSQL database with required schemas, data, and configurations

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${NAMESPACE:-mindmesh}"
ENVIRONMENT="${ENVIRONMENT:-production}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-mindmesh}"
DB_USER="${DB_USER:-mindmesh_user}"
DB_PASSWORD="${DB_PASSWORD:-}"
FORCE_INIT="${FORCE_INIT:-false}"

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
MindMesh Database Initialization Script

Usage: $0 [OPTIONS] [COMMAND]

Commands:
    init            Initialize database (default)
    migrate         Run database migrations
    seed            Seed database with sample data
    reset           Reset database (DROP and recreate)
    status          Check database status
    backup          Create backup before initialization
    test            Test database connection

Options:
    -n, --namespace NS       Kubernetes namespace (default: mindmesh)
    -e, --environment ENV    Environment (default: production)
    -h, --host HOST         Database host (default: localhost)
    -p, --port PORT         Database port (default: 5432)
    -d, --database DB       Database name (default: mindmesh)
    -u, --user USER         Database user (default: mindmesh_user)
    -w, --password PASS     Database password
    -f, --force             Force initialization (overwrite existing)
    -k, --kubectl           Use kubectl to connect to database in cluster
    -v, --verbose           Verbose output
    --help                  Show this help message

Environment Variables:
    NAMESPACE       Kubernetes namespace
    ENVIRONMENT     Target environment
    DB_HOST         Database host
    DB_PORT         Database port
    DB_NAME         Database name
    DB_USER         Database user
    DB_PASSWORD     Database password
    FORCE_INIT      Force initialization

Examples:
    $0 init --environment production
    $0 migrate --kubectl --namespace mindmesh
    $0 seed --environment development --force
    $0 reset --host postgres.example.com --user admin

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
            -h|--host)
                DB_HOST="$2"
                shift 2
                ;;
            -p|--port)
                DB_PORT="$2"
                shift 2
                ;;
            -d|--database)
                DB_NAME="$2"
                shift 2
                ;;
            -u|--user)
                DB_USER="$2"
                shift 2
                ;;
            -w|--password)
                DB_PASSWORD="$2"
                shift 2
                ;;
            -f|--force)
                FORCE_INIT=true
                shift
                ;;
            -k|--kubectl)
                USE_KUBECTL=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            init|migrate|seed|reset|status|backup|test)
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

# Get database credentials from Kubernetes secrets
get_k8s_credentials() {
    if [[ "${USE_KUBECTL:-false}" == "true" ]]; then
        log_info "Getting database credentials from Kubernetes secrets..."
        
        # Check if kubectl is available
        if ! command -v kubectl &> /dev/null; then
            log_error "kubectl is not installed or not in PATH"
            exit 1
        fi
        
        # Get credentials from secrets
        DB_USER=$(kubectl get secret mindmesh-secrets -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_USER}' 2>/dev/null | base64 -d 2>/dev/null || echo "$DB_USER")
        DB_PASSWORD=$(kubectl get secret mindmesh-secrets -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_PASSWORD}' 2>/dev/null | base64 -d 2>/dev/null || echo "$DB_PASSWORD")
        DB_NAME=$(kubectl get configmap mindmesh-config -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_DB}' 2>/dev/null || echo "$DB_NAME")
        DB_HOST=$(kubectl get configmap mindmesh-config -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_HOST}' 2>/dev/null || echo "$DB_HOST")
        DB_PORT=$(kubectl get configmap mindmesh-config -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_PORT}' 2>/dev/null || echo "$DB_PORT")
        
        log_success "Retrieved database credentials from Kubernetes"
    fi
}

# Get PostgreSQL pod for kubectl exec
get_postgres_pod() {
    local postgres_pod=$(kubectl get pods -n "$NAMESPACE" -l app=postgresql -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -z "$postgres_pod" ]]; then
        log_error "PostgreSQL pod not found in namespace: $NAMESPACE"
        exit 1
    fi
    
    echo "$postgres_pod"
}

# Execute SQL command
execute_sql() {
    local sql="$1"
    local database="${2:-$DB_NAME}"
    
    if [[ "${USE_KUBECTL:-false}" == "true" ]]; then
        local postgres_pod=$(get_postgres_pod)
        kubectl exec -n "$NAMESPACE" "$postgres_pod" -- psql -U "$DB_USER" -d "$database" -c "$sql"
    else
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$database" -c "$sql"
    fi
}

# Execute SQL file
execute_sql_file() {
    local file="$1"
    local database="${2:-$DB_NAME}"
    
    if [[ ! -f "$file" ]]; then
        log_error "SQL file not found: $file"
        return 1
    fi
    
    if [[ "${USE_KUBECTL:-false}" == "true" ]]; then
        local postgres_pod=$(get_postgres_pod)
        kubectl exec -i -n "$NAMESPACE" "$postgres_pod" -- psql -U "$DB_USER" -d "$database" < "$file"
    else
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$database" -f "$file"
    fi
}

# Test database connection
test_connection() {
    log_info "Testing database connection..."
    
    if execute_sql "SELECT 1;" "postgres" &>/dev/null; then
        log_success "Database connection successful"
        return 0
    else
        log_error "Database connection failed"
        return 1
    fi
}

# Check if database exists
database_exists() {
    local exists=$(execute_sql "SELECT 1 FROM pg_database WHERE datname='$DB_NAME';" "postgres" 2>/dev/null | grep -c "1" || echo "0")
    [[ "$exists" -gt 0 ]]
}

# Check if tables exist
tables_exist() {
    local count=$(execute_sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | grep -E '^[0-9]+$' || echo "0")
    [[ "$count" -gt 0 ]]
}

# Create database schema
create_schema() {
    log_info "Creating database schema..."
    
    # Users table
    execute_sql "
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        username VARCHAR(100) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        first_name VARCHAR(100),
        last_name VARCHAR(100),
        avatar_url VARCHAR(500),
        role VARCHAR(50) DEFAULT 'user',
        is_active BOOLEAN DEFAULT true,
        email_verified BOOLEAN DEFAULT false,
        last_login TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"
    
    # Organizations table
    execute_sql "
    CREATE TABLE IF NOT EXISTS organizations (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        slug VARCHAR(100) UNIQUE NOT NULL,
        logo_url VARCHAR(500),
        website VARCHAR(255),
        is_active BOOLEAN DEFAULT true,
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"
    
    # Organization members table
    execute_sql "
    CREATE TABLE IF NOT EXISTS organization_members (
        id SERIAL PRIMARY KEY,
        organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        role VARCHAR(50) DEFAULT 'member',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(organization_id, user_id)
    );"
    
    # Ideas table
    execute_sql "
    CREATE TABLE IF NOT EXISTS ideas (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        content TEXT,
        category VARCHAR(100),
        tags TEXT[],
        status VARCHAR(50) DEFAULT 'draft',
        visibility VARCHAR(50) DEFAULT 'public',
        priority INTEGER DEFAULT 0,
        estimated_effort INTEGER,
        estimated_impact INTEGER,
        organization_id INTEGER REFERENCES organizations(id),
        created_by INTEGER REFERENCES users(id),
        assigned_to INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        published_at TIMESTAMP,
        due_date TIMESTAMP
    );"
    
    # Votes table
    execute_sql "
    CREATE TABLE IF NOT EXISTS votes (
        id SERIAL PRIMARY KEY,
        idea_id INTEGER REFERENCES ideas(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        vote_type VARCHAR(20) NOT NULL,
        weight INTEGER DEFAULT 1,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(idea_id, user_id)
    );"
    
    # Comments table
    execute_sql "
    CREATE TABLE IF NOT EXISTS comments (
        id SERIAL PRIMARY KEY,
        idea_id INTEGER REFERENCES ideas(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        parent_id INTEGER REFERENCES comments(id),
        content TEXT NOT NULL,
        is_edited BOOLEAN DEFAULT false,
        is_deleted BOOLEAN DEFAULT false,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"
    
    # Attachments table
    execute_sql "
    CREATE TABLE IF NOT EXISTS attachments (
        id SERIAL PRIMARY KEY,
        idea_id INTEGER REFERENCES ideas(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id),
        filename VARCHAR(255) NOT NULL,
        original_name VARCHAR(255) NOT NULL,
        file_size INTEGER,
        mime_type VARCHAR(100),
        file_path VARCHAR(500),
        url VARCHAR(500),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"
    
    # Decision sessions table
    execute_sql "
    CREATE TABLE IF NOT EXISTS decision_sessions (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        session_type VARCHAR(50) DEFAULT 'voting',
        status VARCHAR(50) DEFAULT 'active',
        organization_id INTEGER REFERENCES organizations(id),
        created_by INTEGER REFERENCES users(id),
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        voting_deadline TIMESTAMP,
        min_participants INTEGER DEFAULT 1,
        max_participants INTEGER,
        settings JSONB,
        results JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"
    
    # Session participants table
    execute_sql "
    CREATE TABLE IF NOT EXISTS session_participants (
        id SERIAL PRIMARY KEY,
        session_id INTEGER REFERENCES decision_sessions(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        role VARCHAR(50) DEFAULT 'participant',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, user_id)
    );"
    
    # Session ideas table
    execute_sql "
    CREATE TABLE IF NOT EXISTS session_ideas (
        id SERIAL PRIMARY KEY,
        session_id INTEGER REFERENCES decision_sessions(id) ON DELETE CASCADE,
        idea_id INTEGER REFERENCES ideas(id) ON DELETE CASCADE,
        order_index INTEGER DEFAULT 0,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, idea_id)
    );"
    
    # Analytics events table
    execute_sql "
    CREATE TABLE IF NOT EXISTS analytics_events (
        id SERIAL PRIMARY KEY,
        event_type VARCHAR(100) NOT NULL,
        event_name VARCHAR(100) NOT NULL,
        user_id INTEGER REFERENCES users(id),
        organization_id INTEGER REFERENCES organizations(id),
        idea_id INTEGER REFERENCES ideas(id),
        session_id INTEGER REFERENCES decision_sessions(id),
        properties JSONB,
        metadata JSONB,
        ip_address INET,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"
    
    # Notifications table
    execute_sql "
    CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        type VARCHAR(50) NOT NULL,
        title VARCHAR(255) NOT NULL,
        message TEXT,
        data JSONB,
        is_read BOOLEAN DEFAULT false,
        is_email_sent BOOLEAN DEFAULT false,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        read_at TIMESTAMP
    );"
    
    log_success "Database schema created successfully"
}

# Create indexes for performance
create_indexes() {
    log_info "Creating database indexes..."
    
    execute_sql "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);"
    
    execute_sql "CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_organizations_active ON organizations(is_active);"
    
    execute_sql "CREATE INDEX IF NOT EXISTS idx_ideas_organization ON ideas(organization_id);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_ideas_created_by ON ideas(created_by);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_ideas_category ON ideas(category);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_ideas_created_at ON ideas(created_at);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_ideas_tags ON ideas USING GIN(tags);"
    
    execute_sql "CREATE INDEX IF NOT EXISTS idx_votes_idea ON votes(idea_id);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_votes_user ON votes(user_id);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_votes_type ON votes(vote_type);"
    
    execute_sql "CREATE INDEX IF NOT EXISTS idx_comments_idea ON comments(idea_id);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_comments_user ON comments(user_id);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_id);"
    
    execute_sql "CREATE INDEX IF NOT EXISTS idx_attachments_idea ON attachments(idea_id);"
    
    execute_sql "CREATE INDEX IF NOT EXISTS idx_decision_sessions_org ON decision_sessions(organization_id);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_decision_sessions_status ON decision_sessions(status);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_decision_sessions_created_by ON decision_sessions(created_by);"
    
    execute_sql "CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_analytics_events_user ON analytics_events(user_id);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_analytics_events_org ON analytics_events(organization_id);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at ON analytics_events(created_at);"
    
    execute_sql "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);"
    execute_sql "CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(user_id, is_read);"
    
    log_success "Database indexes created successfully"
}

# Create database functions and triggers
create_functions() {
    log_info "Creating database functions and triggers..."
    
    # Updated timestamp trigger function
    execute_sql "
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS \$\$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    \$\$ language 'plpgsql';"
    
    # Create triggers for updated_at columns
    local tables_with_updated_at=("users" "organizations" "ideas" "votes" "comments" "decision_sessions")
    
    for table in "${tables_with_updated_at[@]}"; do
        execute_sql "
        DROP TRIGGER IF EXISTS update_${table}_updated_at ON ${table};
        CREATE TRIGGER update_${table}_updated_at
            BEFORE UPDATE ON ${table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();"
    done
    
    # Idea scoring function
    execute_sql "
    CREATE OR REPLACE FUNCTION calculate_idea_score(idea_id_param INTEGER)
    RETURNS NUMERIC AS \$\$
    DECLARE
        upvotes INTEGER := 0;
        downvotes INTEGER := 0;
        score NUMERIC := 0;
    BEGIN
        SELECT 
            COUNT(CASE WHEN vote_type = 'upvote' THEN 1 END),
            COUNT(CASE WHEN vote_type = 'downvote' THEN 1 END)
        INTO upvotes, downvotes
        FROM votes 
        WHERE idea_id = idea_id_param;
        
        score := upvotes - downvotes;
        RETURN score;
    END;
    \$\$ LANGUAGE plpgsql;"
    
    log_success "Database functions and triggers created successfully"
}

# Seed database with sample data
seed_database() {
    log_info "Seeding database with sample data..."
    
    # Create default admin user
    execute_sql "
    INSERT INTO users (email, username, password_hash, first_name, last_name, role, email_verified)
    VALUES (
        'admin@mindmesh.com',
        'admin',
        '\$2b\$10\$rKwKxnm.8EGdTh0o8Q2OU.ZQkj.VzxjXvAK.NZj6GQxf8Rn4K5n.a', -- password: admin123
        'System',
        'Administrator',
        'admin',
        true
    ) ON CONFLICT (email) DO NOTHING;"
    
    # Create default organization
    execute_sql "
    INSERT INTO organizations (name, description, slug, created_by)
    VALUES (
        'MindMesh Demo',
        'Default organization for demonstrating MindMesh features',
        'mindmesh-demo',
        1
    ) ON CONFLICT (slug) DO NOTHING;"
    
    # Add admin to organization
    execute_sql "
    INSERT INTO organization_members (organization_id, user_id, role)
    VALUES (1, 1, 'admin')
    ON CONFLICT (organization_id, user_id) DO NOTHING;"
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        log_info "Adding development sample data..."
        
        # Create sample users
        execute_sql "
        INSERT INTO users (email, username, password_hash, first_name, last_name, email_verified)
        VALUES 
            ('john@example.com', 'john_doe', '\$2b\$10\$rKwKxnm.8EGdTh0o8Q2OU.ZQkj.VzxjXvAK.NZj6GQxf8Rn4K5n.a', 'John', 'Doe', true),
            ('jane@example.com', 'jane_smith', '\$2b\$10\$rKwKxnm.8EGdTh0o8Q2OU.ZQkj.VzxjXvAK.NZj6GQxf8Rn4K5n.a', 'Jane', 'Smith', true),
            ('bob@example.com', 'bob_wilson', '\$2b\$10\$rKwKxnm.8EGdTh0o8Q2OU.ZQkj.VzxjXvAK.NZj6GQxf8Rn4K5n.a', 'Bob', 'Wilson', true)
        ON CONFLICT (email) DO NOTHING;"
        
        # Add sample users to organization
        execute_sql "
        INSERT INTO organization_members (organization_id, user_id, role)
        VALUES 
            (1, 2, 'member'),
            (1, 3, 'member'),
            (1, 4, 'member')
        ON CONFLICT (organization_id, user_id) DO NOTHING;"
        
        # Create sample ideas
        execute_sql "
        INSERT INTO ideas (title, description, content, category, tags, status, organization_id, created_by)
        VALUES 
            (
                'Implement Dark Mode',
                'Add dark mode theme to improve user experience in low-light environments',
                'We should implement a dark mode theme that users can toggle. This will help reduce eye strain and improve usability in dark environments.',
                'UI/UX',
                ARRAY['ui', 'theme', 'accessibility'],
                'published',
                1,
                2
            ),
            (
                'Mobile App Development',
                'Create mobile applications for iOS and Android',
                'Develop native mobile applications to extend our platform reach and provide better mobile user experience.',
                'Development',
                ARRAY['mobile', 'ios', 'android'],
                'published',
                1,
                3
            ),
            (
                'AI-Powered Idea Suggestions',
                'Use AI to suggest relevant ideas based on user preferences',
                'Implement machine learning algorithms to analyze user behavior and suggest ideas that might be of interest.',
                'AI/ML',
                ARRAY['ai', 'ml', 'suggestions'],
                'draft',
                1,
                4
            )
        ON CONFLICT DO NOTHING;"
        
        # Create sample votes
        execute_sql "
        INSERT INTO votes (idea_id, user_id, vote_type, comment)
        VALUES 
            (1, 1, 'upvote', 'Great idea! This would really help.'),
            (1, 3, 'upvote', 'Definitely needed.'),
            (1, 4, 'upvote', 'I support this.'),
            (2, 1, 'upvote', 'Mobile apps are essential.'),
            (2, 2, 'upvote', 'This will expand our reach.'),
            (3, 1, 'downvote', 'Might be too complex for now.')
        ON CONFLICT (idea_id, user_id) DO NOTHING;"
        
        # Create sample comments
        execute_sql "
        INSERT INTO comments (idea_id, user_id, content)
        VALUES 
            (1, 1, 'We should consider implementing this with CSS custom properties for easy theme switching.'),
            (1, 4, 'What about system preference detection?'),
            (2, 1, 'Should we go native or use React Native?'),
            (2, 3, 'React Native might be more cost-effective.')
        ON CONFLICT DO NOTHING;"
        
        log_success "Development sample data added"
    fi
    
    log_success "Database seeded successfully"
}

# Create database views for analytics
create_views() {
    log_info "Creating database views..."
    
    # Idea statistics view
    execute_sql "
    CREATE OR REPLACE VIEW idea_stats AS
    SELECT 
        i.id,
        i.title,
        i.category,
        i.status,
        i.created_at,
        COUNT(v.id) as total_votes,
        COUNT(CASE WHEN v.vote_type = 'upvote' THEN 1 END) as upvotes,
        COUNT(CASE WHEN v.vote_type = 'downvote' THEN 1 END) as downvotes,
        COUNT(c.id) as comment_count,
        calculate_idea_score(i.id) as score
    FROM ideas i
    LEFT JOIN votes v ON i.id = v.idea_id
    LEFT JOIN comments c ON i.id = c.idea_id AND c.is_deleted = false
    GROUP BY i.id, i.title, i.category, i.status, i.created_at;"
    
    # User activity view
    execute_sql "
    CREATE OR REPLACE VIEW user_activity AS
    SELECT 
        u.id,
        u.username,
        u.email,
        COUNT(DISTINCT i.id) as ideas_created,
        COUNT(DISTINCT v.id) as votes_cast,
        COUNT(DISTINCT c.id) as comments_made,
        MAX(ae.created_at) as last_activity
    FROM users u
    LEFT JOIN ideas i ON u.id = i.created_by
    LEFT JOIN votes v ON u.id = v.user_id
    LEFT JOIN comments c ON u.id = c.user_id AND c.is_deleted = false
    LEFT JOIN analytics_events ae ON u.id = ae.user_id
    GROUP BY u.id, u.username, u.email;"
    
    # Organization analytics view
    execute_sql "
    CREATE OR REPLACE VIEW organization_analytics AS
    SELECT 
        o.id,
        o.name,
        o.slug,
        COUNT(DISTINCT om.user_id) as member_count,
        COUNT(DISTINCT i.id) as total_ideas,
        COUNT(DISTINCT CASE WHEN i.status = 'published' THEN i.id END) as published_ideas,
        COUNT(DISTINCT ds.id) as decision_sessions,
        AVG(calculate_idea_score(i.id)) as avg_idea_score
    FROM organizations o
    LEFT JOIN organization_members om ON o.id = om.organization_id
    LEFT JOIN ideas i ON o.id = i.organization_id
    LEFT JOIN decision_sessions ds ON o.id = ds.organization_id
    GROUP BY o.id, o.name, o.slug;"
    
    log_success "Database views created successfully"
}

# Check database status
check_status() {
    log_info "Checking database status..."
    
    if ! test_connection; then
        return 1
    fi
    
    if database_exists; then
        log_success "Database '$DB_NAME' exists"
        
        if tables_exist; then
            local table_count=$(execute_sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" | grep -E '^[0-9]+$' || echo "0")
            log_success "Found $table_count tables"
            
            # Check key tables
            local key_tables=("users" "organizations" "ideas" "votes" "comments")
            for table in "${key_tables[@]}"; do
                local exists=$(execute_sql "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='$table');" | grep -o 't\|f')
                if [[ "$exists" == "t" ]]; then
                    local count=$(execute_sql "SELECT COUNT(*) FROM $table;" | grep -E '^[0-9]+$' || echo "0")
                    log_success "$table: $count records"
                else
                    log_error "$table: table not found"
                fi
            done
        else
            log_warning "Database exists but no tables found"
        fi
    else
        log_warning "Database '$DB_NAME' does not exist"
    fi
    
    # Check database version
    local db_version=$(execute_sql "SELECT version();" "postgres" | head -1 || echo "Unknown")
    log_info "PostgreSQL version: $db_version"
}

# Create backup before initialization
create_backup() {
    if database_exists && tables_exist; then
        log_info "Creating backup before initialization..."
        
        local backup_file="${PROJECT_ROOT}/backups/pre-init-backup-$(date +%Y%m%d-%H%M%S).sql"
        mkdir -p "$(dirname "$backup_file")"
        
        if [[ "${USE_KUBECTL:-false}" == "true" ]]; then
            local postgres_pod=$(get_postgres_pod)
            kubectl exec -n "$NAMESPACE" "$postgres_pod" -- pg_dump -U "$DB_USER" -d "$DB_NAME" --no-password > "$backup_file"
        else
            PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$backup_file"
        fi
        
        if [[ -s "$backup_file" ]]; then
            log_success "Backup created: $backup_file"
        else
            log_error "Backup creation failed"
            rm -f "$backup_file"
            return 1
        fi
    fi
}

# Initialize database
initialize_database() {
    log_info "Initializing MindMesh database..."
    log_info "Environment: $ENVIRONMENT"
    log_info "Database: $DB_NAME"
    log_info "Host: $DB_HOST:$DB_PORT"
    log_info "User: $DB_USER"
    
    # Test connection first
    if ! test_connection; then
        log_error "Cannot connect to database"
        exit 1
    fi
    
    # Create database if it doesn't exist
    if ! database_exists; then
        log_info "Creating database '$DB_NAME'..."
        execute_sql "CREATE DATABASE \"$DB_NAME\";" "postgres"
        log_success "Database created"
    else
        if tables_exist && [[ "$FORCE_INIT" != "true" ]]; then
            log_error "Database already initialized. Use --force to reinitialize"
            exit 1
        fi
        
        if [[ "$FORCE_INIT" == "true" ]]; then
            create_backup
            log_warning "Force initialization - dropping existing tables..."
            execute_sql "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
        fi
    fi
    
    # Create schema and populate
    create_schema
    create_indexes
    create_functions
    create_views
    seed_database
    
    log_success "Database initialization completed successfully!"
    
    # Show final status
    check_status
}

# Reset database
reset_database() {
    log_warning "This will completely reset the database and all data will be lost!"
    read -p "Are you sure you want to continue? Type 'yes' to confirm: " -r
    
    if [[ "$REPLY" != "yes" ]]; then
        log_info "Reset cancelled"
        return 0
    fi
    
    log_info "Resetting database..."
    
    if database_exists; then
        create_backup
        execute_sql "DROP DATABASE IF EXISTS \"$DB_NAME\";" "postgres"
        log_success "Database dropped"
    fi
    
    FORCE_INIT=true
    initialize_database
}

# Run migrations
run_migrations() {
    log_info "Running database migrations..."
    
    # Create migrations table if it doesn't exist
    execute_sql "
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(255) PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"
    
    # Check for migration files
    local migration_dir="${PROJECT_ROOT}/database/migrations"
    
    if [[ -d "$migration_dir" ]]; then
        local migration_files=($(find "$migration_dir" -name "*.sql" | sort))
        
        for migration_file in "${migration_files[@]}"; do
            local migration_name=$(basename "$migration_file" .sql)
            
            # Check if migration already applied
            local applied=$(execute_sql "SELECT COUNT(*) FROM schema_migrations WHERE version='$migration_name';" | grep -E '^[0-9]+$' || echo "0")
            
            if [[ "$applied" -eq 0 ]]; then
                log_info "Applying migration: $migration_name"
                execute_sql_file "$migration_file"
                execute_sql "INSERT INTO schema_migrations (version) VALUES ('$migration_name');"
                log_success "Migration applied: $migration_name"
            else
                log_info "Migration already applied: $migration_name"
            fi
        done
    else
        log_info "No migration directory found: $migration_dir"
    fi
    
    log_success "Migrations completed"
}

# Main execution function
main() {
    local command="${1:-init}"
    
    get_k8s_credentials
    
    # Validate required parameters
    if [[ -z "$DB_PASSWORD" && "${USE_KUBECTL:-false}" != "true" ]]; then
        log_error "Database password not provided. Use --password option or set DB_PASSWORD environment variable"
        exit 1
    fi
    
    case "$command" in
        "init")
            initialize_database
            ;;
        "migrate")
            run_migrations
            ;;
        "seed")
            seed_database
            ;;
        "reset")
            reset_database
            ;;
        "status")
            check_status
            ;;
        "backup")
            create_backup
            ;;
        "test")
            test_connection
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Parse arguments and run main function
COMMAND="init"
VERBOSE=false
USE_KUBECTL=false
parse_args "$@"
main "$COMMAND"