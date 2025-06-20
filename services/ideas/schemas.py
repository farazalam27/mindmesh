"""Pydantic schemas for Ideas service."""
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from .models import IdeaStatus, IdeaCategory


class CommentBase(BaseModel):
    """Base schema for comments."""
    content: str = Field(..., min_length=1, max_length=1000)


class CommentCreate(CommentBase):
    """Schema for creating a comment."""
    pass


class CommentUpdate(BaseModel):
    """Schema for updating a comment."""
    content: Optional[str] = Field(None, min_length=1, max_length=1000)


class CommentResponse(CommentBase):
    """Schema for comment response."""
    id: int
    idea_id: int
    user_id: str
    user_name: Optional[str]
    is_deleted: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class IdeaBase(BaseModel):
    """Base schema for ideas."""
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20, max_length=5000)
    category: IdeaCategory = Field(default=IdeaCategory.OTHER)
    tags: List[str] = Field(default_factory=list, max_items=10)


class IdeaCreate(IdeaBase):
    """Schema for creating an idea."""
    attachments: List[Dict[str, Any]] = Field(default_factory=list, max_items=5)


class IdeaUpdate(BaseModel):
    """Schema for updating an idea."""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=20, max_length=5000)
    category: Optional[IdeaCategory] = None
    status: Optional[IdeaStatus] = None
    tags: Optional[List[str]] = Field(None, max_items=10)
    attachments: Optional[List[Dict[str, Any]]] = Field(None, max_items=5)


class IdeaResponse(IdeaBase):
    """Schema for idea response."""
    id: int
    status: IdeaStatus
    user_id: str
    user_email: str
    user_name: Optional[str]
    vote_count: int
    average_rating: float
    view_count: int
    attachments: List[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]
    published_at: Optional[datetime]
    comments_count: Optional[int] = 0
    
    model_config = ConfigDict(from_attributes=True)


class IdeaListResponse(BaseModel):
    """Schema for paginated idea list response."""
    items: List[IdeaResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class IdeaFilters(BaseModel):
    """Schema for idea filtering."""
    status: Optional[IdeaStatus] = None
    category: Optional[IdeaCategory] = None
    user_id: Optional[str] = None
    search: Optional[str] = None
    tags: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class UserAuth(BaseModel):
    """Schema for user authentication."""
    user_id: str
    email: EmailStr
    name: Optional[str]
    roles: List[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int