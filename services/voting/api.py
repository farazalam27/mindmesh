"""API routes for Voting service."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
import logging
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

from .models import Vote, VoteAggregate, VoteType
from .schemas import (
    VoteCreate, VoteUpdate, VoteResponse, VoteAggregateResponse,
    UserVoteStatus, BulkVoteStatus, BulkVoteStatusResponse,
    VoteStatsResponse, RateLimitInfo
)
from .redis_client import redis_client

# Import database dependencies (should be similar to ideas service)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("VOTING_DATABASE_URL", "postgresql://user:password@localhost/voting_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

# Rate limiting configuration
VOTE_RATE_LIMIT = int(os.getenv("VOTE_RATE_LIMIT", "10"))  # votes per minute
VOTE_RATE_WINDOW = int(os.getenv("VOTE_RATE_WINDOW", "60"))  # seconds

# Security
security = HTTPBearer()

router = APIRouter(prefix="/api/v1/votes", tags=["voting"])


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
            "roles": payload.get("roles", [])
        }
    except JWTError as e:
        logger.error(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


async def check_rate_limit(user_id: str, request: Request) -> RateLimitInfo:
    """Check rate limit for voting."""
    key = f"vote_limit:{user_id}"
    is_allowed, remaining = redis_client.rate_limit_check(
        key, VOTE_RATE_LIMIT, VOTE_RATE_WINDOW
    )
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Vote rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(VOTE_RATE_LIMIT),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(datetime.utcnow().timestamp()) + VOTE_RATE_WINDOW)
            }
        )
    
    return RateLimitInfo(
        limit=VOTE_RATE_LIMIT,
        remaining=remaining,
        reset_time=datetime.utcnow() + timedelta(seconds=VOTE_RATE_WINDOW),
        window_seconds=VOTE_RATE_WINDOW
    )


@router.post("/", response_model=VoteResponse, status_code=status.HTTP_201_CREATED)
async def cast_vote(
    vote: VoteCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Cast a vote on an idea."""
    user_id = current_user["user_id"]
    
    # Check rate limit
    await check_rate_limit(user_id, request)
    
    # Check if user already voted
    existing_vote = db.query(Vote).filter(
        Vote.idea_id == vote.idea_id,
        Vote.user_id == user_id
    ).first()
    
    if existing_vote:
        # Update existing vote
        existing_vote.vote_type = vote.vote_type
        existing_vote.rating = vote.rating
        existing_vote.ip_address = request.client.host
        existing_vote.user_agent = request.headers.get("user-agent", "")[:500]
        db_vote = existing_vote
    else:
        # Create new vote
        db_vote = Vote(
            idea_id=vote.idea_id,
            user_id=user_id,
            vote_type=vote.vote_type,
            rating=vote.rating,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", "")[:500]
        )
        db.add(db_vote)
    
    try:
        db.commit()
        db.refresh(db_vote)
        
        # Update aggregates asynchronously (in production, use message queue)
        update_vote_aggregates(db, vote.idea_id)
        
        # Invalidate cache
        redis_client.delete(f"vote_aggregate:{vote.idea_id}")
        
        logger.info(f"Vote cast by user {user_id} on idea {vote.idea_id}")
        return db_vote
    except Exception as e:
        logger.error(f"Error casting vote: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error casting vote")


