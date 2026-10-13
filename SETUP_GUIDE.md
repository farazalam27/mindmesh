# MindMesh Backend Setup Guide

## Quick Start (Simplified)

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Git

### 1. Clone and Setup
```bash
git clone <your-repo-url>
cd mindmesh
pip install -r requirements.txt
```

### 2. Start All Services (One Command)
```bash
python start_services_simple.py
```

This will:
- Start PostgreSQL and Redis containers
- Start all 4 microservices
- Run health checks
- Show service URLs and documentation links

### 3. Access Services
- **Ideas Service**: http://localhost:8001/docs
- **Voting Service**: http://localhost:8002/docs  
- **Decision Service**: http://localhost:8003/docs
- **Analytics Service**: http://localhost:8004/docs

### 4. Stop Services
Press `Ctrl+C` in the terminal running the startup script.

---

## Manual Setup (Advanced)

### 1. Environment Configuration
The `.env` file is already configured with:
- Database URLs for all services
- JWT authentication settings
- CORS origins (includes GitHub Pages)
- Service URLs

### 2. Start Infrastructure Only
```bash
docker-compose up -d postgres redis
```

### 3. Start Individual Services
```bash
# Ideas Service
cd ideas_service && uvicorn main:app --port 8001 --reload

# Voting Service  
cd voting_service && uvicorn main:app --port 8002 --reload

# Decision Service
cd decision_service && uvicorn main:app --port 8003 --reload

# Analytics Service
cd analytics_service && uvicorn main:app --port 8004 --reload
```

---

## Database Setup

### Initial Migration
```bash
# Run from the root directory
python -c "
from ideas_service.database import engine, Base
Base.metadata.create_all(bind=engine)
print('Ideas service database initialized')
"

python -c "
from voting_service.database import engine, Base  
Base.metadata.create_all(bind=engine)
print('Voting service database initialized')
"

python -c "
from decision_service.database import engine, Base
Base.metadata.create_all(bind=engine)
print('Decision service database initialized')
"
```

### Reset Database
```bash
docker-compose down -v  # Remove volumes
docker-compose up -d postgres redis
# Re-run migration commands above
```

---

## Configuration Details

### Environment Variables
- `DATABASE_URL`: Main PostgreSQL connection
- `REDIS_URL`: Redis connection for caching
- `JWT_SECRET_KEY`: Change in production!
- `CORS_ORIGINS`: Includes GitHub Pages domain

### Service Ports
- Ideas: 8001
- Voting: 8002  
- Decision: 8003
- Analytics: 8004

### Database Schema
Each service manages its own tables in a shared PostgreSQL database:
- Ideas: `ideas`, `comments`
- Voting: `votes` 
- Decision: `decisions`
- Analytics: Uses views across all tables

---

## Troubleshooting

### "Port already in use"
```bash
# Find and kill processes using ports 8001-8004
lsof -ti:8001,8002,8003,8004 | xargs kill -9
```

### "Database connection failed"
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres
```

### "Redis connection failed"  
```bash
# Check if Redis is running
docker-compose ps redis

# View Redis logs
docker-compose logs redis
```

### Services won't start
```bash
# Check Python dependencies
pip install -r requirements.txt

# Check if in correct directory
ls ideas_service voting_service  # Should see these directories
```

---

## Development Tips

### API Testing
Each service has Swagger documentation at `/docs` endpoint:
- http://localhost:8001/docs (Ideas)
- http://localhost:8002/docs (Voting)
- http://localhost:8003/docs (Decision)  
- http://localhost:8004/docs (Analytics)

### Health Checks
All services have health endpoints:
- http://localhost:8001/health
- http://localhost:8002/health
- http://localhost:8003/health
- http://localhost:8004/health

### Database Access
```bash
# Connect to PostgreSQL
docker exec -it mindmesh-postgres-1 psql -U mindmesh -d mindmesh

# Common queries
\dt  # List tables
SELECT * FROM ideas LIMIT 5;
SELECT * FROM votes LIMIT 5;
```

### Logs
```bash
# View all container logs
docker-compose logs

# View specific service logs  
docker-compose logs postgres
docker-compose logs redis
```

---

## Production Notes

### Security
- Change `JWT_SECRET_KEY` in production
- Use strong database passwords
- Enable SSL/TLS for database connections
- Restrict CORS origins to your domain only

### Performance
- Configure PostgreSQL connection pooling
- Set up Redis clustering for high availability
- Use reverse proxy (nginx) for load balancing
- Monitor service health and metrics

### Deployment
- Use proper secrets management
- Set up automated backups
- Configure monitoring and alerting
- Use container orchestration (Kubernetes/Docker Swarm)