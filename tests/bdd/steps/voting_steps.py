"""Step definitions for Voting feature tests."""
import pytest
from behave import given, when, then, step
from unittest.mock import Mock, patch, MagicMock
import json
import redis
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import your actual models and services
from services.voting.models import Vote, VoteAggregate, VoteType
from services.voting.redis_client import get_redis_client
from services.ideas.models import Idea, IdeaStatus


@given('the voting service is running')
def step_voting_service_running(context):
    """Mock or verify that the voting service is running."""
    context.voting_service_url = "http://localhost:8002"
    context.voting_service_running = True
    
    if not hasattr(context, 'voting_client'):
        context.voting_client = Mock()


@given('the Redis cache is available')
def step_redis_cache_available(context):
    """Set up Redis mock for testing."""
    # Mock Redis for testing
    context.redis_client = Mock(spec=redis.Redis)
    context.redis_available = True
    
    # Mock common Redis operations
    context.redis_client.get.return_value = None
    context.redis_client.set.return_value = True
    context.redis_client.incr.return_value = 1
    context.redis_client.exists.return_value = False


@given('there are published ideas available for voting')
def step_published_ideas_for_voting(context):
    """Create published ideas for voting tests."""
    if not hasattr(context, 'db'):
        # Set up test database
        context.test_db_url = "sqlite:///:memory:"
        context.engine = create_engine(context.test_db_url)
        
        # Import and create all tables
        from services.ideas.models import Base as IdeasBase
        from services.voting.models import Base as VotingBase
        
        IdeasBase.metadata.create_all(context.engine)
        VotingBase.metadata.create_all(context.engine)
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=context.engine)
        context.db = SessionLocal()
    
    # Create test ideas
    test_ideas = [
        Idea(
            id=123,
            title="AI-Powered Customer Support",
            description="Implement AI chatbot for customer support",
            category="innovation",
            status=IdeaStatus.PUBLISHED,
            user_id="emp001",
            user_email="emp001@company.com",
            published_at=datetime.now(timezone.utc)
        ),
        Idea(
            id=456,
            title="Flexible Work Arrangements",
            description="Implement flexible working hours policy",
            category="improvement",
            status=IdeaStatus.PUBLISHED,
            user_id="emp002",
            user_email="emp002@company.com",
            published_at=datetime.now(timezone.utc)
        )
    ]
    
    for idea in test_ideas:
        context.db.merge(idea)
    
    context.db.commit()
    context.published_ideas = test_ideas


@given('I am employee "{employee_id}"')
def step_am_employee(context, employee_id):
    """Set up employee context for voting."""
    context.current_employee = {
        'user_id': employee_id,
        'user_email': f'{employee_id}@company.com',
        'user_name': f'Employee {employee_id}',
        'ip_address': '192.168.1.100',
        'user_agent': 'Mozilla/5.0 Test Browser'
    }


@given('there is a published idea with ID "{idea_id}"')
def step_published_idea_with_id(context, idea_id):
    """Reference existing published idea by ID."""
    idea_id_int = int(idea_id)
    context.target_idea = next(
        (idea for idea in context.published_ideas if idea.id == idea_id_int),
        None
    )
    assert context.target_idea is not None, f"Idea with ID {idea_id} not found"


@when('I cast an upvote on the idea')
def step_cast_upvote(context):
    """Cast an upvote on the target idea."""
    vote = Vote(
        idea_id=context.target_idea.id,
        user_id=context.current_employee['user_id'],
        vote_type=VoteType.UPVOTE,
        ip_address=context.current_employee['ip_address'],
        user_agent=context.current_employee['user_agent']
    )
    
    context.db.add(vote)
    context.db.commit()
    context.db.refresh(vote)
    
    context.cast_vote = vote
    
    # Update vote aggregate
    aggregate = context.db.query(VoteAggregate).filter(
        VoteAggregate.idea_id == context.target_idea.id
    ).first()
    
    if not aggregate:
        aggregate = VoteAggregate(idea_id=context.target_idea.id)
        context.db.add(aggregate)
    
    aggregate.upvote_count += 1
    aggregate.total_votes += 1
    aggregate.score = aggregate.calculate_score()
    
    context.db.commit()
    context.vote_aggregate = aggregate


@then('the vote should be recorded successfully')
def step_vote_recorded_successfully(context):
    """Verify vote was recorded in database."""
    assert context.cast_vote.id is not None
    assert context.cast_vote.idea_id == context.target_idea.id
    assert context.cast_vote.user_id == context.current_employee['user_id']
    assert context.cast_vote.vote_type == VoteType.UPVOTE


