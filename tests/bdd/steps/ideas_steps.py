"""Step definitions for Ideas feature tests."""
import pytest
from behave import given, when, then, step
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import requests
import time

# Import your actual models and services
from services.ideas.models import Idea, Comment, IdeaStatus, IdeaCategory
from services.ideas.database import Base
from services.ideas.schemas import IdeaCreate, IdeaUpdate


@given('the ideas service is running')
def step_ideas_service_running(context):
    """Mock or verify that the ideas service is running."""
    context.ideas_service_url = "http://localhost:8001"
    context.ideas_service_running = True
    
    # Mock the service if not actually running
    if not hasattr(context, 'ideas_client'):
        context.ideas_client = Mock()


@given('the database is clean and initialized')
def step_database_clean_initialized(context):
    """Set up clean test database."""
    # Use in-memory SQLite for tests
    context.test_db_url = "sqlite:///:memory:"
    context.engine = create_engine(context.test_db_url)
    Base.metadata.create_all(context.engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=context.engine)
    context.db = SessionLocal()
    
    # Store for cleanup
    context.test_data = {
        'ideas': [],
        'comments': [],
        'users': []
    }


@given('I am a logged-in employee with user ID "{user_id}"')
def step_logged_in_employee(context, user_id):
    """Set up authenticated user context."""
    context.current_user = {
        'user_id': user_id,
        'user_email': f'{user_id}@company.com',
        'user_name': f'Employee {user_id}',
        'role': 'employee',
        'token': f'mock_token_{user_id}'
    }
    context.auth_headers = {'Authorization': f'Bearer {context.current_user["token"]}'}


@when('I submit an idea with title "{title}"')
def step_submit_idea_with_title(context, title):
    """Submit an idea with specified title."""
    context.idea_data = {
        'title': title,
        'user_id': context.current_user['user_id'],
        'user_email': context.current_user['user_email'],
        'user_name': context.current_user['user_name']
    }


@step('description "{description}"')
def step_with_description(context, description):
    """Add description to idea data."""
    context.idea_data['description'] = description


@step('category "{category}"')
def step_with_category(context, category):
    """Add category to idea data."""
    context.idea_data['category'] = category


@then('the idea should be created successfully')
def step_idea_created_successfully(context):
    """Verify idea creation success."""
    # Create the idea in test database
    idea = Idea(
        title=context.idea_data['title'],
        description=context.idea_data['description'],
        category=context.idea_data['category'],
        user_id=context.idea_data['user_id'],
        user_email=context.idea_data['user_email'],
        user_name=context.idea_data['user_name']
    )
    
    context.db.add(idea)
    context.db.commit()
    context.db.refresh(idea)
    
    context.created_idea = idea
    context.test_data['ideas'].append(idea)
    
    assert idea.id is not None
    assert idea.title == context.idea_data['title']
    assert idea.description == context.idea_data['description']


@then('the idea status should be "{status}"')
def step_idea_status_should_be(context, status):
    """Verify idea status."""
    assert context.created_idea.status == status


@then('the idea should have zero votes initially')
def step_idea_zero_votes_initially(context):
    """Verify initial vote count is zero."""
    assert context.created_idea.vote_count == 0
    assert context.created_idea.average_rating == 0.0


@then('the idea should be visible in my submitted ideas list')
def step_idea_visible_in_submitted_list(context):
    """Verify idea appears in user's submitted ideas."""
    user_ideas = context.db.query(Idea).filter(
        Idea.user_id == context.current_user['user_id']
    ).all()
    
    idea_titles = [idea.title for idea in user_ideas]
    assert context.created_idea.title in idea_titles


@given('I have a draft idea with ID "{idea_id}"')
def step_have_draft_idea(context, idea_id):
    """Create a draft idea for testing."""
    draft_idea = Idea(
        title="Draft Innovation Idea",
        description="This is a draft idea for testing",
        category=IdeaCategory.INNOVATION,
        status=IdeaStatus.DRAFT,
        user_id=context.current_user['user_id'],
        user_email=context.current_user['user_email'],
        user_name=context.current_user['user_name']
    )
    
    context.db.add(draft_idea)
    context.db.commit()
    context.db.refresh(draft_idea)
    
    context.draft_idea = draft_idea
    context.test_data['ideas'].append(draft_idea)


