"""Shared pytest fixtures and configuration for all tests."""
import pytest
import os
import sys
import tempfile
import shutil
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import logging

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@pytest.fixture(scope="session")
def project_root_dir():
    """Get project root directory."""
    return project_root


@pytest.fixture(scope="session")
def test_environment():
    """Set up test environment configuration."""
    env_config = {
        "environment": "test",
        "debug": True,
        "testing": True,
        "database_url": "sqlite:///:memory:",
        "redis_url": "redis://localhost:6379/15",
        "secret_key": "test-secret-key",
        "algorithm": "HS256",
        "access_token_expire_minutes": 30,
        "ml_model_path": tempfile.mkdtemp(prefix="test_ml_models_"),
        "spark_master": "local[2]",
        "spark_app_name": "MindMesh Test",
        "log_level": "INFO"
    }
    
    # Set environment variables
    original_env = {}
    for key, value in env_config.items():
        env_key = f"MINDMESH_{key.upper()}"
        original_env[env_key] = os.environ.get(env_key)
        os.environ[env_key] = str(value)
    
    yield env_config
    
    # Restore original environment
    for env_key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = original_value
    
    # Cleanup ML model path
    if os.path.exists(env_config["ml_model_path"]):
        shutil.rmtree(env_config["ml_model_path"], ignore_errors=True)


@pytest.fixture
def mock_logger():
    """Create mock logger for testing."""
    logger = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    return logger


@pytest.fixture
def test_user_data():
    """Generate test user data."""
    return {
        "employee": {
            "user_id": "emp_001",
            "user_email": "employee@company.com",
            "user_name": "Test Employee",
            "role": "employee",
            "department": "Engineering",
            "permissions": ["read_ideas", "submit_ideas", "vote_ideas", "comment_ideas"]
        },
        "manager": {
            "user_id": "mgr_001",
            "user_email": "manager@company.com",
            "user_name": "Test Manager",
            "role": "manager",
            "department": "Management",
            "permissions": [
                "read_ideas", "submit_ideas", "vote_ideas", "comment_ideas",
                "make_decisions", "view_analytics", "manage_team"
            ]
        },
        "admin": {
            "user_id": "admin_001",
            "user_email": "admin@company.com",
            "user_name": "Test Admin",
            "role": "admin",
            "department": "IT",
            "permissions": ["*"]
        }
    }


@pytest.fixture
def mock_jwt_token():
    """Create mock JWT token for authentication testing."""
    def _create_token(user_data, expires_delta=None):
        """Create a mock JWT token."""
        import jwt
        from datetime import timedelta
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=30)
        
        to_encode = user_data.copy()
        to_encode.update({"exp": expire})
        
        # Use test secret key
        secret_key = "test-secret-key"
        algorithm = "HS256"
        
        try:
            encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
            return encoded_jwt
        except Exception:
            # Return mock token if JWT encoding fails
            return f"mock_token_{user_data.get('user_id', 'unknown')}"
    
    return _create_token


@pytest.fixture
def mock_database_operations():
    """Mock database operations for testing."""
    class MockDBOperations:
        def __init__(self):
            self.data_store = {}
            self.call_log = []
        
        def create(self, table, data):
            """Mock create operation."""
            if table not in self.data_store:
                self.data_store[table] = []
            
            # Assign ID if not present
            if 'id' not in data:
                data['id'] = len(self.data_store[table]) + 1
            
            self.data_store[table].append(data.copy())
            self.call_log.append(f"CREATE {table}")
            return data
        
        def read(self, table, filters=None):
            """Mock read operation."""
            self.call_log.append(f"READ {table}")
            
            if table not in self.data_store:
                return []
            
            data = self.data_store[table]
            
            if filters:
                filtered_data = []
                for item in data:
                    match = True
                    for key, value in filters.items():
                        if item.get(key) != value:
                            match = False
                            break
                    if match:
                        filtered_data.append(item)
                return filtered_data
            
            return data
        
        def update(self, table, id_value, updates):
            """Mock update operation."""
            self.call_log.append(f"UPDATE {table}")
            
            if table not in self.data_store:
                return None
            
            for item in self.data_store[table]:
                if item.get('id') == id_value:
                    item.update(updates)
                    return item
            
            return None
        
        def delete(self, table, id_value):
            """Mock delete operation."""
            self.call_log.append(f"DELETE {table}")
            
            if table not in self.data_store:
                return False
            
            original_length = len(self.data_store[table])
            self.data_store[table] = [
                item for item in self.data_store[table] 
                if item.get('id') != id_value
            ]
            
            return len(self.data_store[table]) < original_length
        
        def get_call_log(self):
            """Get log of all database operations."""
            return self.call_log.copy()
        
        def clear(self):
            """Clear all data and logs."""
            self.data_store.clear()
            self.call_log.clear()
    
    return MockDBOperations()


