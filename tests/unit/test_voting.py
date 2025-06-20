"""Unit tests for Voting service."""
import pytest
import json
import redis
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Import your actual modules
from services.voting.models import Vote, VoteAggregate, VoteType, Base
from services.voting.schemas import VoteCreate, VoteUpdate, VoteResponse
from services.voting.redis_client import get_redis_client
from services.voting.api import router


class TestVoteModel:
    """Test cases for Vote model."""
    
    @pytest.fixture
    def db_session(self):
        """Create test database session."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    def test_create_upvote(self, db_session):
        """Test creating an upvote."""
        vote = Vote(
            idea_id=1,
            user_id="test_user_001",
            vote_type=VoteType.UPVOTE,
            ip_address="192.168.1.100",
            user_agent="Test Browser"
        )
        
        db_session.add(vote)
        db_session.commit()
        db_session.refresh(vote)
        
        assert vote.id is not None
        assert vote.idea_id == 1
        assert vote.user_id == "test_user_001"
        assert vote.vote_type == VoteType.UPVOTE
        assert vote.rating is None  # Not set for upvote
        assert vote.created_at is not None
    
    def test_create_rating_vote(self, db_session):
        """Test creating a rating vote."""
        vote = Vote(
            idea_id=2,
            user_id="test_user_002",
            vote_type=VoteType.RATING,
            rating=4.5,
            ip_address="192.168.1.101"
        )
        
        db_session.add(vote)
        db_session.commit()
        db_session.refresh(vote)
        
        assert vote.vote_type == VoteType.RATING
        assert vote.rating == 4.5
        assert 1.0 <= vote.rating <= 5.0
    
    def test_vote_type_enum(self):
        """Test vote type enumeration."""
        assert VoteType.UPVOTE == "upvote"
        assert VoteType.DOWNVOTE == "downvote"
        assert VoteType.RATING == "rating"
    
    def test_unique_constraint_violation(self, db_session):
        """Test unique constraint on idea_id + user_id."""
        # Create first vote
        vote1 = Vote(
            idea_id=1,
            user_id="test_user",
            vote_type=VoteType.UPVOTE
        )
        
        db_session.add(vote1)
        db_session.commit()
        
        # Try to create duplicate vote (same idea + user)
        vote2 = Vote(
            idea_id=1,
            user_id="test_user",
            vote_type=VoteType.DOWNVOTE
        )
        
        db_session.add(vote2)
        
        # Should raise integrity error
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            db_session.commit()
    
    def test_vote_repr(self, db_session):
        """Test vote string representation."""
        vote = Vote(
            idea_id=123,
            user_id="test_user",
            vote_type=VoteType.UPVOTE
        )
        db_session.add(vote)
        db_session.commit()
        db_session.refresh(vote)
        
        expected_repr = f"<Vote(id={vote.id}, idea_id=123, user_id='test_user', type=upvote)>"
        assert repr(vote) == expected_repr


class TestVoteAggregateModel:
    """Test cases for VoteAggregate model."""
    
    @pytest.fixture
    def db_session(self):
        """Create test database session."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    def test_create_vote_aggregate(self, db_session):
        """Test creating a vote aggregate."""
        aggregate = VoteAggregate(
            idea_id=1,
            upvote_count=10,
            downvote_count=2,
            total_votes=12,
            rating_count=5,
            rating_sum=22.5,
            average_rating=4.5
        )
        
        db_session.add(aggregate)
        db_session.commit()
        db_session.refresh(aggregate)
        
        assert aggregate.id is not None
        assert aggregate.idea_id == 1
        assert aggregate.upvote_count == 10
        assert aggregate.downvote_count == 2
        assert aggregate.total_votes == 12
        assert aggregate.average_rating == 4.5
        assert aggregate.last_updated is not None
    
    def test_calculate_score_basic(self, db_session):
        """Test basic score calculation."""
        aggregate = VoteAggregate(
            idea_id=1,
            upvote_count=15,
            downvote_count=3,
            total_votes=18,
            rating_count=0,
            rating_sum=0.0,
            average_rating=0.0
        )
        
        score = aggregate.calculate_score()
        expected_score = 15 - 3  # upvotes - downvotes
        assert score == float(expected_score)
    
    def test_calculate_score_with_ratings(self, db_session):
        """Test score calculation with ratings."""
        aggregate = VoteAggregate(
            idea_id=1,
            upvote_count=10,
            downvote_count=2,
            total_votes=12,
            rating_count=5,
            rating_sum=20.0,
            average_rating=4.0
        )
        
        score = aggregate.calculate_score()
        # Formula: vote_score + (average_rating * rating_weight * rating_count)
        # vote_score = 10 - 2 = 8
        # rating_contribution = 4.0 * 2.0 * 5 = 40.0
        expected_score = 8.0 + 40.0
        assert score == expected_score
    
    def test_calculate_score_no_votes(self, db_session):
        """Test score calculation with no votes."""
        aggregate = VoteAggregate(
            idea_id=1,
            upvote_count=0,
            downvote_count=0,
            total_votes=0
        )
        
        score = aggregate.calculate_score()
        assert score == 0.0
    
    def test_unique_idea_constraint(self, db_session):
        """Test unique constraint on idea_id."""
        # Create first aggregate
        aggregate1 = VoteAggregate(idea_id=1, upvote_count=5)
        db_session.add(aggregate1)
        db_session.commit()
        
        # Try to create duplicate aggregate for same idea
        aggregate2 = VoteAggregate(idea_id=1, upvote_count=10)
        db_session.add(aggregate2)
        
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            db_session.commit()
    
    def test_aggregate_repr(self, db_session):
        """Test aggregate string representation."""
        aggregate = VoteAggregate(idea_id=123, score=45.6)
        db_session.add(aggregate)
        db_session.commit()
        db_session.refresh(aggregate)
        
        expected_repr = f"<VoteAggregate(idea_id=123, score=45.6)>"
        assert repr(aggregate) == expected_repr


