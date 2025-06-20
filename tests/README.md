# MindMesh Testing Framework

## Overview

This comprehensive testing framework covers all aspects of the MindMesh platform, ensuring robust functionality across all services and components. The testing structure is designed to impress hiring teams with its thoroughness, business scenario coverage, and professional approach.

## Testing Structure

```
tests/
├── bdd/                          # Behavior-Driven Development tests
│   ├── features/                 # Gherkin feature files
│   │   ├── ideas.feature         # Idea management scenarios
│   │   ├── voting.feature        # Voting system scenarios
│   │   ├── decisions.feature     # Decision making scenarios
│   │   └── analytics.feature     # Analytics & ML scenarios
│   ├── steps/                    # Python step definitions
│   │   ├── ideas_steps.py        # Ideas feature steps
│   │   ├── voting_steps.py       # Voting feature steps
│   │   ├── decisions_steps.py    # Decision feature steps
│   │   └── analytics_steps.py    # Analytics feature steps
│   └── environment.py            # Behave configuration
├── unit/                         # Unit tests
│   ├── test_ideas.py            # Ideas service unit tests
│   ├── test_voting.py           # Voting service unit tests
│   ├── test_decisions.py        # Decision service unit tests
│   └── test_analytics.py        # Analytics service unit tests
├── integration/                  # Integration tests
│   ├── test_api_integration.py   # End-to-end API tests
│   ├── test_spark_integration.py # PySpark integration tests
│   └── conftest.py              # Integration test fixtures
├── conftest.py                  # Shared pytest fixtures
└── README.md                    # This file
```

## Test Categories

### 1. Unit Tests (`tests/unit/`)

**Purpose**: Test individual components in isolation
**Coverage**: 
- Model validation and business logic
- Service layer functionality
- Schema validation
- Error handling
- Edge cases

**Key Features**:
- Fast execution (< 5 seconds total)
- No external dependencies
- Comprehensive mocking
- High code coverage (>90%)

**Example Business Scenarios**:
- Idea creation with validation
- Vote aggregation calculations
- Decision workflow transitions
- ML model prediction logic

### 2. Integration Tests (`tests/integration/`)

**Purpose**: Test component interactions and end-to-end workflows
**Coverage**:
- API endpoint functionality
- Database interactions
- Service-to-service communication
- External service integration
- Performance requirements

**Key Features**:
- Real database operations (SQLite for tests)
- API client testing
- PySpark integration
- Performance monitoring
- Data consistency verification

**Example Business Scenarios**:
- Complete idea lifecycle (creation → voting → decision)
- Concurrent voting scenarios
- Cross-service data synchronization
- Analytics pipeline execution

### 3. BDD Tests (`tests/bdd/`)

**Purpose**: Test business scenarios in natural language
**Coverage**:
- User journey testing
- Business rule validation
- Stakeholder acceptance criteria
- Complex workflow scenarios

**Key Features**:
- Gherkin syntax for readability
- Stakeholder-friendly scenarios
- Comprehensive business logic coverage
- Real-world usage patterns

**Example Business Scenarios**:
- Employee submits innovation idea
- Manager reviews and decides on ideas
- Analytics identifies trending topics
- Committee-based decision making

## Running Tests

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Additional test dependencies
pip install pytest pytest-cov behave pytest-mock pytest-asyncio
```

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=services --cov-report=html

# Run specific service tests
pytest tests/unit/test_ideas.py -v
```

### Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run API integration tests only
pytest tests/integration/test_api_integration.py -v

# Run Spark integration tests (requires PySpark)
pytest tests/integration/test_spark_integration.py -v -m spark
```

### BDD Tests

```bash
# Run all BDD tests
behave tests/bdd/

# Run specific feature
behave tests/bdd/features/ideas.feature

# Run with specific tags
behave tests/bdd/ --tags=@voting
```

### All Tests

```bash
# Run complete test suite
pytest tests/ -v --tb=short

