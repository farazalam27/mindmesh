"""Pytest configuration and fixtures for integration tests."""
import pytest
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Try to import Spark components
try:
    from pyspark.sql import SparkSession
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False
    SparkSession = Mock


@pytest.fixture(scope="session")
def test_config():
    """Test configuration settings."""
    return {
        "database_url": "sqlite:///:memory:",
        "redis_url": "redis://localhost:6379/15",
        "spark_master": "local[2]",
        "test_data_size": 100,
        "ml_model_path": tempfile.mkdtemp(),
        "log_level": "WARNING"
    }


@pytest.fixture(scope="session")
def temp_directory():
    """Create temporary directory for test files."""
    temp_dir = tempfile.mkdtemp(prefix="mindmesh_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def spark_session(test_config):
    """Create Spark session for integration tests."""
    if SPARK_AVAILABLE:
        spark = SparkSession.builder \
            .appName("MindMesh Integration Tests") \
            .master(test_config["spark_master"]) \
            .config("spark.sql.warehouse.dir", test_config["ml_model_path"]) \
            .config("spark.sql.adaptive.enabled", "true") \
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
            .getOrCreate()
        
        # Set log level to reduce noise
        spark.sparkContext.setLogLevel("WARN")
        
        yield spark
        
        # Cleanup
        spark.stop()
    else:
        # Mock Spark session for environments without Spark
        mock_spark = Mock(spec=SparkSession)
        mock_spark.version = "3.5.0"
        mock_spark.sparkContext.master = "local[2]"
        mock_spark.sql.return_value = Mock()
        mock_spark.read.return_value = Mock()
        yield mock_spark


@pytest.fixture(scope="session")
def test_database_engine(test_config):
    """Create test database engine."""
    engine = create_engine(
        test_config["database_url"],
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in test_config["database_url"] else {}
    )
    
    yield engine
    
    # Cleanup
    engine.dispose()


@pytest.fixture(scope="session")
def test_database_session(test_database_engine):
    """Create test database session factory."""
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_database_engine
    )
    
    # Create all tables
    from services.ideas.models import Base as IdeasBase
    from services.voting.models import Base as VotingBase
    from services.decision.models import Base as DecisionBase
    
    IdeasBase.metadata.create_all(test_database_engine)
    VotingBase.metadata.create_all(test_database_engine)
    DecisionBase.metadata.create_all(test_database_engine)
    
    yield SessionLocal
    
    # Cleanup
    DecisionBase.metadata.drop_all(test_database_engine)
    VotingBase.metadata.drop_all(test_database_engine)
    IdeasBase.metadata.drop_all(test_database_engine)


@pytest.fixture
def db_session(test_database_session):
    """Create database session for individual tests."""
    session = test_database_session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="session")
def redis_client(test_config):
    """Create Redis client for testing."""
    try:
        client = redis.Redis.from_url(test_config["redis_url"])
        client.ping()  # Test connection
        yield client
        client.flushdb()  # Clear test database
    except (redis.ConnectionError, redis.TimeoutError):
        # Mock Redis if not available
        mock_redis = Mock(spec=redis.Redis)
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.incr.return_value = 1
        mock_redis.exists.return_value = False
        mock_redis.ping.return_value = True
        yield mock_redis


@pytest.fixture
def test_app():
    """Create FastAPI application for testing."""
    from fastapi import FastAPI
    from services.ideas.api import router as ideas_router
    from services.voting.api import router as voting_router
    from services.decision.api import router as decision_router
    
    app = FastAPI(title="MindMesh Test API", version="1.0.0")
    
    # Include routers
    app.include_router(ideas_router, prefix="/api/v1/ideas", tags=["ideas"])
    app.include_router(voting_router, prefix="/api/v1/votes", tags=["votes"])
    app.include_router(decision_router, prefix="/api/v1/decisions", tags=["decisions"])
    
    return app


@pytest.fixture
def test_client(test_app):
    """Create test client for API testing."""
    return TestClient(test_app)


@pytest.fixture
def mock_authentication():
    """Mock authentication for API tests."""
    def _mock_auth(user_type="employee", user_id="test_user_001"):
        """Create mock authentication context."""
        auth_data = {
            "employee": {
                "user_id": user_id,
                "user_email": f"{user_id}@company.com",
                "user_name": f"Test {user_type.title()}",
                "role": "employee",
                "permissions": ["read_ideas", "submit_ideas", "vote_ideas"]
            },
            "manager": {
                "user_id": user_id,
                "user_email": f"{user_id}@company.com",
                "user_name": f"Test {user_type.title()}",
                "role": "manager",
                "permissions": ["read_ideas", "submit_ideas", "vote_ideas", "make_decisions", "view_analytics"]
            },
            "admin": {
                "user_id": user_id,
                "user_email": f"{user_id}@company.com",
                "user_name": f"Test {user_type.title()}",
                "role": "admin",
                "permissions": ["*"]
            }
        }
        
        return auth_data.get(user_type, auth_data["employee"])
    
    return _mock_auth


