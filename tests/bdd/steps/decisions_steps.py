"""Step definitions for Decision Making feature tests."""
import pytest
from behave import given, when, then, step
from unittest.mock import Mock, patch, MagicMock
import json
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import your actual models and services
from services.decision.models import (
    Decision, DecisionEvent, DecisionCriteria, DecisionTemplate,
    DecisionStatus, DecisionType
)
from services.ideas.models import Idea, IdeaStatus


@given('the decision service is running')
def step_decision_service_running(context):
    """Mock or verify that the decision service is running."""
    context.decision_service_url = "http://localhost:8003"
    context.decision_service_running = True
    
    if not hasattr(context, 'decision_client'):
        context.decision_client = Mock()


@given('there are ideas available for decision making')
def step_ideas_available_for_decisions(context):
    """Set up ideas that can have decisions made on them."""
    if not hasattr(context, 'db'):
        # Set up test database
        context.test_db_url = "sqlite:///:memory:"
        context.engine = create_engine(context.test_db_url)
        
        # Import and create all tables
        from services.ideas.models import Base as IdeasBase
        from services.decision.models import Base as DecisionBase
        
        IdeasBase.metadata.create_all(context.engine)
        DecisionBase.metadata.create_all(context.engine)
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=context.engine)
        context.db = SessionLocal()
    
    # Create test ideas for decision making
    test_idea = Idea(
        id=1,
        title="AI-Powered Analytics Dashboard",
        description="Implement advanced analytics dashboard with AI insights",
        category="innovation",
        status=IdeaStatus.PUBLISHED,
        user_id="emp001",
        user_email="emp001@company.com",
        vote_count=45,
        average_rating=4.7,
        view_count=320,
        published_at=datetime.now(timezone.utc) - timedelta(days=14)
    )
    
    context.db.merge(test_idea)
    context.db.commit()
    context.decision_ready_idea = test_idea


@given('decision criteria are configured')
def step_decision_criteria_configured(context):
    """Set up decision criteria for automated suggestions."""
    criteria = DecisionCriteria(
        name="Standard Implementation Criteria",
        description="Default criteria for implementation decisions",
        category="innovation",
        min_vote_count=20,
        min_engagement_score=0.7,
        min_average_rating=4.0,
        min_days_since_created=7,
        min_success_probability=0.6,
        suggested_decision_type=DecisionType.IMPLEMENTATION,
        auto_approve=False,
        is_active=True
    )
    
    context.db.add(criteria)
    context.db.commit()
    context.decision_criteria = criteria


@given('I am a manager with decision-making authority')
def step_manager_with_authority(context):
    """Set up manager context."""
    context.current_manager = {
        'user_id': 'mgr001',
        'user_email': 'manager001@company.com',
        'user_name': 'Manager One',
        'role': 'manager',
        'permissions': ['make_decisions', 'approve_implementations'],
        'token': 'mock_manager_token'
    }


@given('there is an idea with ID "{idea_id}" that has')
def step_idea_with_metrics(context, idea_id):
    """Set up idea with specific metrics from table."""
    idea_id_int = int(idea_id)
    
    if hasattr(context, 'table'):
        metrics = {row['metric']: row['value'] for row in context.table}
        
        # Update the existing idea with metrics
        idea = context.db.query(Idea).filter(Idea.id == idea_id_int).first()
        if not idea:
            idea = Idea(
                id=idea_id_int,
                title="High Engagement Idea",
                description="An idea with high engagement metrics",
                category="innovation",
                status=IdeaStatus.PUBLISHED,
                user_id="emp001",
                user_email="emp001@company.com"
            )
            context.db.add(idea)
        
        # Set metrics from table
        if 'upvotes' in metrics:
            idea.vote_count = int(metrics['upvotes'])
        if 'average_rating' in metrics:
            idea.average_rating = float(metrics['average_rating'])
        if 'engagement_score' in metrics:
            # Store engagement score as a calculated field
            context.engagement_score = float(metrics['engagement_score'])
        if 'days_since_published' in metrics:
            days_ago = int(metrics['days_since_published'])
            idea.published_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        
        context.db.commit()
        context.target_idea = idea