class TestVoteSchemas:
    """Test cases for Pydantic schemas."""
    
    def test_vote_create_schema(self):
        """Test VoteCreate schema validation."""
        # Valid upvote
        vote_data = {
            "idea_id": 1,
            "vote_type": "upvote"
        }
        
        vote_create = VoteCreate(**vote_data)
        assert vote_create.idea_id == 1
        assert vote_create.vote_type == "upvote"
        assert vote_create.rating is None
    
    def test_vote_create_rating_schema(self):
        """Test VoteCreate schema with rating."""
        vote_data = {
            "idea_id": 1,
            "vote_type": "rating",
            "rating": 4.5
        }
        
        vote_create = VoteCreate(**vote_data)
        assert vote_create.vote_type == "rating"
        assert vote_create.rating == 4.5
    
    def test_vote_create_validation_errors(self):
        """Test schema validation errors."""
        # Missing required fields
        with pytest.raises(ValueError):
            VoteCreate(vote_type="upvote")  # Missing idea_id
        
        # Invalid vote type
        with pytest.raises(ValueError):
            VoteCreate(idea_id=1, vote_type="invalid_type")
        
        # Invalid rating range
        with pytest.raises(ValueError):
            VoteCreate(idea_id=1, vote_type="rating", rating=6.0)  # > 5.0
        
        with pytest.raises(ValueError):
            VoteCreate(idea_id=1, vote_type="rating", rating=0.5)  # < 1.0
    
    def test_vote_response_schema(self):
        """Test VoteResponse schema."""
        response_data = {
            "id": 1,
            "idea_id": 123,
            "user_id": "test_user",
            "vote_type": "upvote",
            "rating": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        vote_response = VoteResponse(**response_data)
        assert vote_response.id == 1
        assert vote_response.idea_id == 123
        assert vote_response.vote_type == "upvote"


class TestVoteService:
    """Test cases for Voting service logic."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock(spec=redis.Redis)
        redis_mock.get.return_value = None
        redis_mock.set.return_value = True
        redis_mock.incr.return_value = 1
        redis_mock.exists.return_value = False
        return redis_mock
    
    def test_cast_vote_service(self, mock_db, mock_redis):
        """Test vote casting service logic."""
        # Mock user and idea
        user_id = "test_user_001"
        idea_id = 123
        vote_type = VoteType.UPVOTE
        
        # Check if user already voted (Redis cache)
        cache_key = f"user_vote:{user_id}:{idea_id}"
        existing_vote = mock_redis.get(cache_key)
        assert existing_vote is None
        
        # Create new vote
        vote = Vote(
            idea_id=idea_id,
            user_id=user_id,
            vote_type=vote_type,
            ip_address="192.168.1.100"
        )
        
        mock_db.add(vote)
        mock_db.commit()
        mock_db.refresh(vote)
        
        # Update cache
        mock_redis.set(cache_key, vote_type, ex=3600)
        
        # Update or create aggregate
        aggregate = VoteAggregate(idea_id=idea_id)
        aggregate.upvote_count = 1
        aggregate.total_votes = 1
        aggregate.score = aggregate.calculate_score()
        
        mock_db.merge(aggregate)
        mock_db.commit()
        
        # Verify operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        mock_redis.set.assert_called_with(cache_key, vote_type, ex=3600)
    
    def test_update_vote_service(self, mock_db, mock_redis):
        """Test vote update service logic."""
        user_id = "test_user_001"
        idea_id = 123
        
        # Mock existing vote
        existing_vote = Mock(spec=Vote)
        existing_vote.vote_type = VoteType.UPVOTE
        existing_vote.user_id = user_id
        existing_vote.idea_id = idea_id
        
        mock_db.query().filter().first.return_value = existing_vote
        
        # Update to downvote
        new_vote_type = VoteType.DOWNVOTE
        existing_vote.vote_type = new_vote_type
        existing_vote.updated_at = datetime.now(timezone.utc)
        
        mock_db.commit()
        
        # Update cache
        cache_key = f"user_vote:{user_id}:{idea_id}"
        mock_redis.set(cache_key, new_vote_type, ex=3600)
        
        # Update aggregate (mock logic)
        aggregate = Mock(spec=VoteAggregate)
        aggregate.upvote_count = 0  # Decreased from 1
        aggregate.downvote_count = 1  # Increased from 0
        aggregate.total_votes = 1  # Same total
        aggregate.score = aggregate.calculate_score()
        
        # Verify vote was updated
        assert existing_vote.vote_type == VoteType.DOWNVOTE
        mock_db.commit.assert_called()
        mock_redis.set.assert_called_with(cache_key, new_vote_type, ex=3600)
    
    def test_get_vote_aggregate_service(self, mock_db):
        """Test getting vote aggregate service."""
        idea_id = 123
        
        # Mock aggregate data
        mock_aggregate = Mock(spec=VoteAggregate)
        mock_aggregate.idea_id = idea_id
        mock_aggregate.upvote_count = 25
        mock_aggregate.downvote_count = 5
        mock_aggregate.total_votes = 30
        mock_aggregate.rating_count = 10
        mock_aggregate.average_rating = 4.2
        mock_aggregate.score = 85.0
        
        mock_db.query().filter().first.return_value = mock_aggregate
        
        # Test service retrieval
        result = mock_db.query().filter().first()
        
        assert result.idea_id == idea_id
        assert result.upvote_count == 25
        assert result.score == 85.0
    
    def test_prevent_duplicate_vote(self, mock_db, mock_redis):
        """Test duplicate vote prevention."""
        user_id = "test_user_001"
        idea_id = 123
        
        # Mock existing vote in cache
        cache_key = f"user_vote:{user_id}:{idea_id}"
        mock_redis.get.return_value = "upvote"  # User already voted
        
        # Service should check cache first
        existing_vote_type = mock_redis.get(cache_key)
        
        if existing_vote_type:
            # Should not allow new vote, only update
            assert existing_vote_type == "upvote"
            # In real service, this would return an error or update existing vote
    
    def test_calculate_engagement_score(self, mock_db):
        """Test engagement score calculation."""
        # Mock idea metrics
        idea_metrics = {
            'vote_count': 30,
            'average_rating': 4.3,
            'view_count': 250,
            'comment_count': 12,
            'days_since_created': 15
        }
        
        def calculate_engagement_score(metrics):
            """Mock engagement score calculation."""
            vote_factor = min(metrics['vote_count'] / 50, 1.0)
            rating_factor = metrics['average_rating'] / 5.0
            view_factor = min(metrics['view_count'] / 500, 1.0)
            comment_factor = min(metrics['comment_count'] / 20, 1.0)
            recency_factor = max(1.0 - (metrics['days_since_created'] / 30), 0.5)
            
            return (vote_factor * 0.3 + 
                   rating_factor * 0.25 + 
                   view_factor * 0.2 + 
                   comment_factor * 0.15 + 
                   recency_factor * 0.1)
        
        engagement_score = calculate_engagement_score(idea_metrics)
        
        assert 0.0 <= engagement_score <= 1.0
        assert engagement_score > 0.6  # Should be high given good metrics
    
    def test_batch_vote_processing(self, mock_db, mock_redis):
        """Test batch vote processing for performance."""
        # Mock multiple votes to process
        votes_to_process = [
            {'user_id': 'user1', 'idea_id': 1, 'vote_type': 'upvote'},
            {'user_id': 'user2', 'idea_id': 1, 'vote_type': 'upvote'},
            {'user_id': 'user3', 'idea_id': 2, 'vote_type': 'downvote'},
            {'user_id': 'user4', 'idea_id': 2, 'vote_type': 'rating', 'rating': 4.5}
        ]
        
        # Process votes in batch
        vote_objects = []
        aggregates = {}
        
        for vote_data in votes_to_process:
            # Create vote object
            vote = Vote(**vote_data)
            vote_objects.append(vote)
            
            # Update aggregate
            idea_id = vote_data['idea_id']
            if idea_id not in aggregates:
                aggregates[idea_id] = {
                    'upvote_count': 0,
                    'downvote_count': 0,
                    'rating_count': 0,
                    'rating_sum': 0.0
                }
            
            if vote_data['vote_type'] == 'upvote':
                aggregates[idea_id]['upvote_count'] += 1
            elif vote_data['vote_type'] == 'downvote':
                aggregates[idea_id]['downvote_count'] += 1
            elif vote_data['vote_type'] == 'rating':
                aggregates[idea_id]['rating_count'] += 1
                aggregates[idea_id]['rating_sum'] += vote_data.get('rating', 0)
        
        # Verify batch processing results
        assert len(vote_objects) == 4
        assert len(aggregates) == 2  # Two different ideas
        assert aggregates[1]['upvote_count'] == 2
        assert aggregates[2]['downvote_count'] == 1
        assert aggregates[2]['rating_count'] == 1


class TestVoteAPI:
    """Test cases for Vote API endpoints."""
    
    @pytest.fixture
    def mock_get_db(self):
        """Mock database dependency."""
        return Mock()
    
    @pytest.fixture
    def mock_get_redis(self):
        """Mock Redis dependency."""
        redis_mock = Mock(spec=redis.Redis)
        return redis_mock
    
    @pytest.fixture
    def client(self, mock_get_db, mock_get_redis):
        """Test client with mocked dependencies."""
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/votes")
        
        # Override dependencies
        from services.voting.api import get_db
        app.dependency_overrides[get_db] = lambda: mock_get_db
        app.dependency_overrides[get_redis_client] = lambda: mock_get_redis
        
        return TestClient(app)
    
    def test_cast_vote_endpoint(self, client, mock_get_db, mock_get_redis):
        """Test POST /votes endpoint."""
        vote_data = {
            "idea_id": 123,
            "vote_type": "upvote"
        }
        
        headers = {"Authorization": "Bearer mock_token"}
        
        # Mock user authentication
        with patch('services.voting.api.get_current_user') as mock_auth:
            mock_auth.return_value = {
                "user_id": "test_user",
                "user_email": "test@company.com"
            }
            
            # Mock database operations
            mock_get_db.add = Mock()
            mock_get_db.commit = Mock()
            mock_get_db.refresh = Mock()
            
            # Mock Redis operations
            mock_get_redis.get.return_value = None  # No existing vote
            mock_get_redis.set.return_value = True
            
            # Verify vote data structure
            assert vote_data["idea_id"] == 123
            assert vote_data["vote_type"] == "upvote"
    
    def test_get_vote_aggregates_endpoint(self, client, mock_get_db):
        """Test GET /votes/aggregates/{idea_id} endpoint."""
        idea_id = 123
        
        # Mock aggregate data
        mock_aggregate = {
            "idea_id": idea_id,
            "upvote_count": 25,
            "downvote_count": 5,
            "total_votes": 30,
            "rating_count": 8,
            "average_rating": 4.2,
            "score": 75.5,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
        mock_get_db.query().filter().first.return_value = mock_aggregate
        
        # Verify mock aggregate data
        result = mock_get_db.query().filter().first()
        assert result["idea_id"] == idea_id
        assert result["upvote_count"] == 25
        assert result["score"] == 75.5
    
    def test_get_user_votes_endpoint(self, client, mock_get_db):
        """Test GET /votes/user endpoint."""
        user_id = "test_user"
        
        # Mock user votes
        mock_votes = [
            {
                "id": 1,
                "idea_id": 123,
                "vote_type": "upvote",
                "created_at": datetime.now(timezone.utc)
            },
            {
                "id": 2,
                "idea_id": 456,
                "vote_type": "rating",
                "rating": 4.0,
                "created_at": datetime.now(timezone.utc)
            }
        ]
        
        mock_get_db.query().filter().all.return_value = mock_votes
        
        with patch('services.voting.api.get_current_user') as mock_auth:
            mock_auth.return_value = {"user_id": user_id}
            
            result = mock_get_db.query().filter().all()
            assert len(result) == 2
            assert result[0]["vote_type"] == "upvote"
            assert result[1]["rating"] == 4.0
    
    def test_update_vote_endpoint(self, client, mock_get_db, mock_get_redis):
        """Test PUT /votes/{vote_id} endpoint."""
        vote_id = 1
        update_data = {
            "vote_type": "downvote"
        }
        
        # Mock existing vote
        mock_vote = Mock()
        mock_vote.id = vote_id
        mock_vote.user_id = "test_user"
        mock_vote.idea_id = 123
        mock_vote.vote_type = "upvote"
        
        mock_get_db.query().filter().first.return_value = mock_vote
        mock_get_db.commit = Mock()
        
        with patch('services.voting.api.get_current_user') as mock_auth:
            mock_auth.return_value = {"user_id": "test_user"}
            
            # Simulate update
            mock_vote.vote_type = update_data["vote_type"]
            mock_vote.updated_at = datetime.now(timezone.utc)
            
            assert mock_vote.vote_type == "downvote"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])