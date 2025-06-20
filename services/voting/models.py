"""SQLAlchemy models for Voting service."""
from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class VoteType(str, enum.Enum):
    """Enum for vote types."""
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    RATING = "rating"


class Vote(Base):
    """Vote model representing user votes on ideas."""
    __tablename__ = "votes"
    
    id = Column(Integer, primary_key=True, index=True)
    idea_id = Column(Integer, nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    vote_type = Column(String(20), default=VoteType.UPVOTE)
    rating = Column(Float, nullable=True)  # For rating type votes (1-5)
    
    # Metadata
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Ensure one vote per user per idea
    __table_args__ = (
        UniqueConstraint('idea_id', 'user_id', name='_idea_user_uc'),
        Index('idx_user_votes', 'user_id', 'created_at'),
        Index('idx_idea_votes', 'idea_id', 'vote_type'),
    )
    
    def __repr__(self):
        return f"<Vote(id={self.id}, idea_id={self.idea_id}, user_id='{self.user_id}', type={self.vote_type})>"


class VoteAggregate(Base):
    """Aggregated vote statistics for ideas."""
    __tablename__ = "vote_aggregates"
    
    id = Column(Integer, primary_key=True, index=True)
    idea_id = Column(Integer, unique=True, nullable=False, index=True)
    
    # Vote counts
    upvote_count = Column(Integer, default=0)
    downvote_count = Column(Integer, default=0)
    total_votes = Column(Integer, default=0)
    
    # Rating statistics
    rating_count = Column(Integer, default=0)
    rating_sum = Column(Float, default=0.0)
    average_rating = Column(Float, default=0.0)
    
    # Score calculation (can be customized)
    score = Column(Float, default=0.0, index=True)
    
    # Timestamps
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def calculate_score(self):
        """Calculate vote score using Wilson score interval for ranking."""
        # Simple implementation - can be enhanced with Wilson score
        if self.total_votes == 0:
            return 0.0
        
        # Basic score: upvotes - downvotes + (average_rating * rating_weight)
        vote_score = self.upvote_count - self.downvote_count
        rating_weight = 2.0  # Configurable weight for ratings
        
        if self.rating_count > 0:
            return vote_score + (self.average_rating * rating_weight * self.rating_count)
        return float(vote_score)
    
    def __repr__(self):
        return f"<VoteAggregate(idea_id={self.idea_id}, score={self.score})>"