@pytest.fixture
def auth_headers(mock_authentication):
    """Create authentication headers for requests."""
    def _create_headers(user_type="employee", user_id="test_user_001"):
        user_data = mock_authentication(user_type, user_id)
        return {
            "Authorization": f"Bearer test_token_{user_id}",
            "X-User-ID": user_data["user_id"],
            "X-User-Role": user_data["role"]
        }
    
    return _create_headers


@pytest.fixture
def sample_ideas_data():
    """Generate sample ideas data for testing."""
    from services.ideas.models import IdeaCategory, IdeaStatus
    import random
    
    ideas_data = []
    categories = list(IdeaCategory)
    statuses = list(IdeaStatus)
    
    for i in range(50):
        idea = {
            "id": i + 1,
            "title": f"Test Idea {i + 1}",
            "description": f"This is a comprehensive test description for idea {i + 1}. It includes various keywords and concepts that would be useful for testing ML algorithms and search functionality.",
            "category": random.choice(categories),
            "status": random.choice(statuses),
            "user_id": f"user_{i % 10:03d}",
            "user_email": f"user_{i % 10:03d}@company.com",
            "user_name": f"Test User {i % 10:03d}",
            "vote_count": random.randint(0, 100),
            "average_rating": round(random.uniform(1.0, 5.0), 2),
            "view_count": random.randint(10, 1000),
            "tags": [f"tag_{j}" for j in random.sample(range(20), random.randint(1, 5))],
            "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365)),
            "published_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 300)) if random.random() > 0.3 else None
        }
        ideas_data.append(idea)
    
    return ideas_data


@pytest.fixture
def sample_votes_data(sample_ideas_data):
    """Generate sample votes data for testing."""
    from services.voting.models import VoteType
    import random
    
    votes_data = []
    vote_types = list(VoteType)
    
    for idea in sample_ideas_data[:20]:  # Generate votes for first 20 ideas
        num_votes = random.randint(1, 10)
        
        for i in range(num_votes):
            vote = {
                "id": len(votes_data) + 1,
                "idea_id": idea["id"],
                "user_id": f"voter_{i:03d}",
                "vote_type": random.choice(vote_types),
                "rating": round(random.uniform(1.0, 5.0), 1) if random.random() > 0.5 else None,
                "ip_address": f"192.168.1.{random.randint(1, 254)}",
                "user_agent": "Mozilla/5.0 Test Browser",
                "created_at": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 72))
            }
            votes_data.append(vote)
    
    return votes_data


@pytest.fixture
def sample_decisions_data(sample_ideas_data):
    """Generate sample decisions data for testing."""
    from services.decision.models import DecisionType, DecisionStatus
    import random
    
    decisions_data = []
    decision_types = list(DecisionType)
    decision_statuses = list(DecisionStatus)
    
    # Create decisions for high-engagement ideas
    high_engagement_ideas = [idea for idea in sample_ideas_data if idea["vote_count"] > 30]
    
    for idea in high_engagement_ideas[:10]:  # First 10 high-engagement ideas
        decision = {
            "id": len(decisions_data) + 1,
            "idea_id": idea["id"],
            "decision_type": random.choice(decision_types),
            "status": random.choice(decision_statuses),
            "decided_by": f"manager_{random.randint(1, 5):03d}",
            "summary": f"Decision for idea {idea['id']}: {random.choice(['Approved', 'Rejected', 'Deferred', 'Modified'])}",
            "rationale": f"Based on analysis of idea {idea['id']}, the decision was made considering engagement metrics, business alignment, and resource availability.",
            "metrics_snapshot": {
                "vote_count": idea["vote_count"],
                "average_rating": idea["average_rating"],
                "view_count": idea["view_count"],
                "engagement_score": random.uniform(0.3, 0.9)
            },
            "timeline_days": random.randint(30, 180) if random.random() > 0.5 else None,
            "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 90)),
            "decided_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 60)) if random.random() > 0.3 else None
        }
        decisions_data.append(decision)
    
    return decisions_data


