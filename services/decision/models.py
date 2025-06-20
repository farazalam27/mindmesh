"""SQLAlchemy models for Decision service."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import enum
import uuid

Base = declarative_base()


class DecisionStatus(str, enum.Enum):
    """Enum for decision status."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    ON_HOLD = "on_hold"


class DecisionType(str, enum.Enum):
    """Enum for decision types."""
    IMPLEMENTATION = "implementation"
    REJECTION = "rejection"
    MODIFICATION = "modification"
    ESCALATION = "escalation"
    DEFERRAL = "deferral"


class Decision(Base):
    """Decision model representing decisions made on ideas."""
    __tablename__ = "decisions"
    
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(String(50), unique=True, default=lambda: str(uuid.uuid4()))
    idea_id = Column(Integer, nullable=False, index=True)
    
    # Decision details
    decision_type = Column(String(50), default=DecisionType.IMPLEMENTATION)
    status = Column(String(50), default=DecisionStatus.PENDING, index=True)
    
    # Decision makers
    decided_by = Column(String(100), nullable=True)
    decision_committee = Column(JSON, default=list)  # List of committee member IDs
    
    # Decision content
    summary = Column(String(500), nullable=False)
    rationale = Column(Text, nullable=False)
    conditions = Column(JSON, default=list)  # List of conditions/requirements
    
    # Metrics used for decision
    metrics_snapshot = Column(JSON, default=dict)  # Snapshot of idea metrics at decision time
    score_threshold = Column(Float, nullable=True)
    
    # Implementation details
    implementation_plan = Column(Text, nullable=True)
    estimated_impact = Column(JSON, default=dict)
    resource_requirements = Column(JSON, default=dict)
    timeline_days = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    decided_at = Column(DateTime(timezone=True), nullable=True)
    implemented_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    events = relationship("DecisionEvent", back_populates="decision", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Decision(id={self.id}, idea_id={self.idea_id}, type={self.decision_type}, status={self.status})>"


class DecisionEvent(Base):
    """Event sourcing for decision history."""
    __tablename__ = "decision_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(50), unique=True, default=lambda: str(uuid.uuid4()))
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=False)
    
    # Event details
    event_type = Column(String(100), nullable=False)  # e.g., "created", "status_changed", "metrics_updated"
    event_data = Column(JSON, default=dict)
    
    # Actor information
    actor_id = Column(String(100), nullable=False)
    actor_name = Column(String(100))
    actor_role = Column(String(50))
    
    # Timestamps
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    decision = relationship("Decision", back_populates="events")
    
    def __repr__(self):
        return f"<DecisionEvent(id={self.id}, decision_id={self.decision_id}, event_type='{self.event_type}')>"


class DecisionCriteria(Base):
    """Configurable criteria for automated decision suggestions."""
    __tablename__ = "decision_criteria"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    
    # Criteria configuration
    category = Column(String(50))  # Idea category this applies to
    min_vote_count = Column(Integer, default=10)
    min_engagement_score = Column(Float, default=0.0)
    min_average_rating = Column(Float, default=3.0)
    max_controversy_score = Column(Float, default=0.5)
    
    # Time-based criteria
    min_days_since_created = Column(Integer, default=7)
    max_days_in_review = Column(Integer, default=30)
    
    # ML model thresholds
    min_success_probability = Column(Float, default=0.6)
    required_cluster_size = Column(Integer, default=5)
    
    # Decision outcome
    suggested_decision_type = Column(String(50), default=DecisionType.IMPLEMENTATION)
    auto_approve = Column(Boolean, default=False)
    
    # Active flag
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<DecisionCriteria(id={self.id}, name='{self.name}', category={self.category})>"


class DecisionTemplate(Base):
    """Templates for common decision types."""
    __tablename__ = "decision_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    decision_type = Column(String(50), nullable=False)
    
    # Template content
    summary_template = Column(Text, nullable=False)
    rationale_template = Column(Text, nullable=False)
    conditions_template = Column(JSON, default=list)
    
    # Default values
    default_timeline_days = Column(Integer, default=30)
    default_resource_requirements = Column(JSON, default=dict)
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<DecisionTemplate(id={self.id}, name='{self.name}', type={self.decision_type})>"