@router.delete("/{idea_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_vote(
    idea_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Remove a vote from an idea."""
    user_id = current_user["user_id"]
    
    vote = db.query(Vote).filter(
        Vote.idea_id == idea_id,
        Vote.user_id == user_id
    ).first()
    
    if not vote:
        raise HTTPException(status_code=404, detail="Vote not found")
    
    db.delete(vote)
    db.commit()
    
    # Update aggregates
    update_vote_aggregates(db, idea_id)
    
    # Invalidate cache
    redis_client.delete(f"vote_aggregate:{idea_id}")
    
    logger.info(f"Vote removed by user {user_id} from idea {idea_id}")


@router.get("/idea/{idea_id}/aggregate", response_model=VoteAggregateResponse)
async def get_vote_aggregate(
    idea_id: int,
    db: Session = Depends(get_db)
):
    """Get aggregated vote statistics for an idea."""
    # Try cache first
    cache_key = f"vote_aggregate:{idea_id}"
    cached = redis_client.get_json(cache_key)
    if cached:
        return VoteAggregateResponse(**cached)
    
    # Get from database
    aggregate = db.query(VoteAggregate).filter(
        VoteAggregate.idea_id == idea_id
    ).first()
    
    if not aggregate:
        # Create empty aggregate
        aggregate = VoteAggregate(idea_id=idea_id)
        db.add(aggregate)
        db.commit()
        db.refresh(aggregate)
    
    # Cache result
    redis_client.set(cache_key, aggregate.__dict__, ttl=300)  # 5 minutes
    
    return aggregate


@router.get("/user/status", response_model=UserVoteStatus)
async def get_user_vote_status(
    idea_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Check if current user has voted on a specific idea."""
    user_id = current_user["user_id"]
    
    vote = db.query(Vote).filter(
        Vote.idea_id == idea_id,
        Vote.user_id == user_id
    ).first()
    
    if vote:
        return UserVoteStatus(
            idea_id=idea_id,
            has_voted=True,
            vote_type=vote.vote_type,
            rating=vote.rating,
            voted_at=vote.created_at
        )
    
    return UserVoteStatus(
        idea_id=idea_id,
        has_voted=False
    )


@router.post("/user/bulk-status", response_model=BulkVoteStatusResponse)
async def get_bulk_vote_status(
    request: BulkVoteStatus,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Check user's vote status for multiple ideas."""
    user_id = current_user["user_id"]
    
    votes = db.query(Vote).filter(
        Vote.user_id == user_id,
        Vote.idea_id.in_(request.idea_ids)
    ).all()
    
    vote_map = {vote.idea_id: vote for vote in votes}
    
    results = []
    for idea_id in request.idea_ids:
        if idea_id in vote_map:
            vote = vote_map[idea_id]
            results.append(UserVoteStatus(
                idea_id=idea_id,
                has_voted=True,
                vote_type=vote.vote_type,
                rating=vote.rating,
                voted_at=vote.created_at
            ))
        else:
            results.append(UserVoteStatus(
                idea_id=idea_id,
                has_voted=False
            ))
    
    return BulkVoteStatusResponse(votes=results)


@router.get("/stats", response_model=VoteStatsResponse)
async def get_voting_stats(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """Get voting statistics."""
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Total votes cast
    total_votes = db.query(func.count(Vote.id)).filter(
        Vote.created_at >= since_date
    ).scalar()
    
    # Unique voters
    unique_voters = db.query(func.count(func.distinct(Vote.user_id))).filter(
        Vote.created_at >= since_date
    ).scalar()
    
    # Most voted ideas
    most_voted = db.query(VoteAggregate).order_by(
        desc(VoteAggregate.score)
    ).limit(10).all()
    
    # Recent activity
    recent_votes = db.query(Vote).order_by(
        desc(Vote.created_at)
    ).limit(10).all()
    
    return VoteStatsResponse(
        total_votes_cast=total_votes or 0,
        unique_voters=unique_voters or 0,
        most_voted_ideas=most_voted,
        recent_activity=recent_votes
    )


def update_vote_aggregates(db: Session, idea_id: int):
    """Update vote aggregates for an idea."""
    try:
        # Get or create aggregate
        aggregate = db.query(VoteAggregate).filter(
            VoteAggregate.idea_id == idea_id
        ).first()
        
        if not aggregate:
            aggregate = VoteAggregate(idea_id=idea_id)
            db.add(aggregate)
        
        # Calculate counts
        votes = db.query(Vote).filter(Vote.idea_id == idea_id).all()
        
        aggregate.upvote_count = sum(1 for v in votes if v.vote_type == VoteType.UPVOTE)
        aggregate.downvote_count = sum(1 for v in votes if v.vote_type == VoteType.DOWNVOTE)
        aggregate.total_votes = aggregate.upvote_count + aggregate.downvote_count
        
        # Calculate ratings
        ratings = [v.rating for v in votes if v.vote_type == VoteType.RATING and v.rating]
        aggregate.rating_count = len(ratings)
        aggregate.rating_sum = sum(ratings) if ratings else 0
        aggregate.average_rating = aggregate.rating_sum / aggregate.rating_count if aggregate.rating_count > 0 else 0
        
        # Calculate score
        aggregate.score = aggregate.calculate_score()
        
        db.commit()
        
        logger.info(f"Updated vote aggregates for idea {idea_id}")
    except Exception as e:
        logger.error(f"Error updating vote aggregates: {e}")
        db.rollback()