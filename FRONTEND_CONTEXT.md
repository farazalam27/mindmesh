# MindMesh Frontend Development Context

## Overview
This file provides context for developing the MindMesh frontend in a separate repository. The frontend will be a modern TypeScript React application using Next.js 14.

## Backend Architecture Deep Dive

### System Overview
MindMesh backend is a microservices architecture with 4 main services:
1. **Ideas Service** (Port 8001) - Core idea management
2. **Voting Service** (Port 8002) - Real-time voting with Redis caching
3. **Decision Service** (Port 8003) - Decision tracking with event sourcing
4. **Analytics Service** (Foundation) - PySpark-based analytics (not fully implemented)

### Infrastructure Stack
- **Language**: Python 3.11
- **Framework**: FastAPI with async/await
- **Database**: PostgreSQL 15 (port 5433 in development)
- **Cache**: Redis 7 (port 6380 in development)  
- **Authentication**: JWT with role-based access
- **Container**: Docker & Docker Compose
- **Deployment**: Kubernetes (AWS EKS configurations included)

### Database Architecture

#### Ideas Service Database (PostgreSQL)
**Tables:**
- `ideas` - Core idea storage
  - id (PK), title, description, category, tags[], status, user_id, user_email, user_name
  - vote_count, average_rating, view_count, created_at, updated_at, published_at
- `comments` - User comments on ideas
  - id (PK), idea_id (FK), content, user_id, user_email, user_name, created_at

**Categories**: innovation, improvement, problem_solving, cost_saving, revenue_generation, other
**Statuses**: draft, active, implemented, rejected

#### Voting Service Database (PostgreSQL + Redis)
**PostgreSQL Tables:**
- `votes` - Individual vote records
  - id (PK), idea_id, user_id, vote_type (upvote/downvote), rating (1-5), created_at
- `vote_aggregates` - Cached voting statistics
  - idea_id (PK), upvote_count, downvote_count, total_votes, rating_count, average_rating, score, last_updated

**Redis Usage:**
- Rate limiting for votes (prevents spam)
- Real-time vote caching
- Session storage

#### Decision Service Database (PostgreSQL)
**Tables:**
- `decisions` - Core decision records
  - id (PK), decision_id (UUID), idea_id, decision_type, status, summary, rationale
  - conditions[], decided_by, decision_committee[], timeline_days
  - created_at, decided_at, implemented_at
- `decision_events` - Event sourcing for audit trails
  - id (PK), event_id (UUID), decision_id (FK), event_type, actor_id, occurred_at
- `decision_criteria` - Automated decision rules (not fully implemented)
- `decision_templates` - Reusable decision formats (not fully implemented)

**Decision Types**: implementation, rejection, modification, escalation, deferral
**Statuses**: pending, in_review, approved, rejected, implemented, on_hold

### Backend Service Details

#### Ideas Service (Port 8001)
**File Structure:**
- `main.py` - FastAPI app with lifespan management
- `api.py` - Router with JWT auth middleware
- `models.py` - SQLAlchemy models (Idea, Comment, IdeaStatus enum)
- `schemas.py` - Pydantic models for request/response validation
- `database.py` - Database session management and initialization

**Key Features:**
- Automatic database table creation on startup
- JWT authentication with role-based access
- Pagination and filtering for idea lists
- Full CRUD operations with proper validation
- User information embedded in responses (no separate user service)

#### Voting Service (Port 8002)
**File Structure:**
- `main.py` - FastAPI app with Redis health checks
- `api.py` - Voting endpoints with rate limiting
- `models.py` - Vote and VoteAggregate models
- `schemas.py` - Vote validation schemas
- `redis_client.py` - Redis connection and operations

**Key Features:**
- Rate limiting per user using Redis
- Real-time vote aggregation
- Prevents duplicate voting (one vote per user per idea)
- Redis caching for performance
- Vote statistics and analytics endpoints

#### Decision Service (Port 8003)
**File Structure:**
- `main.py` - FastAPI app with analytics integration attempts
- `api.py` - Decision CRUD with role-based permissions
- `models.py` - Decision, DecisionEvent, DecisionCriteria models
- `schemas.py` - Complex decision validation schemas
- `events.py` - Event sourcing for decision audit trails

**Key Features:**
- Event sourcing for complete audit trails
- Role-based permissions (decision_maker role required)
- Integration attempts with analytics service (returns 404)
- Complex decision workflows with conditions and timelines
- Automatic event logging for all decision changes

### Backend Security Implementation