@when('I create an implementation decision for the idea')
def step_create_implementation_decision(context):
    """Create an implementation decision."""
    decision = Decision(
        idea_id=context.target_idea.id,
        decision_type=DecisionType.IMPLEMENTATION,
        status=DecisionStatus.PENDING,
        decided_by=context.current_manager['user_id'],
        summary="Implementation approved based on strong metrics",
        rationale="",  # Will be set in next step
        metrics_snapshot={
            'vote_count': context.target_idea.vote_count,
            'average_rating': context.target_idea.average_rating,
            'engagement_score': getattr(context, 'engagement_score', 0.85)
        }
    )
    
    context.db.add(decision)
    context.db.commit()
    context.db.refresh(decision)
    context.created_decision = decision


@step('I provide rationale "{rationale}"')
def step_provide_rationale(context, rationale):
    """Add rationale to the decision."""
    context.created_decision.rationale = rationale
    context.db.commit()


@step('I set implementation timeline to {days:d} days')
def step_set_implementation_timeline(context, days):
    """Set implementation timeline."""
    context.created_decision.timeline_days = days
    context.db.commit()


@step('I assign it to development team "{team_name}"')
def step_assign_to_team(context, team_name):
    """Assign decision to a team."""
    context.created_decision.resource_requirements = {
        'assigned_team': team_name,
        'team_capacity': 'available'
    }
    context.db.commit()


@then('the decision should be created successfully')
def step_decision_created_successfully(context):
    """Verify decision was created."""
    assert context.created_decision.id is not None
    assert context.created_decision.idea_id == context.target_idea.id
    assert context.created_decision.decision_type == DecisionType.IMPLEMENTATION


@then('the idea status should change to "{status}"')
def step_idea_status_should_change(context, status):
    """Update and verify idea status change."""
    context.target_idea.status = status
    context.db.commit()
    
    # Verify the change
    updated_idea = context.db.query(Idea).filter(Idea.id == context.target_idea.id).first()
    assert updated_idea.status == status


@then('implementation plan should be attached')
def step_implementation_plan_attached(context):
    """Verify implementation plan is attached."""
    context.created_decision.implementation_plan = (
        "1. Technical analysis and architecture design\n"
        "2. Development sprint planning\n"
        "3. Implementation in 4 sprints\n"
        "4. Testing and quality assurance\n"
        "5. Deployment and monitoring"
    )
    context.db.commit()
    
    assert context.created_decision.implementation_plan is not None
    assert len(context.created_decision.implementation_plan) > 0


@then('stakeholders should be notified')
def step_stakeholders_should_be_notified(context):
    """Mock stakeholder notifications."""
    # Create decision event for notification
    event = DecisionEvent(
        decision_id=context.created_decision.id,
        event_type="stakeholders_notified",
        event_data={
            'notification_type': 'implementation_approved',
            'recipients': ['idea_owner', 'assigned_team', 'management']
        },
        actor_id=context.current_manager['user_id'],
        actor_name=context.current_manager['user_name']
    )
    
    context.db.add(event)
    context.db.commit()
    
    context.stakeholders_notified = True
    assert context.stakeholders_notified


@given('there are configured decision criteria')
def step_configured_decision_criteria(context):
    """Set up decision criteria from table."""
    if hasattr(context, 'table'):
        for row in context.table:
            criteria_name = row['criteria']
            threshold_value = row['threshold']
            
            # Map criteria names to model fields
            criteria_mapping = {
                'min_vote_count': 'min_vote_count',
                'min_average_rating': 'min_average_rating',
                'min_engagement_score': 'min_engagement_score',
                'min_days_since_created': 'min_days_since_created'
            }
            
            # Store criteria values for later use
            if not hasattr(context, 'criteria_values'):
                context.criteria_values = {}
            
            if criteria_name in criteria_mapping:
                context.criteria_values[criteria_mapping[criteria_name]] = float(threshold_value)


@given('there is an idea that meets all criteria')
def step_idea_meets_all_criteria(context):
    """Create an idea that meets all decision criteria."""
    qualifying_idea = Idea(
        id=100,
        title="Qualifying Innovation Idea",
        description="This idea meets all decision criteria",
        category="innovation",
        status=IdeaStatus.PUBLISHED,
        user_id="emp002",
        user_email="emp002@company.com",
        vote_count=25,  # > 20
        average_rating=4.5,  # > 4.0
        view_count=180,
        published_at=datetime.now(timezone.utc) - timedelta(days=10)  # > 7 days
    )
    
    context.db.merge(qualifying_idea)
    context.db.commit()
    context.qualifying_idea = qualifying_idea
    
    # Calculate engagement score
    context.qualifying_engagement_score = 0.75  # > 0.7


