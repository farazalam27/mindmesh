"""API routes for Ideas service."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
import logging
from datetime import datetime
from jose import JWTError, jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

from .database import get_db
from .models import Idea, Comment, IdeaStatus
from .schemas import (
    IdeaCreate, IdeaUpdate, IdeaResponse, IdeaListResponse,
    CommentCreate, CommentResponse, IdeaFilters, UserAuth
)

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

# Security
security = HTTPBearer()

router = APIRouter(prefix="/api/v1/ideas", tags=["ideas"])


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserAuth:
    """Decode and validate JWT token."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = UserAuth(
            user_id=payload.get("user_id"),
            email=payload.get("email"),
            name=payload.get("name"),
            roles=payload.get("roles", [])
        )
        return user
    except JWTError as e:
        logger.error(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


@router.post("/", response_model=IdeaResponse, status_code=status.HTTP_201_CREATED)
async def create_idea(
    idea: IdeaCreate,
    db: Session = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user)
):
    """Create a new idea."""
    try:
        db_idea = Idea(
            **idea.model_dump(),
            user_id=current_user.user_id,
            user_email=current_user.email,
            user_name=current_user.name
        )
        db.add(db_idea)
        db.commit()
        db.refresh(db_idea)
        
        logger.info(f"Created idea {db_idea.id} by user {current_user.user_id}")
        return db_idea
    except Exception as e:
        logger.error(f"Error creating idea: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error creating idea")


@router.get("/", response_model=IdeaListResponse)
async def list_ideas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[IdeaStatus] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    user_id: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|vote_count|average_rating)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """List ideas with filtering and pagination."""
    try:
        query = db.query(Idea)
        
        # Apply filters
        if status:
            query = query.filter(Idea.status == status)
        if category:
            query = query.filter(Idea.category == category)
        if user_id:
            query = query.filter(Idea.user_id == user_id)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Idea.title.ilike(search_term),
                    Idea.description.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        order_column = getattr(Idea, sort_by)
        if order == "desc":
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        ideas = query.offset(offset).limit(page_size).all()
        
        # Add comments count
        for idea in ideas:
            idea.comments_count = len([c for c in idea.comments if not c.is_deleted])
        
        return IdeaListResponse(
            items=ideas,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size
        )
    except Exception as e:
        logger.error(f"Error listing ideas: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving ideas")


@router.get("/{idea_id}", response_model=IdeaResponse)
async def get_idea(
    idea_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific idea by ID."""
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    # Increment view count
    idea.view_count += 1
    db.commit()
    
    # Add comments count
    idea.comments_count = len([c for c in idea.comments if not c.is_deleted])
    
    return idea


@router.patch("/{idea_id}", response_model=IdeaResponse)
async def update_idea(
    idea_id: int,
    idea_update: IdeaUpdate,
    db: Session = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user)
):
    """Update an idea."""
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    # Check permissions
    if idea.user_id != current_user.user_id and "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Not authorized to update this idea")
    
    # Update fields
    update_data = idea_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(idea, field, value)
    
    # Update published_at if status changed to published
    if idea_update.status == IdeaStatus.PUBLISHED and not idea.published_at:
        idea.published_at = datetime.utcnow()
    
    db.commit()
    db.refresh(idea)
    
    logger.info(f"Updated idea {idea_id} by user {current_user.user_id}")
    return idea


@router.delete("/{idea_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_idea(
    idea_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user)
):
    """Delete an idea."""
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    # Check permissions
    if idea.user_id != current_user.user_id and "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Not authorized to delete this idea")
    
    db.delete(idea)
    db.commit()
    
    logger.info(f"Deleted idea {idea_id} by user {current_user.user_id}")


@router.post("/{idea_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    idea_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user)
):
    """Add a comment to an idea."""
    # Check if idea exists
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    db_comment = Comment(
        idea_id=idea_id,
        user_id=current_user.user_id,
        user_name=current_user.name,
        content=comment.content
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    return db_comment


@router.get("/{idea_id}/comments", response_model=List[CommentResponse])
async def list_comments(
    idea_id: int,
    db: Session = Depends(get_db)
):
    """List all comments for an idea."""
    # Check if idea exists
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    comments = db.query(Comment).filter(
        Comment.idea_id == idea_id,
        Comment.is_deleted == False
    ).order_by(Comment.created_at.desc()).all()
    
    return comments