#### JWT Authentication Details
**Token Structure:**
```json
{
  "user_id": "string",
  "email": "email@domain.com", 
  "name": "Full Name",
  "roles": ["role1", "role2"],
  "exp": 1234567890
}
```

**Security Features:**
- Bearer token authentication on all protected endpoints
- Role-based access control with middleware validation
- Token expiration handling
- Secret key loaded from environment variables

#### Environment Variables Required
```bash
# Core secrets (REQUIRED)
JWT_SECRET_KEY=your-super-secret-key-here-for-development
POSTGRES_PASSWORD=mindmesh123

# Database URLs (service-specific)
IDEAS_DATABASE_URL=postgresql://mindmesh:mindmesh123@localhost:5433/mindmesh
VOTING_DATABASE_URL=postgresql://mindmesh:mindmesh123@localhost:5433/mindmesh
DECISION_DATABASE_URL=postgresql://mindmesh:mindmesh123@localhost:5433/mindmesh
REDIS_URL=redis://localhost:6380
```

### Backend Startup Sequence

#### Development Mode Startup
```bash
# 1. Start infrastructure
docker-compose up -d  # Starts PostgreSQL + Redis

# 2. Set environment variables
export JWT_SECRET_KEY="your-super-secret-key-here-for-development"
export POSTGRES_PASSWORD="mindmesh123"
export IDEAS_DATABASE_URL=postgresql://mindmesh:mindmesh123@localhost:5433/mindmesh
export VOTING_DATABASE_URL=postgresql://mindmesh:mindmesh123@localhost:5433/mindmesh
export DECISION_DATABASE_URL=postgresql://mindmesh:mindmesh123@localhost:5433/mindmesh
export REDIS_URL=redis://localhost:6380

# 3. Start services (in separate terminals)
python -m uvicorn services.ideas.main:app --host 0.0.0.0 --port 8001
python -m uvicorn services.voting.main:app --host 0.0.0.0 --port 8002
python -m uvicorn services.decision.main:app --host 0.0.0.0 --port 8003
```

#### Health Check Endpoints
- Ideas: `GET http://localhost:8001/health`
- Voting: `GET http://localhost:8002/health` 
- Decision: `GET http://localhost:8003/health`

### Current Backend Status

#### Working Features (Tested)
- ✅ **Ideas CRUD**: Create, read, update, delete ideas
- ✅ **Voting System**: Upvote/downvote with aggregation
- ✅ **Decision Tracking**: Create and manage decisions
- ✅ **JWT Authentication**: Role-based access control
- ✅ **Health Monitoring**: Service health endpoints
- ✅ **Database Integration**: PostgreSQL with proper models
- ✅ **Redis Caching**: Vote aggregation and rate limiting

#### Foundation Implemented (Not Active)
- 🏗️ **Analytics Service**: PySpark structure exists but not functional
- 🏗️ **Event Streaming**: Kafka configs exist but not used
- 🏗️ **ML Models**: Placeholder code for clustering and prediction
- 🏗️ **Real-time Features**: WebSocket foundation not implemented

#### Known Issues
- Decision service tries to connect to analytics service (404 errors)
- Some vote aggregation edge cases
- No real-time WebSocket connections yet
- Analytics service not fully functional

### Test Data Generation

#### JWT Token Generation
Use `scripts/create_jwt_tokens.py` to generate test tokens:
```bash
export JWT_SECRET_KEY="your-super-secret-key-here-for-development"
python scripts/create_jwt_tokens.py
```

**Sample Users Available:**
1. **Alice Johnson** (alice@techcorp.com) - facilitator, admin
2. **Bob Smith** (bob@techcorp.com) - member  
3. **Carol Davis** (carol@techcorp.com) - decision_maker

#### API Testing Examples
```bash
# Get all ideas
curl http://localhost:8001/api/v1/ideas/

# Create idea (requires auth)
curl -X POST http://localhost:8001/api/v1/ideas/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Idea","description":"Test description","category":"innovation","tags":["test"]}'

# Vote on idea
curl -X POST http://localhost:8002/api/v1/votes/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"idea_id":1,"vote_type":"upvote"}'

# Create decision (decision_maker role required)
curl -X POST http://localhost:8003/api/v1/decisions/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"idea_id":1,"decision_type":"implementation","summary":"Approved for implementation","rationale":"Strong team support and clear value proposition"}'
```

## Backend API Integration

### Service Endpoints
- **Ideas API**: http://localhost:8001/api/v1/ideas
- **Voting API**: http://localhost:8002/api/v1/votes  
- **Decisions API**: http://localhost:8003/api/v1/decisions