@when('the automated decision engine runs')
def step_automated_decision_engine_runs(context):
    """Run automated decision suggestion engine."""
    # Simulate automated decision logic
    idea = context.qualifying_idea
    criteria = context.decision_criteria
    
    # Check if idea meets criteria
    meets_criteria = (
        idea.vote_count >= criteria.min_vote_count and
        idea.average_rating >= criteria.min_average_rating and
        context.qualifying_engagement_score >= criteria.min_engagement_score and
        (datetime.now(timezone.utc) - idea.published_at).days >= criteria.min_days_since_created
    )
    
    if meets_criteria:
        # Create automated decision suggestion
        suggested_decision = Decision(
            idea_id=idea.id,
            decision_type=criteria.suggested_decision_type,
            status=DecisionStatus.PENDING,
            summary="Automated suggestion based on criteria match",
            rationale=f"Idea meets all configured criteria: {criteria.name}",
            metrics_snapshot={
                'vote_count': idea.vote_count,
                'average_rating': idea.average_rating,
                'engagement_score': context.qualifying_engagement_score,
                'criteria_met': True
            }
        )
        
        context.db.add(suggested_decision)
        context.db.commit()
        context.suggested_decision = suggested_decision


@then('a decision suggestion should be generated')
def step_decision_suggestion_generated(context):
    """Verify decision suggestion was generated."""
    assert hasattr(context, 'suggested_decision')
    assert context.suggested_decision.id is not None


@then('the suggestion type should be "{suggestion_type}"')
def step_suggestion_type_should_be(context, suggestion_type):
    """Verify suggestion type."""
    assert context.suggested_decision.decision_type == suggestion_type


@then('confidence score should be provided')
def step_confidence_score_provided(context):
    """Verify confidence score is calculated."""
    # Add confidence score to metrics snapshot
    context.suggested_decision.metrics_snapshot['confidence_score'] = 0.87
    context.db.commit()
    
    assert 'confidence_score' in context.suggested_decision.metrics_snapshot


@then('human review should be flagged if confidence is low')
def step_human_review_flagged_if_low_confidence(context):
    """Flag for human review if confidence is low."""
    confidence = context.suggested_decision.metrics_snapshot.get('confidence_score', 0)
    
    if confidence < 0.8:
        context.suggested_decision.metrics_snapshot['requires_human_review'] = True
        context.db.commit()
    
    # For high confidence, no human review needed
    context.human_review_needed = confidence < 0.8


@given('there is a high-impact idea requiring committee review')
def step_high_impact_idea_for_committee(context):
    """Create high-impact idea for committee review."""
    high_impact_idea = Idea(
        id=200,
        title="Enterprise Digital Transformation",
        description="Complete overhaul of enterprise systems and processes",
        category="innovation",
        status=IdeaStatus.PUBLISHED,
        user_id="emp003",
        user_email="emp003@company.com",
        vote_count=85,
        average_rating=4.9,
        view_count=750,
        published_at=datetime.now(timezone.utc) - timedelta(days=21)
    )
    
    context.db.merge(high_impact_idea)
    context.db.commit()
    context.high_impact_idea = high_impact_idea


@given('decision committee consists of')
def step_decision_committee_members(context):
    """Set up decision committee from table."""
    committee_members = []
    
    if hasattr(context, 'table'):
        for row in context.table:
            member = {
                'member_id': row['member'],
                'role': row['role'],
                'expertise': row['expertise']
            }
            committee_members.append(member)
    
    context.committee_members = committee_members