@pytest.fixture
def mock_redis_operations():
    """Mock Redis operations for testing."""
    class MockRedisOperations:
        def __init__(self):
            self.data_store = {}
            self.call_log = []
        
        def get(self, key):
            """Mock Redis GET operation."""
            self.call_log.append(f"GET {key}")
            return self.data_store.get(key)
        
        def set(self, key, value, ex=None):
            """Mock Redis SET operation."""
            self.call_log.append(f"SET {key}")
            self.data_store[key] = value
            return True
        
        def incr(self, key, amount=1):
            """Mock Redis INCR operation."""
            self.call_log.append(f"INCR {key}")
            current_value = int(self.data_store.get(key, 0))
            new_value = current_value + amount
            self.data_store[key] = str(new_value)
            return new_value
        
        def exists(self, key):
            """Mock Redis EXISTS operation."""
            self.call_log.append(f"EXISTS {key}")
            return key in self.data_store
        
        def delete(self, *keys):
            """Mock Redis DELETE operation."""
            deleted_count = 0
            for key in keys:
                self.call_log.append(f"DELETE {key}")
                if key in self.data_store:
                    del self.data_store[key]
                    deleted_count += 1
            return deleted_count
        
        def flushdb(self):
            """Mock Redis FLUSHDB operation."""
            self.call_log.append("FLUSHDB")
            self.data_store.clear()
            return True
        
        def ping(self):
            """Mock Redis PING operation."""
            self.call_log.append("PING")
            return True
        
        def get_call_log(self):
            """Get log of all Redis operations."""
            return self.call_log.copy()
        
        def clear(self):
            """Clear all data and logs."""
            self.data_store.clear()
            self.call_log.clear()
    
    return MockRedisOperations()


@pytest.fixture
def mock_file_operations():
    """Mock file system operations for testing."""
    class MockFileOperations:
        def __init__(self):
            self.file_store = {}
            self.call_log = []
        
        def write_file(self, file_path, content):
            """Mock file write operation."""
            self.call_log.append(f"WRITE {file_path}")
            self.file_store[file_path] = content
            return True
        
        def read_file(self, file_path):
            """Mock file read operation."""
            self.call_log.append(f"READ {file_path}")
            return self.file_store.get(file_path)
        
        def delete_file(self, file_path):
            """Mock file delete operation."""
            self.call_log.append(f"DELETE {file_path}")
            if file_path in self.file_store:
                del self.file_store[file_path]
                return True
            return False
        
        def exists(self, file_path):
            """Mock file exists check."""
            self.call_log.append(f"EXISTS {file_path}")
            return file_path in self.file_store
        
        def list_files(self, directory):
            """Mock directory listing."""
            self.call_log.append(f"LIST {directory}")
            return [
                path for path in self.file_store.keys()
                if path.startswith(directory)
            ]
        
        def get_call_log(self):
            """Get log of all file operations."""
            return self.call_log.copy()
        
        def clear(self):
            """Clear all files and logs."""
            self.file_store.clear()
            self.call_log.clear()
    
    return MockFileOperations()


