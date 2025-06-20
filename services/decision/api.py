"""API routes for Decision service."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import httpx

from .models import Decision, DecisionEvent, DecisionCriteria, DecisionTemplate, DecisionStatus, DecisionType
from .schemas import (
    DecisionCreate, DecisionUpdate, DecisionResponse, DecisionWithEvents,
    DecisionCriteriaCreate, DecisionCriteriaUpdate, DecisionCriteriaResponse,
    DecisionTemplateCreate, DecisionTemplateResponse,
    DecisionSuggestion, DecisionStats
)
from .events import DecisionEventHandlers, EventStore, EventProjections

# Import database dependencies
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DECISION_DATABASE_URL", "postgresql://user:password@localhost/decision_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

# External service URLs
IDEAS_SERVICE_URL = os.getenv("IDEAS_SERVICE_URL", "http://localhost:8001")
ANALYTICS_SERVICE_URL = os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8003")

# Security
security = HTTPBearer()

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Decode and validate JWT token."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "name": payload.get("name"),
            "roles": payload.get("roles", [])
        }
    except JWTError as e:
        logger.error(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


async def get_idea_metrics(idea_id: int, token: str) -> Dict[str, Any]:
    """Fetch idea metrics from analytics service."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ANALYTICS_SERVICE_URL}/api/v1/analytics/ideas/{idea_id}/metrics",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to fetch metrics for idea {idea_id}")
                return {}
    except Exception as e:
        logger.error(f"Error fetching idea metrics: {e}")
        return {}


