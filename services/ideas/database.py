"""Database configuration for Ideas service."""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Generator
import logging

logger = logging.getLogger(__name__)

# Database URL from environment or default
DATABASE_URL = os.getenv(
    "IDEAS_DATABASE_URL",
    "postgresql://user:password@localhost/ideas_db"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()


def get_db() -> Generator:
    """
    Dependency to get database session.
    Yields database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Initialize database with all tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise