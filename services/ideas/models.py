"""SQLAlchemy models for Ideas service."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum


class IdeaStatus(str, enum.Enum):
    """Enum for idea status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    UNDER_REVIEW = "under_review"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"


class IdeaCategory(str, enum.Enum):
    """Enum for idea categories."""
    INNOVATION = "innovation"
    IMPROVEMENT = "improvement"
    PROBLEM_SOLVING = "problem_solving"
    COST_SAVING = "cost_saving"
    REVENUE_GENERATION = "revenue_generation"
    OTHER = "other"


class Idea(Base):
    """Idea model representing user-submitted ideas."""
    __tablename__ = "ideas"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(String(50), default=IdeaCategory.OTHER)
    status = Column(String(50), default=IdeaStatus.DRAFT, index=True)
    
    # User information
    user_id = Column(String(100), nullable=False, index=True)
    user_email = Column(String(255), nullable=False)
    user_name = Column(String(100))
    
    # Metrics
    vote_count = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    view_count = Column(Integer, default=0)
    
    # Metadata
    tags = Column(JSON, default=list)
    attachments = Column(JSON, default=list)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    comments = relationship("Comment", back_populates="idea", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Idea(id={self.id}, title='{self.title}', status={self.status})>"


class Comment(Base):
    """Comment model for idea discussions."""
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    idea_id = Column(Integer, ForeignKey("ideas.id"), nullable=False)
    user_id = Column(String(100), nullable=False)
    user_name = Column(String(100))
    content = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    idea = relationship("Idea", back_populates="comments")
    
    def __repr__(self):
        return f"<Comment(id={self.id}, idea_id={self.idea_id}, user_id='{self.user_id}')>"