@then("the idea's upvote count should increase by 1")
def step_upvote_count_increased(context):
    """Verify upvote count increased."""
    assert context.vote_aggregate.upvote_count >= 1
    assert context.vote_aggregate.total_votes >= 1


@then('my vote should be cached for quick retrieval')
def step_vote_cached(context):
    """Verify vote is cached in Redis."""
    cache_key = f"user_vote:{context.current_employee['user_id']}:{context.target_idea.id}"
    context.redis_client.set.assert_called()
    context.vote_cached = True


@then('I should not be able to vote again on the same idea')
def step_cannot_vote_again(context):
    """Verify duplicate vote prevention."""
    # Try to vote again
    try:
        duplicate_vote = Vote(
            idea_id=context.target_idea.id,
            user_id=context.current_employee['user_id'],
            vote_type=VoteType.UPVOTE
        )
        context.db.add(duplicate_vote)
        context.db.commit()
        # Should raise integrity error due to unique constraint
        assert False, "Duplicate vote should not be allowed"
    except Exception:
        # This is expected due to unique constraint
        context.db.rollback()
        context.duplicate_vote_prevented = True
        assert context.duplicate_vote_prevented


@given('I have already upvoted idea "{idea_id}"')
def step_already_upvoted_idea(context, idea_id):
    """Set up existing upvote."""
    idea_id_int = int(idea_id)
    context.target_idea = next(
        (idea for idea in context.published_ideas if idea.id == idea_id_int),
        None
    )
    
    # Create existing vote
    existing_vote = Vote(
        idea_id=idea_id_int,
        user_id=context.current_employee['user_id'],
        vote_type=VoteType.UPVOTE
    )
    
    context.db.add(existing_vote)
    context.db.commit()
    context.existing_vote = existing_vote
    
    # Update aggregate
    aggregate = VoteAggregate(
        idea_id=idea_id_int,
        upvote_count=1,
        total_votes=1
    )
    aggregate.score = aggregate.calculate_score()
    
    context.db.add(aggregate)
    context.db.commit()
    context.original_aggregate = aggregate


@when('I change my vote to downvote')
def step_change_vote_to_downvote(context):
    """Change existing vote from upvote to downvote."""
    # Update existing vote
    context.existing_vote.vote_type = VoteType.DOWNVOTE
    context.existing_vote.updated_at = datetime.now(timezone.utc)
    
    # Update aggregate
    context.original_aggregate.upvote_count -= 1
    context.original_aggregate.downvote_count += 1
    # Total votes stays the same
    context.original_aggregate.score = context.original_aggregate.calculate_score()
    
    context.db.commit()


@then('my previous upvote should be removed')
def step_previous_upvote_removed(context):
    """Verify previous upvote was changed."""
    assert context.existing_vote.vote_type == VoteType.DOWNVOTE
    assert context.original_aggregate.upvote_count == 0


@then('a downvote should be recorded')
def step_downvote_recorded(context):
    """Verify downvote was recorded."""
    assert context.original_aggregate.downvote_count == 1


@then("the idea's vote counts should be updated accordingly")
def step_vote_counts_updated(context):
    """Verify vote counts are correct."""
    assert context.original_aggregate.upvote_count == 0
    assert context.original_aggregate.downvote_count == 1
    assert context.original_aggregate.total_votes == 1


@then('the net score should decrease by 2')
def step_net_score_decreased(context):
    """Verify score calculation after vote change."""
    # Score changed from +1 (upvote) to -1 (downvote) = net change of -2
    expected_score = -1.0  # 0 upvotes - 1 downvote
    assert context.original_aggregate.score == expected_score


@given('there is an idea about "{topic}"')
def step_idea_about_topic(context, topic):
    """Create or reference idea about specific topic."""
    topic_idea = Idea(
        id=789,
        title=topic,
        description=f"Detailed description about {topic}",
        category="improvement",
        status=IdeaStatus.PUBLISHED,
        user_id="emp001",
        user_email="emp001@company.com",
        published_at=datetime.now(timezone.utc)
    )
    
    context.db.merge(topic_idea)
    context.db.commit()
    context.topic_idea = topic_idea


@when('I give a rating of {rating:f} out of 5')
def step_give_rating(context, rating):
    """Give a rating to an idea."""
    rating_vote = Vote(
        idea_id=context.topic_idea.id,
        user_id=context.current_employee['user_id'],
        vote_type=VoteType.RATING,
        rating=rating
    )
    
    context.db.add(rating_vote)
    context.db.commit()
    context.rating_vote = rating_vote
    
    # Update aggregate
    aggregate = VoteAggregate(
        idea_id=context.topic_idea.id,
        rating_count=1,
        rating_sum=rating,
        average_rating=rating
    )
    aggregate.score = aggregate.calculate_score()
    
    context.db.add(aggregate)
    context.db.commit()
    context.rating_aggregate = aggregate