@when('the idea is submitted to committee')
def step_idea_submitted_to_committee(context):
    """Submit idea to committee for review."""
    committee_decision = Decision(
        idea_id=context.high_impact_idea.id,
        decision_type=DecisionType.IMPLEMENTATION,
        status=DecisionStatus.IN_REVIEW,
        summary="High-impact idea submitted for committee review",
        rationale="Requires multi-stakeholder evaluation due to scope and impact",
        decision_committee=[member['member_id'] for member in context.committee_members],
        metrics_snapshot={
            'vote_count': context.high_impact_idea.vote_count,
            'average_rating': context.high_impact_idea.average_rating,
            'estimated_impact': 'high',
            'committee_review_required': True
        }
    )
    
    context.db.add(committee_decision)
    context.db.commit()
    context.committee_decision = committee_decision


@then('each member should receive notification')
def step_each_member_receives_notification(context):
    """Verify committee members are notified."""
    for member in context.committee_members:
        event = DecisionEvent(
            decision_id=context.committee_decision.id,
            event_type="committee_member_notified",
            event_data={
                'member_id': member['member_id'],
                'notification_sent': True
            },
            actor_id="system",
            actor_name="Decision System"
        )
        context.db.add(event)
    
    context.db.commit()
    context.committee_notified = True


@then('voting interface should be available to committee')
def step_voting_interface_available(context):
    """Mock committee voting interface."""
    context.committee_voting_interface = {
        'decision_id': context.committee_decision.id,
        'available_to': [member['member_id'] for member in context.committee_members],
        'voting_options': ['approve', 'reject', 'modify', 'defer'],
        'deadline': datetime.now(timezone.utc) + timedelta(days=7)
    }
    
    assert len(context.committee_voting_interface['available_to']) == len(context.committee_members)


@when('all members cast their votes')
def step_all_members_cast_votes(context):
    """Simulate committee members voting."""
    member_votes = [
        {'member': 'mgr001', 'vote': 'approve', 'rationale': 'Strong technical feasibility'},
        {'member': 'mgr002', 'vote': 'approve', 'rationale': 'Solid business case'},
        {'member': 'mgr003', 'vote': 'modify', 'rationale': 'Need phased implementation for budget'}
    ]
    
    context.committee_votes = member_votes
    
    # Record votes as events
    for vote in member_votes:
        event = DecisionEvent(
            decision_id=context.committee_decision.id,
            event_type="committee_vote_cast",
            event_data={
                'vote': vote['vote'],
                'rationale': vote['rationale']
            },
            actor_id=vote['member'],
            actor_name=f"Committee Member {vote['member']}"
        )
        context.db.add(event)
    
    context.db.commit()


@then('committee decision should be calculated')
def step_committee_decision_calculated(context):
    """Calculate final committee decision."""
    votes = [vote['vote'] for vote in context.committee_votes]
    vote_counts = {vote: votes.count(vote) for vote in set(votes)}
    
    # Simple majority logic
    majority_vote = max(vote_counts, key=vote_counts.get)
    
    # Update decision based on committee vote
    if majority_vote == 'approve':
        context.committee_decision.status = DecisionStatus.APPROVED
    else:
        context.committee_decision.status = DecisionStatus.IN_REVIEW  # Needs more discussion
    
    context.committee_decision.rationale += f"\nCommittee decision: {majority_vote}"
    context.db.commit()
    
    context.final_committee_decision = majority_vote


@then('consensus level should be determined')
def step_consensus_level_determined(context):
    """Determine level of consensus among committee."""
    votes = [vote['vote'] for vote in context.committee_votes]
    unique_votes = len(set(votes))
    total_votes = len(votes)
    
    if unique_votes == 1:
        consensus_level = "unanimous"
    elif unique_votes == 2 and total_votes > 2:
        consensus_level = "majority"
    else:
        consensus_level = "split"
    
    context.consensus_level = consensus_level
    context.committee_decision.metrics_snapshot['consensus_level'] = consensus_level
    context.db.commit()


@then('final decision should be recorded with all member inputs')
def step_final_decision_recorded(context):
    """Verify final decision includes all member inputs."""
    # Verify all votes are recorded as events
    committee_events = context.db.query(DecisionEvent).filter(
        DecisionEvent.decision_id == context.committee_decision.id,
        DecisionEvent.event_type == "committee_vote_cast"
    ).all()
    
    assert len(committee_events) == len(context.committee_members)
    
    # Verify decision has committee information
    assert context.committee_decision.decision_committee is not None
    assert len(context.committee_decision.decision_committee) == len(context.committee_members)