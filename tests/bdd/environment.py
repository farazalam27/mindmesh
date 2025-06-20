"""Behave environment configuration for BDD tests."""
import os
import sys
import logging
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def before_all(context):
    """Set up test environment before all tests."""
    logger.info("Setting up BDD test environment...")
    
    # Set test configuration
    context.config = {
        'test_mode': True,
        'database_url': 'sqlite:///:memory:',
        'redis_url': 'redis://localhost:6379/15',  # Use test Redis DB
        'spark_master': 'local[*]',
        'log_level': 'INFO'
    }
    
    # Mock external services that might not be available
    context.mocks = {}
    
    # Mock Spark if not available
    try:
        from pyspark.sql import SparkSession
        context.spark_available = True
    except ImportError:
        logger.warning("PySpark not available, using mocks")
        context.spark_available = False
        context.mocks['spark'] = Mock()
    
    # Mock Redis if not available
    try:
        import redis
        # Test Redis connection
        r = redis.Redis(host='localhost', port=6379, db=15)
        r.ping()
        context.redis_available = True
    except Exception:
        logger.warning("Redis not available, using mocks")
        context.redis_available = False
        context.mocks['redis'] = Mock()
    
    # Set up test database engine
    context.test_engine = create_engine(
        'sqlite:///:memory:',
        echo=False,
        connect_args={'check_same_thread': False}
    )
    
    logger.info("BDD test environment setup complete")


def before_feature(context, feature):
    """Set up before each feature."""
    logger.info(f"Starting feature: {feature.name}")
    
    # Create fresh database for each feature
    from services.ideas.models import Base as IdeasBase
    from services.voting.models import Base as VotingBase
    from services.decision.models import Base as DecisionBase
    
    # Create all tables
    IdeasBase.metadata.create_all(context.test_engine)
    VotingBase.metadata.create_all(context.test_engine)
    DecisionBase.metadata.create_all(context.test_engine)
    
    # Create session factory
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=context.test_engine
    )
    context.SessionLocal = SessionLocal
    
    # Set up feature-specific mocks
    context.feature_mocks = {}
    
    if feature.name == "Analytics and Machine Learning":
        # Mock ML models and Spark for analytics tests
        context.feature_mocks.update({
            'kmeans_model': Mock(),
            'success_prediction_model': Mock(),
            'lda_model': Mock(),
            'spark_session': Mock()
        })
    
    elif feature.name == "Voting System":
        # Mock Redis for voting tests
        if not context.redis_available:
            context.feature_mocks['redis_client'] = Mock()
    
    elif feature.name == "Decision Making Process":
        # Mock notification services for decision tests
        context.feature_mocks.update({
            'notification_service': Mock(),
            'email_service': Mock()
        })


def before_scenario(context, scenario):
    """Set up before each scenario."""
    logger.debug(f"Starting scenario: {scenario.name}")
    
    # Create fresh database session for each scenario
    context.db = context.SessionLocal()
    
    # Initialize scenario-specific data
    context.test_data = {
        'ideas': [],
        'votes': [],
        'decisions': [],
        'users': []
    }
    
    # Set up authentication context
    context.authenticated_users = {}
    context.current_user = None
    
    # Initialize metrics tracking
    context.metrics = {
        'api_calls': 0,
        'database_operations': 0,
        'cache_operations': 0
    }


def after_scenario(context, scenario):
    """Clean up after each scenario."""
    logger.debug(f"Completing scenario: {scenario.name}")
    
    # Clean up database session
    if hasattr(context, 'db'):
        try:
            context.db.rollback()
            context.db.close()
        except Exception as e:
            logger.warning(f"Error closing database session: {e}")
    
    # Clean up any file artifacts
    if hasattr(context, 'temp_files'):
        for temp_file in context.temp_files:
            try:
                os.remove(temp_file)
            except FileNotFoundError:
                pass
    
    # Log scenario metrics
    if hasattr(context, 'metrics'):
        logger.debug(f"Scenario metrics: {context.metrics}")


def after_feature(context, feature):
    """Clean up after each feature."""
    logger.info(f"Completing feature: {feature.name}")
    
    # Clean up feature-specific resources
    if hasattr(context, 'feature_mocks'):
        context.feature_mocks.clear()
    
    # Drop all tables
    try:
        from services.ideas.models import Base as IdeasBase
        from services.voting.models import Base as VotingBase
        from services.decision.models import Base as DecisionBase
        
        DecisionBase.metadata.drop_all(context.test_engine)
        VotingBase.metadata.drop_all(context.test_engine)
        IdeasBase.metadata.drop_all(context.test_engine)
    except Exception as e:
        logger.warning(f"Error dropping tables: {e}")