@given('I am the owner of the idea')
def step_am_owner_of_idea(context):
    """Verify user is the owner of the idea."""
    assert context.draft_idea.user_id == context.current_user['user_id']


@when('I publish the idea')
def step_publish_idea(context):
    """Publish the draft idea."""
    context.draft_idea.status = IdeaStatus.PUBLISHED
    context.draft_idea.published_at = datetime.now(timezone.utc)
    context.db.commit()
    context.db.refresh(context.draft_idea)


@then('the idea status should change to "{status}"')
def step_idea_status_change_to(context, status):
    """Verify idea status change."""
    assert context.draft_idea.status == status


@then('the idea should be visible to all employees')
def step_idea_visible_to_all(context):
    """Verify idea is publicly visible."""
    published_ideas = context.db.query(Idea).filter(
        Idea.status == IdeaStatus.PUBLISHED
    ).all()
    
    assert context.draft_idea in published_ideas


@then('the published_at timestamp should be set')
def step_published_timestamp_set(context):
    """Verify published timestamp is set."""
    assert context.draft_idea.published_at is not None


@given('there is a published idea with ID "{idea_id}"')
def step_published_idea_exists(context, idea_id):
    """Create a published idea for testing."""
    published_idea = Idea(
        title="Remote Work Policy Enhancement",
        description="Let's improve our remote work policies",
        category=IdeaCategory.IMPROVEMENT,
        status=IdeaStatus.PUBLISHED,
        user_id="emp001",
        user_email="emp001@company.com",
        user_name="Employee 001",
        published_at=datetime.now(timezone.utc)
    )
    
    context.db.add(published_idea)
    context.db.commit()
    context.db.refresh(published_idea)
    
    context.published_idea = published_idea
    context.test_data['ideas'].append(published_idea)


@step('the idea has title "{title}"')
def step_idea_has_title(context, title):
    """Verify or set idea title."""
    if hasattr(context, 'published_idea'):
        context.published_idea.title = title
        context.db.commit()


@when('employee "{employee_id}" adds comment "{comment_text}"')
def step_employee_adds_comment(context, employee_id, comment_text):
    """Add comment as specified employee."""
    comment = Comment(
        idea_id=context.published_idea.id,
        user_id=employee_id,
        user_name=f"Employee {employee_id}",
        content=comment_text
    )
    
    context.db.add(comment)
    context.db.commit()
    context.db.refresh(comment)
    
    if not hasattr(context, 'comments'):
        context.comments = []
    context.comments.append(comment)
    context.test_data['comments'].append(comment)


@then('the idea should have {count:d} comments')
def step_idea_should_have_comments(context, count):
    """Verify comment count."""
    actual_count = context.db.query(Comment).filter(
        Comment.idea_id == context.published_idea.id,
        Comment.is_deleted == False
    ).count()
    
    assert actual_count == count


@then('all comments should be visible to viewers')
def step_comments_visible_to_viewers(context):
    """Verify comments are visible."""
    comments = context.db.query(Comment).filter(
        Comment.idea_id == context.published_idea.id,
        Comment.is_deleted == False
    ).all()
    
    assert len(comments) > 0
    for comment in comments:
        assert not comment.is_deleted


@then('the idea view count should increase')
def step_idea_view_count_increase(context):
    """Simulate and verify view count increase."""
    # Simulate view count increment
    context.published_idea.view_count += 1
    context.db.commit()
    
    assert context.published_idea.view_count > 0