@pytest.fixture
def mock_notification_service():
    """Mock notification service for testing."""
    class MockNotificationService:
        def __init__(self):
            self.sent_notifications = []
        
        def send_email(self, to_email, subject, body, attachments=None):
            """Mock email notification."""
            notification = {
                "type": "email",
                "to": to_email,
                "subject": subject,
                "body": body,
                "attachments": attachments or [],
                "timestamp": datetime.now(timezone.utc)
            }
            self.sent_notifications.append(notification)
            return True
        
        def send_push_notification(self, user_id, title, message, data=None):
            """Mock push notification."""
            notification = {
                "type": "push",
                "user_id": user_id,
                "title": title,
                "message": message,
                "data": data or {},
                "timestamp": datetime.now(timezone.utc)
            }
            self.sent_notifications.append(notification)
            return True
        
        def send_sms(self, phone_number, message):
            """Mock SMS notification."""
            notification = {
                "type": "sms",
                "phone": phone_number,
                "message": message,
                "timestamp": datetime.now(timezone.utc)
            }
            self.sent_notifications.append(notification)
            return True
        
        def get_sent_notifications(self, notification_type=None):
            """Get sent notifications, optionally filtered by type."""
            if notification_type:
                return [
                    n for n in self.sent_notifications 
                    if n["type"] == notification_type
                ]
            return self.sent_notifications.copy()
        
        def clear_notifications(self):
            """Clear all sent notifications."""
            self.sent_notifications.clear()
    
    return MockNotificationService()


@pytest.fixture
def test_data_factory():
    """Factory for generating test data."""
    import random
    from datetime import timedelta
    
    class TestDataFactory:
        @staticmethod
        def create_idea(overrides=None):
            """Create test idea data."""
            base_data = {
                "title": f"Test Idea {random.randint(1000, 9999)}",
                "description": "This is a test idea description with enough content to be meaningful for testing purposes.",
                "category": random.choice(["innovation", "improvement", "cost_saving", "revenue_generation"]),
                "status": "draft",
                "user_id": f"user_{random.randint(1, 100):03d}",
                "user_email": f"user{random.randint(1, 100)}@company.com",
                "user_name": f"Test User {random.randint(1, 100)}",
                "tags": [f"tag_{i}" for i in random.sample(range(50), random.randint(1, 5))],
                "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
            }
            
            if overrides:
                base_data.update(overrides)
            
            return base_data
        
        @staticmethod
        def create_vote(idea_id=None, overrides=None):
            """Create test vote data."""
            base_data = {
                "idea_id": idea_id or random.randint(1, 100),
                "user_id": f"voter_{random.randint(1, 100):03d}",
                "vote_type": random.choice(["upvote", "downvote", "rating"]),
                "rating": round(random.uniform(1.0, 5.0), 1) if random.random() > 0.5 else None,
                "created_at": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 72))
            }
            
            if overrides:
                base_data.update(overrides)
            
            return base_data
        
        @staticmethod
        def create_decision(idea_id=None, overrides=None):
            """Create test decision data."""
            base_data = {
                "idea_id": idea_id or random.randint(1, 100),
                "decision_type": random.choice(["implementation", "rejection", "modification", "deferral"]),
                "status": "pending",
                "decided_by": f"manager_{random.randint(1, 10):03d}",
                "summary": f"Test decision summary for idea {idea_id or 'unknown'}",
                "rationale": "This is a test rationale for the decision based on various factors.",
                "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 7))
            }
            
            if overrides:
                base_data.update(overrides)
            
            return base_data
        
        @staticmethod
        def create_user(role="employee", overrides=None):
            """Create test user data."""
            user_id = f"{role}_{random.randint(1, 100):03d}"
            base_data = {
                "user_id": user_id,
                "user_email": f"{user_id}@company.com",
                "user_name": f"Test {role.title()} {random.randint(1, 100)}",
                "role": role,
                "department": random.choice(["Engineering", "Marketing", "Sales", "HR", "Finance"]),
                "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(30, 365))
            }
            
            if overrides:
                base_data.update(overrides)
            
            return base_data
    
    return TestDataFactory()


