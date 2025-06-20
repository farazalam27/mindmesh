"""Pydantic schemas for Decision service."""
from pydantic import BaseModel, Field, ConfigDict, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from .models import DecisionStatus, DecisionType


class DecisionEventBase(BaseModel):
    """Base schema for decision events."""
    event_type: str = Field(..., min_length=1, max_length=100)
    event_data: Dict[str, Any] = Field(default_factory=dict)


class DecisionEventCreate(DecisionEventBase):
    """Schema for creating a decision event."""
    actor_id: str
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None


class DecisionEventResponse(DecisionEventBase):
    """Schema for decision event response."""
    id: int
    event_id: str
    decision_id: int
    actor_id: str
    actor_name: Optional[str]
    actor_role: Optional[str]
    occurred_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DecisionBase(BaseModel):
    """Base schema for decisions."""
    idea_id: int = Field(..., gt=0)
    decision_type: DecisionType
    summary: str = Field(..., min_length=10, max_length=500)
    rationale: str = Field(..., min_length=20)
    conditions: List[str] = Field(default_factory=list)


class DecisionCreate(DecisionBase):
    """Schema for creating a decision."""
    decision_committee: List[str] = Field(default_factory=list)
    implementation_plan: Optional[str] = None
    estimated_impact: Dict[str, Any] = Field(default_factory=dict)
    resource_requirements: Dict[str, Any] = Field(default_factory=dict)
    timeline_days: Optional[int] = Field(None, gt=0)


class DecisionUpdate(BaseModel):
    """Schema for updating a decision."""
    status: Optional[DecisionStatus] = None
    summary: Optional[str] = Field(None, min_length=10, max_length=500)
    rationale: Optional[str] = Field(None, min_length=20)
    conditions: Optional[List[str]] = None
    implementation_plan: Optional[str] = None
    estimated_impact: Optional[Dict[str, Any]] = None
    resource_requirements: Optional[Dict[str, Any]] = None
    timeline_days: Optional[int] = Field(None, gt=0)


class DecisionResponse(DecisionBase):
    """Schema for decision response."""
    id: int
    decision_id: str
    status: DecisionStatus
    decided_by: Optional[str]
    decision_committee: List[str]
    metrics_snapshot: Dict[str, Any]
    score_threshold: Optional[float]
    implementation_plan: Optional[str]
    estimated_impact: Dict[str, Any]
    resource_requirements: Dict[str, Any]
    timeline_days: Optional[int]
    created_at: datetime
    decided_at: Optional[datetime]
    implemented_at: Optional[datetime]
    updated_at: Optional[datetime]
    events_count: Optional[int] = 0
    
    model_config = ConfigDict(from_attributes=True)


class DecisionWithEvents(DecisionResponse):
    """Schema for decision with events."""
    events: List[DecisionEventResponse] = Field(default_factory=list)


class DecisionCriteriaBase(BaseModel):
    """Base schema for decision criteria."""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = None
    min_vote_count: int = Field(default=10, ge=0)
    min_engagement_score: float = Field(default=0.0)
    min_average_rating: float = Field(default=3.0, ge=1.0, le=5.0)
    max_controversy_score: float = Field(default=0.5, ge=0.0, le=1.0)
    min_days_since_created: int = Field(default=7, ge=0)
    max_days_in_review: int = Field(default=30, ge=1)
    min_success_probability: float = Field(default=0.6, ge=0.0, le=1.0)
    required_cluster_size: int = Field(default=5, ge=1)
    suggested_decision_type: DecisionType = DecisionType.IMPLEMENTATION
    auto_approve: bool = False


class DecisionCriteriaCreate(DecisionCriteriaBase):
    """Schema for creating decision criteria."""
    pass


class DecisionCriteriaUpdate(BaseModel):
    """Schema for updating decision criteria."""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = None
    min_vote_count: Optional[int] = Field(None, ge=0)
    min_engagement_score: Optional[float] = None
    min_average_rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    max_controversy_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_days_since_created: Optional[int] = Field(None, ge=0)
    max_days_in_review: Optional[int] = Field(None, ge=1)
    min_success_probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    required_cluster_size: Optional[int] = Field(None, ge=1)
    suggested_decision_type: Optional[DecisionType] = None
    auto_approve: Optional[bool] = None
    is_active: Optional[bool] = None


class DecisionCriteriaResponse(DecisionCriteriaBase):
    """Schema for decision criteria response."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class DecisionSuggestion(BaseModel):
    """Schema for automated decision suggestions."""
    idea_id: int
    suggested_decision_type: DecisionType
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    matching_criteria: List[str]
    idea_metrics: Dict[str, Any]
    rationale: str
    auto_approve_eligible: bool = False


class DecisionTemplateBase(BaseModel):
    """Base schema for decision templates."""
    name: str = Field(..., min_length=3, max_length=100)
    decision_type: DecisionType
    summary_template: str = Field(..., min_length=10)
    rationale_template: str = Field(..., min_length=20)
    conditions_template: List[str] = Field(default_factory=list)
    default_timeline_days: int = Field(default=30, gt=0)
    default_resource_requirements: Dict[str, Any] = Field(default_factory=dict)


class DecisionTemplateCreate(DecisionTemplateBase):
    """Schema for creating a decision template."""
    pass


class DecisionTemplateResponse(DecisionTemplateBase):
    """Schema for decision template response."""
    id: int
    usage_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class DecisionStats(BaseModel):
    """Schema for decision statistics."""
    total_decisions: int
    decisions_by_status: Dict[str, int]
    decisions_by_type: Dict[str, int]
    average_time_to_decision: Optional[float]
    average_implementation_time: Optional[float]
    recent_decisions: List[DecisionResponse]