### API Documentation
- **Ideas Swagger**: http://localhost:8001/docs
- **Voting Swagger**: http://localhost:8002/docs
- **Decisions Swagger**: http://localhost:8003/docs

## Authentication System

### JWT Authentication
- **Type**: Bearer tokens
- **Header**: `Authorization: Bearer <token>`
- **Secret**: Use environment variable `JWT_SECRET_KEY`
- **Algorithm**: HS256
- **Expiry**: 60 minutes (configurable)

### User Roles
1. **facilitator**: Can create/edit ideas, vote, create decisions
2. **member**: Can create/edit ideas, vote
3. **decision_maker**: Can create/edit ideas, vote, create/update decisions
4. **admin**: Full access (inherits facilitator permissions)

### Sample JWT Payload
```json
{
  "user_id": "user_001",
  "email": "alice@techcorp.com",
  "name": "Alice Johnson",
  "roles": ["facilitator", "admin"],
  "exp": 1234567890
}
```

## API Endpoints Reference

### Ideas Service (`/api/v1/ideas`)

#### Core Endpoints
- `GET /` - List ideas (paginated, filterable)
  - Query params: `page`, `page_size`, `sort_by`, `order`, `category`, `status`, `search`
- `POST /` - Create new idea (auth required)
- `GET /{id}` - Get specific idea
- `PUT /{id}` - Update idea (auth required)
- `DELETE /{id}` - Delete idea (auth required)

#### Request/Response Examples
```typescript
// Create Idea
interface IdeaCreate {
  title: string;
  description: string;
  category: 'innovation' | 'improvement' | 'problem_solving' | 'cost_saving' | 'revenue_generation' | 'other';
  tags: string[];
}

// Idea Response
interface IdeaResponse {
  id: number;
  title: string;
  description: string;
  category: string;
  tags: string[];
  status: 'draft' | 'active' | 'implemented' | 'rejected';
  user_id: string;
  user_email: string;
  user_name: string;
  vote_count: number;
  average_rating: number;
  view_count: number;
  created_at: string;
  updated_at: string | null;
  published_at: string | null;
  comments_count: number;
}
```

### Voting Service (`/api/v1/votes`)

#### Core Endpoints
- `POST /` - Cast vote (auth required)
- `DELETE /{idea_id}` - Remove vote (auth required)
- `GET /idea/{idea_id}/aggregate` - Get vote statistics
- `GET /stats` - Overall voting statistics

#### Request/Response Examples
```typescript
// Vote Creation
interface VoteCreate {
  idea_id: number;
  vote_type: 'upvote' | 'downvote';
  rating?: number; // 1-5 scale
}

// Vote Aggregate Response
interface VoteAggregateResponse {
  idea_id: number;
  upvote_count: number;
  downvote_count: number;
  total_votes: number;
  rating_count: number;
  average_rating: number;
  score: number;
  last_updated: string;
}
```

### Decision Service (`/api/v1/decisions`)

#### Core Endpoints
- `POST /` - Create decision (auth required, decision_maker role)
- `GET /` - List decisions
- `GET /{id}` - Get specific decision
- `PUT /{id}` - Update decision status

#### Request/Response Examples
```typescript
// Decision Creation
interface DecisionCreate {
  idea_id: number;
  decision_type: 'implementation' | 'rejection' | 'modification' | 'escalation' | 'deferral';
  summary: string; // 10-500 chars
  rationale: string; // min 20 chars
  conditions?: string[];
  timeline_days?: number;
}

// Decision Response
interface DecisionResponse {
  id: number;
  decision_id: string; // UUID
  idea_id: number;
  decision_type: string;
  status: 'pending' | 'in_review' | 'approved' | 'rejected' | 'implemented' | 'on_hold';
  summary: string;
  rationale: string;
  conditions: string[];
  timeline_days: number | null;
  created_at: string;
  decided_at: string | null;
  implemented_at: string | null;
  events_count: number;
}
```

## Frontend Technology Stack

### Recommended Stack
- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **State Management**: Zustand or TanStack Query
- **Authentication**: NextAuth.js or custom JWT handling
- **HTTP Client**: Axios with interceptors
- **Forms**: React Hook Form + Zod validation
- **Charts**: Chart.js or Recharts
- **Testing**: Jest + React Testing Library