@pytest.fixture
def populate_test_database(db_session, sample_ideas_data, sample_votes_data, sample_decisions_data):
    """Populate test database with sample data."""
    from services.ideas.models import Idea, Comment
    from services.voting.models import Vote, VoteAggregate
    from services.decision.models import Decision
    
    # Create ideas
    for idea_data in sample_ideas_data[:20]:  # Limit for test performance
        idea = Idea(
            title=idea_data["title"],
            description=idea_data["description"],
            category=idea_data["category"],
            status=idea_data["status"],
            user_id=idea_data["user_id"],
            user_email=idea_data["user_email"],
            user_name=idea_data["user_name"],
            vote_count=idea_data["vote_count"],
            average_rating=idea_data["average_rating"],
            view_count=idea_data["view_count"],
            tags=idea_data["tags"],
            created_at=idea_data["created_at"],
            published_at=idea_data["published_at"]
        )
        db_session.add(idea)
    
    # Create votes
    for vote_data in sample_votes_data[:50]:  # Limit for test performance
        vote = Vote(
            idea_id=vote_data["idea_id"],
            user_id=vote_data["user_id"],
            vote_type=vote_data["vote_type"],
            rating=vote_data["rating"],
            ip_address=vote_data["ip_address"],
            user_agent=vote_data["user_agent"],
            created_at=vote_data["created_at"]
        )
        db_session.add(vote)
    
    # Create decisions
    for decision_data in sample_decisions_data[:10]:  # Limit for test performance
        decision = Decision(
            idea_id=decision_data["idea_id"],
            decision_type=decision_data["decision_type"],
            status=decision_data["status"],
            decided_by=decision_data["decided_by"],
            summary=decision_data["summary"],
            rationale=decision_data["rationale"],
            metrics_snapshot=decision_data["metrics_snapshot"],
            timeline_days=decision_data["timeline_days"],
            created_at=decision_data["created_at"],
            decided_at=decision_data["decided_at"]
        )
        db_session.add(decision)
    
    db_session.commit()
    
    yield  # Test runs here
    
    # Cleanup is handled by session rollback in db_session fixture


@pytest.fixture
def mock_external_services():
    """Mock external services for integration tests."""
    mocks = {}
    
    # Mock email service
    mocks['email_service'] = Mock()
    mocks['email_service'].send_notification.return_value = True
    
    # Mock file storage service
    mocks['storage_service'] = Mock()
    mocks['storage_service'].upload_file.return_value = "https://storage.example.com/file123.pdf"
    mocks['storage_service'].delete_file.return_value = True
    
    # Mock analytics service
    mocks['analytics_service'] = Mock()
    mocks['analytics_service'].calculate_engagement_score.return_value = 0.75
    mocks['analytics_service'].get_trending_topics.return_value = [
        {"topic": "AI", "growth_rate": 0.15},
        {"topic": "sustainability", "growth_rate": 0.08}
    ]
    
    # Mock notification service
    mocks['notification_service'] = Mock()
    mocks['notification_service'].send_push_notification.return_value = True
    
    return mocks


@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during tests."""
    import time
    import psutil
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.start_memory = None
            self.metrics = {}
        
        def start(self):
            self.start_time = time.time()
            self.start_memory = psutil.Process().memory_info().rss
        
        def stop(self, operation_name="test"):
            if self.start_time:
                duration = time.time() - self.start_time
                current_memory = psutil.Process().memory_info().rss
                memory_delta = current_memory - self.start_memory
                
                self.metrics[operation_name] = {
                    "duration": duration,
                    "memory_delta": memory_delta,
                    "memory_peak": current_memory
                }
                
                return self.metrics[operation_name]
        
        def get_summary(self):
            return self.metrics
    
    return PerformanceMonitor()


# Test markers for different types of integration tests
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "spark: mark test as requiring Spark"
    )
    config.addinivalue_line(
        "markers", "redis: mark test as requiring Redis"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "api: mark test as API integration test"
    )
    config.addinivalue_line(
        "markers", "ml: mark test as ML/analytics test"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on file location and imports."""
    for item in items:
        # Mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Mark Spark tests
        if "spark" in str(item.fspath) or any("spark" in str(marker) for marker in item.iter_markers()):
            item.add_marker(pytest.mark.spark)
            if not SPARK_AVAILABLE:
                item.add_marker(pytest.mark.skip(reason="PySpark not available"))
        
        # Mark API tests
        if "api" in str(item.fspath) or "test_client" in str(item.fixturenames):
            item.add_marker(pytest.mark.api)
        
        # Mark ML tests
        if any(keyword in str(item.fspath).lower() for keyword in ["ml", "analytics", "clustering", "prediction"]):
            item.add_marker(pytest.mark.ml)


# Session-scoped setup and teardown
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(test_config, temp_directory):
    """Set up test environment before all tests."""
    # Set environment variables
    os.environ["MINDMESH_ENV"] = "test"
    os.environ["MINDMESH_DATABASE_URL"] = test_config["database_url"]
    os.environ["MINDMESH_REDIS_URL"] = test_config["redis_url"]
    os.environ["ML_MODEL_PATH"] = test_config["ml_model_path"]
    
    yield
    
    # Cleanup environment
    for key in ["MINDMESH_ENV", "MINDMESH_DATABASE_URL", "MINDMESH_REDIS_URL", "ML_MODEL_PATH"]:
        if key in os.environ:
            del os.environ[key]