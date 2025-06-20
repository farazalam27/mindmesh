# MindMesh Frontend Development Context

## Overview
This file provides context for developing the MindMesh frontend in a separate repository. The frontend will be a modern TypeScript React application using Next.js 14.

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

### Environment Setup
```bash
# 1. Create Next.js project
npx create-next-app@latest mindmesh-frontend --typescript --tailwind --eslint --app

# 2. Install additional dependencies
npm install axios zustand @hookform/react-hook-form zod @radix-ui/react-* 

# 3. Set up environment variables
cp .env.example .env.local
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