# Run with coverage and generate report
pytest tests/ --cov=services --cov-report=html --cov-report=term
```

## Test Configuration

### Environment Variables

```bash
# Test environment configuration
export MINDMESH_ENV=test
export MINDMESH_DATABASE_URL=sqlite:///:memory:
export MINDMESH_REDIS_URL=redis://localhost:6379/15
export ML_MODEL_PATH=/tmp/test_ml_models
export SPARK_MASTER=local[2]
```

### Mock Strategies

The testing framework uses comprehensive mocking strategies:

1. **Database Mocking**: SQLite in-memory for fast tests
2. **Redis Mocking**: Mock Redis client for caching tests
3. **Spark Mocking**: Mock Spark sessions for ML tests
4. **External Services**: Mock email, notifications, file storage
5. **Authentication**: Mock JWT tokens and user contexts

### Test Data Management

- **Fixtures**: Comprehensive pytest fixtures for data setup
- **Factories**: Test data factories for generating realistic data
- **Seeds**: Predefined test datasets for consistent scenarios
- **Cleanup**: Automatic cleanup after each test

## Business Scenarios Covered

### Ideas Management
- ✅ Employee idea submission and validation
- ✅ Idea publishing and visibility controls
- ✅ Collaborative commenting and discussions
- ✅ Idea search and categorization
- ✅ Idea lifecycle management
- ✅ Bulk operations and data migration

### Voting System
- ✅ Democratic voting with fraud prevention
- ✅ Real-time vote aggregation and leaderboards
- ✅ Rating systems with detailed feedback
- ✅ Controversy detection and flagging
- ✅ Expert opinion weighting
- ✅ Voting campaigns and time-based contests

### Decision Making
- ✅ Automated decision suggestions based on criteria
- ✅ Committee-based collaborative decision making
- ✅ Decision workflow and status management
- ✅ Impact analysis and ROI calculations
- ✅ Decision audit trails and governance
- ✅ Template-based decision consistency

### Analytics & ML
- ✅ Idea clustering and pattern recognition
- ✅ Topic modeling and trend analysis
- ✅ Success prediction using machine learning
- ✅ Real-time streaming analytics
- ✅ Employee engagement measurement
- ✅ Business impact tracking and ROI analysis

## Performance Requirements

### Response Time Targets
- **API Endpoints**: < 200ms for simple operations
- **Database Queries**: < 100ms for standard queries
- **ML Processing**: < 5 seconds for batch operations
- **Search Operations**: < 500ms for full-text search

### Scalability Targets
- **Concurrent Users**: 1000+ simultaneous users
- **Data Volume**: 100,000+ ideas with associated data
- **Vote Processing**: 10,000+ votes per minute
- **Analytics Processing**: Real-time stream processing

### Reliability Targets
- **API Availability**: 99.9% uptime
- **Data Consistency**: ACID compliance for critical operations
- **Error Rate**: < 0.1% for user-facing operations
- **Recovery Time**: < 5 minutes for service recovery

## Quality Metrics

### Code Coverage
- **Unit Tests**: >90% line coverage
- **Integration Tests**: >80% feature coverage
- **BDD Tests**: 100% business scenario coverage

### Test Execution Time
- **Unit Tests**: < 30 seconds total
- **Integration Tests**: < 5 minutes total
- **BDD Tests**: < 10 minutes total
- **Full Suite**: < 15 minutes total

### Test Reliability
- **Flaky Test Rate**: < 1%
- **False Positive Rate**: < 0.5%
- **Test Maintenance**: Monthly review cycle

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:6
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov behave
      - name: Run unit tests
        run: pytest tests/unit/ --cov=services
      - name: Run integration tests
        run: pytest tests/integration/
      - name: Run BDD tests
        run: behave tests/bdd/
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest-unit
        name: pytest unit tests
        entry: pytest tests/unit/
        language: system
        pass_filenames: false
      - id: black
        name: black
        entry: black
        language: system
        types: [python]
      - id: flake8
        name: flake8
        entry: flake8
        language: system
        types: [python]
```

## Test Data Examples

### Sample Test Scenarios

**High-Engagement Innovation Idea**:
```python
{
    "title": "AI-Powered Customer Support Automation",
    "description": "Implement machine learning chatbot to handle 80% of customer inquiries automatically, reducing response time and improving satisfaction",
    "category": "innovation",
    "vote_count": 85,
    "average_rating": 4.7,
    "engagement_score": 0.89,
    "status": "under_review"
}
```

**Committee Decision Scenario**:
```python
{
    "committee_members": [
        {"id": "mgr001", "role": "Product Manager", "vote": "approve"},
        {"id": "mgr002", "role": "Engineering Manager", "vote": "approve"},
        {"id": "mgr003", "role": "Finance Manager", "vote": "modify"}
    ],
    "decision_criteria": {
        "min_vote_count": 20,
        "min_rating": 4.0,
        "max_cost": 100000
    }
}
```

## Troubleshooting

### Common Issues

**PySpark Tests Failing**:
```bash
# Install Java 8 or 11
sudo apt-get install openjdk-8-jdk

# Set JAVA_HOME
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
```

**Redis Connection Issues**:
```bash
# Start Redis server
redis-server --daemonize yes --port 6379

# Or use Docker
docker run -d -p 6379:6379 redis:6
```

**Database Migration Issues**:
```bash
# Reset test database
rm -f test.db
pytest tests/unit/ --tb=short
```

### Debug Mode

```bash
# Run tests in debug mode
pytest tests/ -v -s --tb=long --pdb

# Run specific test with debugging
pytest tests/unit/test_ideas.py::TestIdeaModel::test_create_idea -vvv -s
```

## Best Practices

### Writing New Tests

1. **Follow AAA Pattern**: Arrange, Act, Assert
2. **Use Descriptive Names**: `test_employee_can_submit_innovation_idea_successfully`
3. **Test One Thing**: Each test should verify one specific behavior
4. **Mock External Dependencies**: Keep tests isolated and fast
5. **Use Fixtures**: Leverage pytest fixtures for setup and teardown

### Test Organization

1. **Group Related Tests**: Use test classes for logical grouping
2. **Tag Tests Appropriately**: Use pytest markers for test categories
3. **Document Complex Scenarios**: Add docstrings for business logic tests
4. **Keep Tests DRY**: Use helper functions for repeated operations

### Performance Optimization

1. **Parallel Execution**: Use pytest-xdist for parallel test runs
2. **Test Data Optimization**: Use minimal data sets for fast execution
3. **Mock Heavy Operations**: Mock database, network, and ML operations
4. **Profile Slow Tests**: Identify and optimize bottlenecks

## Contributing

When adding new features, ensure comprehensive test coverage:

1. **Unit Tests**: Test all new functions and methods
2. **Integration Tests**: Test API endpoints and service interactions
3. **BDD Tests**: Add business scenarios for user-facing features
4. **Documentation**: Update test documentation and examples

## Metrics Dashboard

Track testing metrics and quality indicators:

- **Test Coverage**: Line and branch coverage percentages
- **Test Execution Time**: Performance trends over time
- **Test Reliability**: Success rates and flaky test identification
- **Bug Detection Rate**: Tests catching bugs before production
- **Business Scenario Coverage**: Stakeholder requirement validation

This comprehensive testing framework ensures the MindMesh platform meets the highest quality standards while providing confidence in business-critical functionality.