### Project Structure
```
mindmesh-frontend/
├── src/
│   ├── app/                 # Next.js App Router pages
│   ├── components/          # Reusable UI components
│   │   ├── ui/             # shadcn/ui components
│   │   ├── forms/          # Form components
│   │   └── charts/         # Analytics visualizations
│   ├── hooks/              # Custom React hooks
│   ├── lib/                # Utilities and configurations
│   ├── services/           # API service layer
│   ├── stores/             # State management
│   ├── types/              # TypeScript type definitions
│   └── utils/              # Helper functions
├── public/                 # Static assets
└── tests/                  # Component and integration tests
```

## Key Features to Implement

### 1. Authentication Flow
- Login/Register forms
- JWT token storage and refresh
- Protected routes
- Role-based UI rendering

### 2. Ideas Management
- Ideas dashboard with filtering/search
- Create/edit idea forms with rich text
- Categories and tags management
- Comments system

### 3. Voting Interface
- Voting buttons with real-time updates
- Vote aggregation displays
- Rating system (1-5 stars)
- Voting history and statistics

### 4. Decision Tracking
- Decision creation workflow for decision makers
- Decision status timeline
- Conditions checklist tracking
- Implementation progress monitoring

### 5. Analytics Dashboard
- Charts showing ideas by category/status
- Voting trends over time
- User engagement metrics
- Decision success rates

## Development Workflow

### NEXT STEPS: Complete Setup Guide

#### Step 1: Create Frontend Repository
```bash
# 1. Create new repository on GitHub: mindmesh-frontend
# 2. Clone locally
cd ~/workspace/github.com/farazalam27/
git clone https://github.com/farazalam27/mindmesh-frontend.git
cd mindmesh-frontend/

# 3. Copy this context file
# (You'll move FRONTEND_CONTEXT.md here manually)
```

#### Step 2: Initialize Next.js Project
```bash
# Create Next.js project with all recommended settings
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"

# Install core dependencies
npm install axios zustand @hookform/react-hook-form zod @radix-ui/react-slot class-variance-authority clsx tailwind-merge lucide-react

# Install UI components (shadcn/ui)
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card input label textarea select checkbox radio-group

# Install chart libraries
npm install recharts chart.js react-chartjs-2

# Install development dependencies
npm install -D @types/node prettier prettier-plugin-tailwindcss
```

#### Step 3: Environment Setup
```bash
# Create environment file
cp .env.example .env.local
# Edit .env.local with actual values
```

#### Step 4: Initial Project Structure
```bash
# Create directory structure
mkdir -p src/{components/{ui,forms,charts,layout},hooks,lib,services,stores,types,utils}
mkdir -p src/app/{login,dashboard,ideas,voting,decisions,analytics}
```

#### Step 5: Start Development
```bash
# Start backend services (in mindmesh directory)
cd ../mindmesh/
docker-compose up -d
export JWT_SECRET_KEY="your-super-secret-key-here-for-development"
export POSTGRES_PASSWORD="mindmesh123"
# Start each service...

# Start frontend (in mindmesh-frontend directory)
cd ../mindmesh-frontend/
npm run dev
# Visit http://localhost:3000
```

### Environment Variables (.env.local)
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001
NEXT_PUBLIC_VOTING_API_URL=http://localhost:8002
NEXT_PUBLIC_DECISION_API_URL=http://localhost:8003
NEXTAUTH_SECRET=your-nextauth-secret
NEXTAUTH_URL=http://localhost:3000
```

### API Service Layer Example
```typescript
// lib/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL,
});

// JWT token interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('jwt_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const ideasApi = {
  getIdeas: (params?: IdeaFilters) => api.get('/api/v1/ideas', { params }),
  createIdea: (data: IdeaCreate) => api.post('/api/v1/ideas/', data),
  getIdea: (id: number) => api.get(`/api/v1/ideas/${id}`),
  updateIdea: (id: number, data: IdeaUpdate) => api.put(`/api/v1/ideas/${id}`, data),
};
```

## Development Notes

### CORS Configuration
The backend is configured to allow requests from `http://localhost:3000` (Next.js default port).

### Real-time Features
Consider implementing WebSocket connections for:
- Live voting updates
- Real-time notifications
- Live decision status changes

### Testing Strategy
- Unit tests for components and utilities
- Integration tests for API calls
- E2E tests for critical user flows
- Mock API responses for development

### Security Considerations
- Validate all user inputs
- Sanitize data before rendering
- Implement proper error handling
- Use HTTPS in production
- Secure JWT token storage

## Repository Structure Recommendation

Create separate repository: `mindmesh-frontend`
- Allows independent deployment cycles
- Clear separation of backend/frontend skills
- Technology-specific CI/CD pipelines
- Better portfolio showcase

Link to backend repository in README for complete project context.