@router.post("/", response_model=DecisionResponse, status_code=status.HTTP_201_CREATED)
async def create_decision(
    decision: DecisionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a new decision for an idea."""
    # Check if user has decision-making authority
    if "decision_maker" not in current_user["roles"] and "admin" not in current_user["roles"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create decisions"
        )
    
    # Fetch current idea metrics
    metrics = await get_idea_metrics(decision.idea_id, credentials.credentials)
    
    # Create decision
    db_decision = Decision(
        **decision.model_dump(),
        metrics_snapshot=metrics
    )
    db.add(db_decision)
    db.commit()
    db.refresh(db_decision)
    
    # Record creation event
    DecisionEventHandlers.on_decision_created(
        db=db,
        decision=db_decision,
        actor_id=current_user["user_id"],
        actor_name=current_user.get("name"),
        actor_role="decision_maker"
    )
    
    db.commit()
    
    logger.info(f"Created decision {db_decision.id} for idea {decision.idea_id}")
    return db_decision


@router.get("/", response_model=List[DecisionResponse])
async def list_decisions(
    status: Optional[DecisionStatus] = None,
    decision_type: Optional[DecisionType] = None,
    idea_id: Optional[int] = None,
    decided_by: Optional[str] = None,
    days_back: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """List decisions with filtering."""
    query = db.query(Decision)
    
    # Apply filters
    if status:
        query = query.filter(Decision.status == status)
    if decision_type:
        query = query.filter(Decision.decision_type == decision_type)
    if idea_id:
        query = query.filter(Decision.idea_id == idea_id)
    if decided_by:
        query = query.filter(Decision.decided_by == decided_by)
    
    # Time filter
    since_date = datetime.utcnow() - timedelta(days=days_back)
    query = query.filter(Decision.created_at >= since_date)
    
    # Order and limit
    decisions = query.order_by(Decision.created_at.desc()).limit(limit).all()
    
    # Add event count
    for decision in decisions:
        decision.events_count = len(decision.events)
    
    return decisions


@router.get("/{decision_id}", response_model=DecisionWithEvents)
async def get_decision(
    decision_id: int,
    include_events: bool = Query(True),
    db: Session = Depends(get_db)
):
    """Get a specific decision with optional event history."""
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    response = DecisionWithEvents.from_orm(decision)
    
    if include_events:
        response.events = decision.events
    
    return response


@router.patch("/{decision_id}", response_model=DecisionResponse)
async def update_decision(
    decision_id: int,
    update: DecisionUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a decision."""
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    # Check permissions
    if "decision_maker" not in current_user["roles"] and "admin" not in current_user["roles"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Track status change
    old_status = decision.status if update.status else None
    
    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(decision, field, value)
    
    # Handle status change event
    if old_status and update.status and old_status != update.status:
        DecisionEventHandlers.on_status_changed(
            db=db,
            decision=decision,
            old_status=old_status,
            new_status=update.status,
            actor_id=current_user["user_id"],
            actor_name=current_user.get("name"),
            actor_role="decision_maker"
        )
    
    # Handle implementation plan update
    if update.implementation_plan:
        DecisionEventHandlers.on_implementation_plan_updated(
            db=db,
            decision=decision,
            plan=update.implementation_plan,
            timeline_days=update.timeline_days,
            resource_requirements=update.resource_requirements or {},
            actor_id=current_user["user_id"],
            actor_name=current_user.get("name"),
            actor_role="decision_maker"
        )
    
    db.commit()
    db.refresh(decision)
    
    logger.info(f"Updated decision {decision_id}")
    return decision


@router.post("/{decision_id}/approve", response_model=DecisionResponse)
async def approve_decision(
    decision_id: int,
    reason: str = Query(..., min_length=10),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Approve a decision."""
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    if decision.status != DecisionStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve decision in {decision.status} status"
        )
    
    # Update status
    DecisionEventHandlers.on_status_changed(
        db=db,
        decision=decision,
        old_status=decision.status,
        new_status=DecisionStatus.APPROVED,
        actor_id=current_user["user_id"],
        actor_name=current_user.get("name"),
        actor_role="approver",
        reason=reason
    )
    
    db.commit()
    db.refresh(decision)
    
    return decision


@router.post("/{decision_id}/reject", response_model=DecisionResponse)
async def reject_decision(
    decision_id: int,
    reason: str = Query(..., min_length=10),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Reject a decision."""
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    if decision.status not in [DecisionStatus.PENDING, DecisionStatus.IN_REVIEW]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject decision in {decision.status} status"
        )
    
    # Update status
    DecisionEventHandlers.on_status_changed(
        db=db,
        decision=decision,
        old_status=decision.status,
        new_status=DecisionStatus.REJECTED,
        actor_id=current_user["user_id"],
        actor_name=current_user.get("name"),
        actor_role="reviewer",
        reason=reason
    )
    
    db.commit()
    db.refresh(decision)
    
    return decision


@router.get("/{decision_id}/timeline", response_model=List[Dict[str, Any]])
async def get_decision_timeline(
    decision_id: int,
    db: Session = Depends(get_db)
):
    """Get timeline of events for a decision."""
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    return EventProjections.get_decision_timeline(db, decision_id)


@router.get("/{decision_id}/audit", response_model=List[Dict[str, Any]])
async def get_decision_audit_trail(
    decision_id: int,
    event_types: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """Get audit trail for a decision."""
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    return EventProjections.get_decision_audit_trail(db, decision_id, event_types)


# Decision Criteria Management
@router.post("/criteria", response_model=DecisionCriteriaResponse)
async def create_criteria(
    criteria: DecisionCriteriaCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create new decision criteria."""
    if "admin" not in current_user["roles"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db_criteria = DecisionCriteria(**criteria.model_dump())
    db.add(db_criteria)
    db.commit()
    db.refresh(db_criteria)
    
    return db_criteria


@router.get("/criteria", response_model=List[DecisionCriteriaResponse])
async def list_criteria(
    active_only: bool = Query(True),
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List decision criteria."""
    query = db.query(DecisionCriteria)
    
    if active_only:
        query = query.filter(DecisionCriteria.is_active == True)
    if category:
        query = query.filter(DecisionCriteria.category == category)
    
    return query.all()


@router.get("/suggestions/{idea_id}", response_model=DecisionSuggestion)
async def get_decision_suggestion(
    idea_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get automated decision suggestion for an idea."""
    # Fetch idea metrics
    metrics = await get_idea_metrics(idea_id, credentials.credentials)
    
    if not metrics:
        raise HTTPException(
            status_code=404,
            detail="Unable to fetch idea metrics"
        )
    
    # Find matching criteria
    criteria_list = db.query(DecisionCriteria).filter(
        DecisionCriteria.is_active == True
    ).all()
    
    matching_criteria = []
    confidence_scores = []
    
    for criteria in criteria_list:
        score = 0
        matches = 0
        total_checks = 0
        
        # Check vote count
        if metrics.get("vote_count", 0) >= criteria.min_vote_count:
            score += 0.2
            matches += 1
        total_checks += 1
        
        # Check engagement score
        if metrics.get("engagement_score", 0) >= criteria.min_engagement_score:
            score += 0.2
            matches += 1
        total_checks += 1
        
        # Check average rating
        if metrics.get("average_rating", 0) >= criteria.min_average_rating:
            score += 0.2
            matches += 1
        total_checks += 1
        
        # Check controversy score
        if metrics.get("controversy_score", 1) <= criteria.max_controversy_score:
            score += 0.1
            matches += 1
        total_checks += 1
        
        # Check success probability (if available)
        if "success_probability" in metrics:
            if metrics["success_probability"] >= criteria.min_success_probability:
                score += 0.3
                matches += 1
            total_checks += 1
        
        if matches >= total_checks * 0.6:  # At least 60% criteria met
            matching_criteria.append(criteria.name)
            confidence_scores.append(score)
    
    if not matching_criteria:
        # Default suggestion
        return DecisionSuggestion(
            idea_id=idea_id,
            suggested_decision_type=DecisionType.DEFERRAL,
            confidence_score=0.3,
            matching_criteria=[],
            idea_metrics=metrics,
            rationale="Idea does not meet minimum criteria for implementation",
            auto_approve_eligible=False
        )
    
    # Select best matching criteria
    best_score = max(confidence_scores)
    best_criteria_idx = confidence_scores.index(best_score)
    best_criteria = criteria_list[best_criteria_idx]
    
    return DecisionSuggestion(
        idea_id=idea_id,
        suggested_decision_type=best_criteria.suggested_decision_type,
        confidence_score=best_score,
        matching_criteria=matching_criteria,
        idea_metrics=metrics,
        rationale=f"Idea meets criteria for {best_criteria.suggested_decision_type}",
        auto_approve_eligible=best_criteria.auto_approve and best_score > 0.8
    )


@router.get("/stats", response_model=DecisionStats)
async def get_decision_stats(
    days_back: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get decision statistics."""
    since_date = datetime.utcnow() - timedelta(days=days_back)
    
    # Total decisions
    total_decisions = db.query(func.count(Decision.id)).filter(
        Decision.created_at >= since_date
    ).scalar()
    
    # By status
    status_counts = db.query(
        Decision.status,
        func.count(Decision.id)
    ).filter(
        Decision.created_at >= since_date
    ).group_by(Decision.status).all()
    
    decisions_by_status = {status: count for status, count in status_counts}
    
    # By type
    type_counts = db.query(
        Decision.decision_type,
        func.count(Decision.id)
    ).filter(
        Decision.created_at >= since_date
    ).group_by(Decision.decision_type).all()
    
    decisions_by_type = {dtype: count for dtype, count in type_counts}
    
    # Average times
    avg_time_to_decision = db.query(
        func.avg(
            func.extract('epoch', Decision.decided_at - Decision.created_at) / 86400
        )
    ).filter(
        Decision.decided_at.isnot(None),
        Decision.created_at >= since_date
    ).scalar()
    
    avg_implementation_time = db.query(
        func.avg(
            func.extract('epoch', Decision.implemented_at - Decision.decided_at) / 86400
        )
    ).filter(
        Decision.implemented_at.isnot(None),
        Decision.created_at >= since_date
    ).scalar()
    
    # Recent decisions
    recent_decisions = db.query(Decision).order_by(
        Decision.created_at.desc()
    ).limit(10).all()
    
    return DecisionStats(
        total_decisions=total_decisions or 0,
        decisions_by_status=decisions_by_status,
        decisions_by_type=decisions_by_type,
        average_time_to_decision=avg_time_to_decision,
        average_implementation_time=avg_implementation_time,
        recent_decisions=recent_decisions
    )