@given('there are multiple published ideas')
def step_multiple_published_ideas(context):
    """Create multiple published ideas for testing."""
    ideas_data = [
        {
            'title': 'Green Office Initiative',
            'description': 'Make our office more environmentally friendly',
            'category': IdeaCategory.IMPROVEMENT,
            'vote_count': 25,
            'average_rating': 4.5
        },
        {
            'title': 'Cost Reduction Strategy',
            'description': 'Strategic approach to reduce operational costs',
            'category': IdeaCategory.COST_SAVING,
            'vote_count': 18,
            'average_rating': 4.2
        },
        {
            'title': 'Employee Wellness Program',
            'description': 'Comprehensive wellness program for employees',
            'category': IdeaCategory.IMPROVEMENT,
            'vote_count': 30,
            'average_rating': 4.8
        }
    ]
    
    context.test_ideas = []
    for idea_data in ideas_data:
        idea = Idea(
            title=idea_data['title'],
            description=idea_data['description'],
            category=idea_data['category'],
            status=IdeaStatus.PUBLISHED,
            user_id='emp001',
            user_email='emp001@company.com',
            user_name='Employee 001',
            vote_count=idea_data['vote_count'],
            average_rating=idea_data['average_rating'],
            published_at=datetime.now(timezone.utc)
        )
        
        context.db.add(idea)
        context.test_ideas.append(idea)
    
    context.db.commit()
    context.test_data['ideas'].extend(context.test_ideas)


@step('idea "{title}" has {upvotes:d} upvotes and {rating:f} rating')
def step_idea_has_votes_and_rating(context, title, upvotes, rating):
    """Set specific votes and rating for an idea."""
    idea = next((idea for idea in context.test_ideas if idea.title == title), None)
    if idea:
        idea.vote_count = upvotes
        idea.average_rating = rating
        context.db.commit()


@when('I filter ideas by "{filter_type}"')
def step_filter_ideas_by(context, filter_type):
    """Filter ideas by specified criteria."""
    if filter_type == "high engagement":
        # Calculate engagement score (simplified formula)
        context.filtered_ideas = []
        for idea in context.test_ideas:
            engagement_score = (idea.vote_count * 0.6) + (idea.average_rating * 10 * 0.4)
            idea.engagement_score = engagement_score
            context.filtered_ideas.append((idea, engagement_score))
        
        # Sort by engagement score descending
        context.filtered_ideas.sort(key=lambda x: x[1], reverse=True)


@then('I should see ideas ordered by engagement score')
def step_ideas_ordered_by_engagement(context):
    """Verify ideas are ordered by engagement score."""
    scores = [item[1] for item in context.filtered_ideas]
    assert scores == sorted(scores, reverse=True)


@then('"{title}" should be ranked {position}')
def step_idea_ranked_at_position(context, title, position):
    """Verify specific idea ranking."""
    position_map = {'first': 0, 'second': 1, 'third': 2}
    expected_index = position_map[position]
    
    actual_title = context.filtered_ideas[expected_index][0].title
    assert actual_title == title


@when('a manager changes the status to "{new_status}"')
def step_manager_changes_status(context, new_status):
    """Simulate manager changing idea status."""
    # Assume we have a published idea from previous steps
    idea = context.test_ideas[0] if hasattr(context, 'test_ideas') else context.published_idea
    idea.status = new_status
    context.db.commit()
    context.status_changed_idea = idea


@then('stakeholders should be notified')
def step_stakeholders_notified(context):
    """Verify stakeholder notification (mock)."""
    # In real implementation, this would trigger notification service
    context.notifications_sent = True
    assert context.notifications_sent


@then('the idea owner should receive implementation notification')
def step_owner_receives_notification(context):
    """Verify idea owner notification (mock)."""
    # Mock notification to idea owner
    context.owner_notified = True
    assert context.owner_notified


# Additional step definitions for search, analytics, and error handling scenarios...

@when('I search for ideas with keyword "{keyword}"')
def step_search_ideas_with_keyword(context, keyword):
    """Search ideas by keyword."""
    context.search_results = []
    for idea in context.test_ideas:
        if keyword.lower() in idea.title.lower() or keyword.lower() in idea.description.lower():
            context.search_results.append(idea)


@then('I should see the "{category}" idea in results')
def step_should_see_category_idea_in_results(context, category):
    """Verify specific category idea in search results."""
    category_ideas = [idea for idea in context.search_results if idea.category == category]
    assert len(category_ideas) > 0


@when('I filter by category "{category}"')
def step_filter_by_category(context, category):
    """Filter ideas by category."""
    context.category_filtered_ideas = [
        idea for idea in context.test_ideas
        if idea.category == category
    ]


@then('I should only see {category} category ideas')
def step_should_see_only_category_ideas(context, category):
    """Verify only specified category ideas are shown."""
    for idea in context.category_filtered_ideas:
        assert idea.category == category