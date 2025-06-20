"""Pydantic schemas for Voting service."""
from pydantic import BaseModel, Field, ConfigDict, validator
from typing import Optional, List
from datetime import datetime
from .models import VoteType


class VoteBase(BaseModel):
    """Base schema for votes."""
    vote_type: VoteType = VoteType.UPVOTE
    rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    
    @validator('rating')
    def validate_rating(cls, v, values):
        """Ensure rating is only provided for rating type votes."""
        if values.get('vote_type') == VoteType.RATING and v is None:
            raise ValueError('Rating value required for rating type votes')
        if values.get('vote_type') != VoteType.RATING and v is not None:
            raise ValueError('Rating value only allowed for rating type votes')
        return v


class VoteCreate(VoteBase):
    """Schema for creating a vote."""
    idea_id: int = Field(..., gt=0)


class VoteUpdate(BaseModel):
    """Schema for updating a vote."""
    vote_type: Optional[VoteType] = None
    rating: Optional[float] = Field(None, ge=1.0, le=5.0)


class VoteResponse(VoteBase):
    """Schema for vote response."""
    id: int
    idea_id: int
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class VoteAggregateResponse(BaseModel):
    """Schema for vote aggregate response."""
    idea_id: int
    upvote_count: int
    downvote_count: int
    total_votes: int
    rating_count: int
    average_rating: float
    score: float
    last_updated: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserVoteStatus(BaseModel):
    """Schema for user's vote status on an idea."""
    idea_id: int
    has_voted: bool
    vote_type: Optional[VoteType] = None
    rating: Optional[float] = None
    voted_at: Optional[datetime] = None


class BulkVoteStatus(BaseModel):
    """Schema for checking multiple ideas vote status."""
    idea_ids: List[int] = Field(..., min_items=1, max_items=100)


class BulkVoteStatusResponse(BaseModel):
    """Response for bulk vote status check."""
    votes: List[UserVoteStatus]


class VoteStatsResponse(BaseModel):
    """Schema for vote statistics."""
    total_votes_cast: int
    unique_voters: int
    most_voted_ideas: List[VoteAggregateResponse]
    recent_activity: List[VoteResponse]


class RateLimitInfo(BaseModel):
    """Schema for rate limit information."""
    limit: int
    remaining: int
    reset_time: datetime
    window_seconds: int