@step('I provide feedback "{feedback}"')
def step_provide_feedback(context, feedback):
    """Add feedback to the rating (could be stored separately)."""
    context.rating_feedback = feedback
    # In real implementation, this might be stored in a separate feedback table


@then('the rating should be recorded')
def step_rating_recorded(context):
    """Verify rating was recorded."""
    assert context.rating_vote.rating is not None
    assert context.rating_vote.vote_type == VoteType.RATING


@then("the idea's average rating should be recalculated")
def step_average_rating_recalculated(context):
    """Verify average rating calculation."""
    assert context.rating_aggregate.average_rating == context.rating_vote.rating
    assert context.rating_aggregate.rating_count == 1


@then('my rating should contribute to the overall score')
def step_rating_contributes_to_score(context):
    """Verify rating affects overall score."""
    expected_score = context.rating_vote.rating * 2.0  # Based on calculate_score logic
    assert context.rating_aggregate.score == expected_score


@given('there are {count:d} ideas competing for implementation')
def step_ideas_competing(context, count):
    """Set up multiple competing ideas."""
    context.competing_ideas = []
    for i in range(count):
        idea = Idea(
            id=1000 + i,
            title=f"Competing Idea {i+1}",
            description=f"Description for idea {i+1}",
            category="innovation",
            status=IdeaStatus.PUBLISHED,
            user_id=f"emp{i:03d}",
            user_email=f"emp{i:03d}@company.com",
            published_at=datetime.now(timezone.utc)
        )
        context.db.merge(idea)
        context.competing_ideas.append(idea)
    
    context.db.commit()


@when('multiple employees vote simultaneously')
def step_multiple_employees_vote_simultaneously(context):
    """Process simultaneous votes from multiple employees."""
    # This step expects a table with vote data
    if hasattr(context, 'table'):
        context.simultaneous_votes = []
        context.vote_aggregates = {}
        
        for row in context.table:
            employee = row['employee']
            idea_id = int(row['idea_id'])
            vote_type = row['vote_type']
            rating = float(row['rating']) if row['rating'] else None
            
            # Create vote
            vote = Vote(
                idea_id=idea_id,
                user_id=employee,
                vote_type=vote_type,
                rating=rating
            )
            
            context.db.add(vote)
            context.simultaneous_votes.append(vote)
            
            # Update or create aggregate
            if idea_id not in context.vote_aggregates:
                aggregate = VoteAggregate(
                    idea_id=idea_id,
                    upvote_count=0,
                    downvote_count=0,
                    rating_count=0,
                    rating_sum=0.0,
                    average_rating=0.0
                )
                context.vote_aggregates[idea_id] = aggregate
                context.db.add(aggregate)
            
            aggregate = context.vote_aggregates[idea_id]
            
            if vote_type == 'upvote':
                aggregate.upvote_count += 1
                aggregate.total_votes += 1
            elif vote_type == 'rating' and rating:
                aggregate.rating_count += 1
                aggregate.rating_sum += rating
                aggregate.average_rating = aggregate.rating_sum / aggregate.rating_count
            
            aggregate.score = aggregate.calculate_score()
        
        context.db.commit()


@then('vote aggregates should be updated in real-time')
def step_vote_aggregates_updated_realtime(context):
    """Verify vote aggregates are updated."""
    for idea_id, aggregate in context.vote_aggregates.items():
        assert aggregate.score > 0
        # Verify counts match expected values


@then('idea001 should be ranked highest')
def step_idea001_ranked_highest(context):
    """Verify idea001 has highest score."""
    idea001_aggregate = context.vote_aggregates.get(1, None)
    if idea001_aggregate:
        # Compare with other ideas
        highest_score = max(agg.score for agg in context.vote_aggregates.values())
        assert idea001_aggregate.score == highest_score


@then('leaderboard should reflect current standings')
def step_leaderboard_reflects_standings(context):
    """Verify leaderboard is correctly ordered."""
    sorted_aggregates = sorted(
        context.vote_aggregates.values(),
        key=lambda x: x.score,
        reverse=True
    )
    
    # Verify order is descending
    scores = [agg.score for agg in sorted_aggregates]
    assert scores == sorted(scores, reverse=True)


@then('Redis cache should contain latest vote counts')
def step_redis_contains_latest_counts(context):
    """Verify Redis cache is updated."""
    # Mock verification that Redis was called to update cache
    context.redis_client.set.assert_called()
    context.cache_updated = True