def after_all(context):
    """Clean up after all tests."""
    logger.info("Cleaning up BDD test environment...")
    
    # Close database engine
    if hasattr(context, 'test_engine'):
        try:
            context.test_engine.dispose()
        except Exception as e:
            logger.warning(f"Error disposing database engine: {e}")
    
    # Clean up mocks
    if hasattr(context, 'mocks'):
        context.mocks.clear()
    
    logger.info("BDD test environment cleanup complete")


# Custom formatters and utilities
def format_table_data(table):
    """Convert Behave table to dictionary format."""
    if not table:
        return []
    
    return [dict(zip(table.headings, row.cells)) for row in table.rows]


def mock_api_response(status_code=200, data=None, headers=None):
    """Create mock API response."""
    response = Mock()
    response.status_code = status_code
    response.json.return_value = data or {}
    response.headers = headers or {}
    return response


def mock_database_operation(operation_type, result=None, side_effect=None):
    """Mock database operations."""
    mock_op = Mock()
    
    if side_effect:
        mock_op.side_effect = side_effect
    else:
        mock_op.return_value = result
    
    return mock_op


# Error handling for test scenarios
class TestDataError(Exception):
    """Raised when test data setup fails."""
    pass


class ServiceMockError(Exception):
    """Raised when service mocking fails."""
    pass


# Utility functions for test data generation
def generate_test_user(user_id=None, role='employee'):
    """Generate test user data."""
    user_id = user_id or f"test_user_{hash(str(os.urandom(8))) % 10000:04d}"
    
    return {
        'user_id': user_id,
        'user_email': f'{user_id}@company.com',
        'user_name': f'Test User {user_id}',
        'role': role,
        'permissions': ['read_ideas', 'submit_ideas', 'vote_ideas'] if role == 'employee' 
                      else ['read_ideas', 'submit_ideas', 'vote_ideas', 'make_decisions'],
        'token': f'mock_token_{user_id}'
    }


def generate_test_idea(title=None, category='innovation', status='published'):
    """Generate test idea data."""
    import random
    
    title = title or f"Test Idea {random.randint(1000, 9999)}"
    
    return {
        'title': title,
        'description': f"This is a test description for {title}",
        'category': category,
        'status': status,
        'user_id': 'test_user_001',
        'user_email': 'test_user_001@company.com',
        'user_name': 'Test User 001',
        'vote_count': random.randint(0, 50),
        'average_rating': round(random.uniform(1.0, 5.0), 2),
        'view_count': random.randint(10, 500)
    }


# Performance monitoring utilities
def measure_test_performance(func):
    """Decorator to measure test performance."""
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(context, *args, **kwargs):
        start_time = time.time()
        result = func(context, *args, **kwargs)
        end_time = time.time()
        
        # Store performance metrics
        if not hasattr(context, 'performance_metrics'):
            context.performance_metrics = {}
        
        context.performance_metrics[func.__name__] = {
            'duration': end_time - start_time,
            'timestamp': start_time
        }
        
        return result
    
    return wrapper


# Test data validation utilities
def validate_test_data(data, schema):
    """Validate test data against schema."""
    if not isinstance(data, dict):
        raise TestDataError("Test data must be a dictionary")
    
    for field, field_type in schema.items():
        if field not in data:
            raise TestDataError(f"Missing required field: {field}")
        
        if not isinstance(data[field], field_type):
            raise TestDataError(
                f"Field {field} must be of type {field_type.__name__}, "
                f"got {type(data[field]).__name__}"
            )
    
    return True


# Schemas for test data validation
USER_SCHEMA = {
    'user_id': str,
    'user_email': str,
    'user_name': str,
    'role': str
}

IDEA_SCHEMA = {
    'title': str,
    'description': str,
    'category': str,
    'status': str,
    'user_id': str
}

VOTE_SCHEMA = {
    'idea_id': int,
    'user_id': str,
    'vote_type': str
}

DECISION_SCHEMA = {
    'idea_id': int,
    'decision_type': str,
    'status': str,
    'decided_by': str
}