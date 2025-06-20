"""Data models and schemas for MindMesh data validation and serialization."""

from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
import uuid
import re


class InteractionType(str, Enum):
    """Enumeration of user interaction types."""
    VIEW = "view"
    LIKE = "like"
    SHARE = "share"
    COMMENT = "comment"
    SEARCH = "search"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    BOOKMARK = "bookmark"
    FOLLOW = "follow"


class DeviceType(str, Enum):
    """Enumeration of device types."""
    MOBILE = "mobile"
    DESKTOP = "desktop"
    TABLET = "tablet"
    UNKNOWN = "unknown"


class SentimentCategory(str, Enum):
    """Enumeration of sentiment categories."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class MetricType(str, Enum):
    """Enumeration of system metric types."""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    DISK_USAGE = "disk_usage"
    NETWORK_IO = "network_io"


class BaseEventModel(BaseModel):
    """Base model for all events."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="1.0")
    source: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserModel(BaseModel):
    """User data model."""
    user_id: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = None
    username: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    preferences: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('email')
    def validate_email(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('User ID can only contain alphanumeric characters, hyphens, and underscores')
        return v


class UserInteractionModel(BaseEventModel):
    """User interaction event model."""
    user_id: str = Field(..., min_length=1)
    interaction_type: InteractionType
    content_id: Optional[str] = None
    session_id: Optional[str] = None
    device_type: DeviceType = DeviceType.UNKNOWN
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    page_url: Optional[str] = None
    duration_ms: Optional[int] = Field(None, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('ip_address')
    def validate_ip_address(cls, v):
        if v and not re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', v):
            raise ValueError('Invalid IP address format')
        return v
    
    @validator('duration_ms')
    def validate_duration(cls, v):
        if v is not None and v < 0:
            raise ValueError('Duration cannot be negative')
        return v


class ThoughtModel(BaseEventModel):
    """Thought capture model."""
    user_id: str = Field(..., min_length=1)
    thought_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    thought_text: str = Field(..., min_length=1, max_length=10000)
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    sentiment_category: Optional[SentimentCategory] = None
    tags: List[str] = Field(default_factory=list)
    word_count: Optional[int] = Field(None, ge=0)
    character_count: Optional[int] = Field(None, ge=0)
    language: Optional[str] = Field(default="en")
    is_private: bool = True
    parent_thought_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('thought_text')
    def validate_thought_text(cls, v):
        if not v.strip():
            raise ValueError('Thought text cannot be empty or only whitespace')
        return v.strip()
    
    @validator('tags')
    def validate_tags(cls, v):
        if len(v) > 20:
            raise ValueError('Maximum 20 tags allowed')
        # Clean and validate tags
        cleaned_tags = []
        for tag in v:
            if isinstance(tag, str) and tag.strip():
                cleaned_tag = tag.strip().lower()
                if len(cleaned_tag) <= 50 and re.match(r'^[a-zA-Z0-9_-]+$', cleaned_tag):
                    cleaned_tags.append(cleaned_tag)
        return cleaned_tags
    
    @root_validator
    def calculate_counts(cls, values):
        thought_text = values.get('thought_text', '')
        if thought_text:
            values['word_count'] = len(thought_text.split())
            values['character_count'] = len(thought_text)
        return values
    
    @root_validator
    def set_sentiment_category(cls, values):
        sentiment_score = values.get('sentiment_score')
        if sentiment_score is not None:
            if sentiment_score > 0.3:
                values['sentiment_category'] = SentimentCategory.POSITIVE
            elif sentiment_score < -0.3:
                values['sentiment_category'] = SentimentCategory.NEGATIVE
            else:
                values['sentiment_category'] = SentimentCategory.NEUTRAL
        return values


class ContentModel(BaseModel):
    """Content item model."""
    content_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(..., min_length=1, max_length=500)
    content_type: str = Field(..., min_length=1)
    author_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    description: Optional[str] = Field(None, max_length=2000)
    url: Optional[str] = None
    is_published: bool = False
    view_count: int = Field(default=0, ge=0)
    like_count: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('url')
    def validate_url(cls, v):
        if v and not re.match(r'^https?://', v):
            raise ValueError('URL must start with http:// or https://')
        return v


class SystemMetricModel(BaseEventModel):
    """System performance metric model."""
    metric_name: str = Field(..., min_length=1)
    metric_value: float
    metric_type: Optional[MetricType] = None
    component: str = Field(..., min_length=1)
    host: Optional[str] = None
    environment: Optional[str] = Field(default="production")
    unit: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    
    @validator('metric_value')
    def validate_metric_value(cls, v):
        if not isinstance(v, (int, float)):
            raise ValueError('Metric value must be a number')
        return float(v)
    
    @validator('metric_name')
    def validate_metric_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError('Metric name can only contain alphanumeric characters, dots, hyphens, and underscores')
        return v.lower()


class RecommendationModel(BaseEventModel):
    """Content recommendation model."""
    user_id: str = Field(..., min_length=1)
    recommended_content_ids: List[str] = Field(..., min_items=1)
    algorithm: str = Field(..., min_length=1)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    context: Dict[str, Any] = Field(default_factory=dict)
    expires_at: Optional[datetime] = None
    is_viewed: bool = False
    is_clicked: bool = False
    feedback_score: Optional[float] = Field(None, ge=0.0, le=5.0)
    
    @validator('recommended_content_ids')
    def validate_content_ids(cls, v):
        if len(v) > 50:
            raise ValueError('Maximum 50 recommended items allowed')
        return v


class UserSessionModel(BaseModel):
    """User session tracking model."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., min_length=1)
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    device_type: DeviceType = DeviceType.UNKNOWN
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    page_views: int = Field(default=0, ge=0)
    interactions: int = Field(default=0, ge=0)
    duration_seconds: Optional[int] = Field(None, ge=0)
    
    @root_validator
    def calculate_duration(cls, values):
        start_time = values.get('start_time')
        end_time = values.get('end_time')
        if start_time and end_time:
            duration = (end_time - start_time).total_seconds()
            values['duration_seconds'] = max(0, int(duration))
        return values


class DataQualityReport(BaseModel):
    """Data quality assessment report."""
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    dataset_name: str
    total_records: int = Field(..., ge=0)
    valid_records: int = Field(..., ge=0)
    invalid_records: int = Field(..., ge=0)
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    accuracy_score: float = Field(..., ge=0.0, le=1.0)
    consistency_score: float = Field(..., ge=0.0, le=1.0)
    overall_quality_score: float = Field(..., ge=0.0, le=1.0)
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    @root_validator
    def calculate_overall_score(cls, values):
        completeness = values.get('completeness_score', 0)
        accuracy = values.get('accuracy_score', 0)
        consistency = values.get('consistency_score', 0)
        
        # Weighted average of quality dimensions
        overall = (completeness * 0.4 + accuracy * 0.4 + consistency * 0.2)
        values['overall_quality_score'] = round(overall, 3)
        
        return values


class MLModelMetrics(BaseModel):
    """Machine learning model performance metrics."""
    model_id: str
    model_name: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    accuracy: Optional[float] = Field(None, ge=0.0, le=1.0)
    precision: Optional[float] = Field(None, ge=0.0, le=1.0)
    recall: Optional[float] = Field(None, ge=0.0, le=1.0)
    f1_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    auc_roc: Optional[float] = Field(None, ge=0.0, le=1.0)
    training_time_seconds: Optional[float] = Field(None, ge=0.0)
    prediction_time_ms: Optional[float] = Field(None, ge=0.0)
    model_size_mb: Optional[float] = Field(None, ge=0.0)
    feature_importance: Dict[str, float] = Field(default_factory=dict)
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    """Batch of events for bulk processing."""
    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    batch_timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str
    events: List[Dict[str, Any]] = Field(..., min_items=1)
    total_events: int
    source_system: Optional[str] = None
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @root_validator
    def validate_batch(cls, values):
        events = values.get('events', [])
        values['total_events'] = len(events)
        
        if values['total_events'] > 10000:
            raise ValueError('Batch size cannot exceed 10,000 events')
        
        return values


class ValidationError(BaseModel):
    """Data validation error details."""
    field_name: str
    error_type: str
    error_message: str
    invalid_value: Any
    suggested_value: Optional[Any] = None
    severity: str = Field(default="error")  # error, warning, info


class ProcessingStatus(str, Enum):
    """Processing status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataPipelineRun(BaseModel):
    """Data pipeline execution tracking."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    input_records: int = Field(default=0, ge=0)
    output_records: int = Field(default=0, ge=0)
    error_records: int = Field(default=0, ge=0)
    processing_time_seconds: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    error_messages: List[str] = Field(default_factory=list)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    
    @root_validator
    def calculate_processing_time(cls, values):
        start_time = values.get('start_time')
        end_time = values.get('end_time')
        if start_time and end_time:
            duration = (end_time - start_time).total_seconds()
            values['processing_time_seconds'] = duration
        return values


# Utility functions for model validation and serialization

def validate_event_batch(events: List[Dict], event_model_class: BaseModel) -> Tuple[List[BaseModel], List[ValidationError]]:
    """Validate a batch of events against a model class."""
    valid_events = []
    validation_errors = []
    
    for i, event_data in enumerate(events):
        try:
            valid_event = event_model_class(**event_data)
            valid_events.append(valid_event)
        except Exception as e:
            error = ValidationError(
                field_name=f"event_{i}",
                error_type=type(e).__name__,
                error_message=str(e),
                invalid_value=event_data
            )
            validation_errors.append(error)
    
    return valid_events, validation_errors


def serialize_for_kafka(model: BaseModel) -> bytes:
    """Serialize a model for Kafka transmission."""
    return model.json().encode('utf-8')


def deserialize_from_kafka(data: bytes, model_class: BaseModel) -> BaseModel:
    """Deserialize Kafka data to a model."""
    json_data = data.decode('utf-8')
    return model_class.parse_raw(json_data)


# Model registry for dynamic model loading
MODEL_REGISTRY = {
    'user_interaction': UserInteractionModel,
    'thought_capture': ThoughtModel,
    'system_metric': SystemMetricModel,
    'recommendation': RecommendationModel,
    'user_session': UserSessionModel,
    'content': ContentModel,
    'user': UserModel
}


def get_model_class(event_type: str) -> Optional[BaseModel]:
    """Get model class for a given event type."""
    return MODEL_REGISTRY.get(event_type)


if __name__ == "__main__":
    # Example usage and testing
    
    # Test user interaction model
    interaction_data = {
        "user_id": "user_123",
        "interaction_type": "view",
        "content_id": "content_456",
        "device_type": "mobile",
        "duration_ms": 5000
    }
    
    try:
        interaction = UserInteractionModel(**interaction_data)
        print(f"Valid interaction: {interaction.json()}")
    except Exception as e:
        print(f"Validation error: {e}")
    
    # Test thought model
    thought_data = {
        "user_id": "user_123",
        "thought_text": "This is a sample thought for testing",
        "sentiment_score": 0.7,
        "tags": ["positive", "testing", "sample"]
    }
    
    try:
        thought = ThoughtModel(**thought_data)
        print(f"Valid thought: {thought.json()}")
    except Exception as e:
        print(f"Validation error: {e}")
    
    # Test batch validation
    events = [
        {"user_id": "user_1", "interaction_type": "view"},
        {"user_id": "user_2", "interaction_type": "like"},
        {"user_id": "", "interaction_type": "invalid"}  # This should fail
    ]
    
    valid_events, errors = validate_event_batch(events, UserInteractionModel)
    print(f"Valid events: {len(valid_events)}, Errors: {len(errors)}")
    
    for error in errors:
        print(f"Validation error: {error.json()}")