@pytest.fixture
def test_metrics_collector():
    """Collect test metrics and performance data."""
    import time
    
    class TestMetricsCollector:
        def __init__(self):
            self.metrics = {}
            self.start_times = {}
        
        def start_timer(self, operation_name):
            """Start timing an operation."""
            self.start_times[operation_name] = time.time()
        
        def end_timer(self, operation_name):
            """End timing an operation and record duration."""
            if operation_name in self.start_times:
                duration = time.time() - self.start_times[operation_name]
                if operation_name not in self.metrics:
                    self.metrics[operation_name] = []
                self.metrics[operation_name].append(duration)
                del self.start_times[operation_name]
                return duration
            return None
        
        def record_metric(self, metric_name, value):
            """Record a custom metric."""
            if metric_name not in self.metrics:
                self.metrics[metric_name] = []
            self.metrics[metric_name].append(value)
        
        def get_average(self, metric_name):
            """Get average value for a metric."""
            if metric_name in self.metrics and self.metrics[metric_name]:
                return sum(self.metrics[metric_name]) / len(self.metrics[metric_name])
            return None
        
        def get_metrics_summary(self):
            """Get summary of all collected metrics."""
            summary = {}
            for metric_name, values in self.metrics.items():
                if values:
                    summary[metric_name] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "average": sum(values) / len(values),
                        "total": sum(values)
                    }
            return summary
        
        def clear_metrics(self):
            """Clear all collected metrics."""
            self.metrics.clear()
            self.start_times.clear()
    
    return TestMetricsCollector()


# Configure pytest
def pytest_configure(config):
    """Configure pytest with custom markers."""
    # Add custom markers
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "bdd: mark test as BDD test")
    config.addinivalue_line("markers", "api: mark test as API test")
    config.addinivalue_line("markers", "database: mark test as requiring database")
    config.addinivalue_line("markers", "redis: mark test as requiring Redis")
    config.addinivalue_line("markers", "spark: mark test as requiring Spark")
    config.addinivalue_line("markers", "ml: mark test as ML/analytics test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "external: mark test as requiring external services")


def pytest_runtest_setup(item):
    """Setup for each test run."""
    # Set up test isolation
    if hasattr(item, 'cls') and item.cls:
        if not hasattr(item.cls, '_test_setup_done'):
            item.cls._test_setup_done = True


def pytest_runtest_teardown(item, nextitem):
    """Teardown after each test run."""
    # Clean up any global state
    pass


def pytest_sessionstart(session):
    """Actions to perform at the start of test session."""
    print("\n🚀 Starting MindMesh test suite...")
    print("=" * 50)


def pytest_sessionfinish(session, exitstatus):
    """Actions to perform at the end of test session."""
    print("=" * 50)
    if exitstatus == 0:
        print("✅ All tests completed successfully!")
    else:
        print(f"❌ Test suite completed with exit status: {exitstatus}")
    print("🏁 MindMesh test suite finished.")


# Auto-use fixtures for test environment setup
@pytest.fixture(autouse=True)
def setup_test_logging():
    """Set up logging configuration for tests."""
    import logging
    
    # Configure logging for tests
    logging.getLogger().setLevel(logging.WARNING)
    
    # Suppress noisy loggers
    for logger_name in ['urllib3', 'requests', 'sqlalchemy']:
        logging.getLogger(logger_name).setLevel(logging.ERROR)


@pytest.fixture(autouse=True, scope="session")
def verify_test_environment():
    """Verify test environment setup."""
    # Check Python version
    import sys
    assert sys.version_info >= (3, 8), "Python 3.8+ required for tests"
    
    # Verify project structure
    assert os.path.exists(project_root), "Project root directory not found"
    assert os.path.exists(os.path.join(project_root, "services")), "Services directory not found"
    
    yield
    
    # Post-test cleanup
    # Any global cleanup can go here