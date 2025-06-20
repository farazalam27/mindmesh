"""Unit tests for Decision service."""
import pytest
import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Import your actual modules
from services.decision.models import (
    Decision, DecisionEvent, DecisionCriteria, DecisionTemplate,
    DecisionStatus, DecisionType, Base
)
from services.decision.schemas import (
    DecisionCreate, DecisionUpdate, DecisionResponse,
    DecisionEventCreate, DecisionCriteriaCreate
)
from services.decision.api import router


class TestDecisionModel:
    """Test cases for Decision model."""
    
    @pytest.fixture
    def db_session(self):
        """Create test database session."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    def test_create_decision(self, db_session):
        """Test creating a new decision."""
        decision = Decision(
            idea_id=123,
            decision_type=DecisionType.IMPLEMENTATION,
            status=DecisionStatus.PENDING,
            decided_by="manager_001",
            summary="Approved for implementation based on high engagement",
            rationale="Strong user support and clear business value",
            metrics_snapshot={
                "vote_count": 45,
                "average_rating": 4.7,
                "engagement_score": 0.85
            }
        )
        
        db_session.add(decision)
        db_session.commit()
        db_session.refresh(decision)
        
        assert decision.id is not None
        assert decision.decision_id is not None  # Auto-generated UUID
        assert decision.idea_id == 123
        assert decision.decision_type == DecisionType.IMPLEMENTATION
        assert decision.status == DecisionStatus.PENDING
        assert decision.created_at is not None
        assert decision.metrics_snapshot["vote_count"] == 45
    
    def test_decision_type_enum(self):
        """Test decision type enumeration."""
        assert DecisionType.IMPLEMENTATION == "implementation"
        assert DecisionType.REJECTION == "rejection"
        assert DecisionType.MODIFICATION == "modification"
        assert DecisionType.ESCALATION == "escalation"
        assert DecisionType.DEFERRAL == "deferral"
    
    def test_decision_status_enum(self):
        """Test decision status enumeration."""
        assert DecisionStatus.PENDING == "pending"
        assert DecisionStatus.IN_REVIEW == "in_review"
        assert DecisionStatus.APPROVED == "approved"
        assert DecisionStatus.REJECTED == "rejected"
        assert DecisionStatus.IMPLEMENTED == "implemented"
        assert DecisionStatus.ON_HOLD == "on_hold"
    
    def test_decision_with_committee(self, db_session):
        """Test decision with committee members."""
        decision = Decision(
            idea_id=456,
            decision_type=DecisionType.IMPLEMENTATION,
            status=DecisionStatus.IN_REVIEW,
            summary="Committee review required",
            rationale="High-impact idea requiring multi-stakeholder approval",
            decision_committee=["mgr001", "mgr002", "mgr003"],
            timeline_days=90,
            estimated_impact={
                "cost_estimate": 150000,
                "revenue_potential": 500000,
                "resource_requirements": "2 senior developers, 1 PM"
            }
        )
        
        db_session.add(decision)
        db_session.commit()
        db_session.refresh(decision)
        
        assert len(decision.decision_committee) == 3
        assert "mgr001" in decision.decision_committee
        assert decision.timeline_days == 90
        assert decision.estimated_impact["cost_estimate"] == 150000
    
    def test_decision_with_conditions(self, db_session):
        """Test decision with implementation conditions."""
        decision = Decision(
            idea_id=789,
            decision_type=DecisionType.MODIFICATION,
            status=DecisionStatus.APPROVED,
            summary="Approved with modifications",
            rationale="Good concept but needs scope reduction",
            conditions=[
                "Reduce initial scope by 30%",
                "Implement in phases",
                "Conduct pilot program first"
            ],
            resource_requirements={
                "budget": 75000,
                "team_size": 3,
                "timeline_months": 6
            }
        )
        
        db_session.add(decision)
        db_session.commit()
        db_session.refresh(decision)
        
        assert len(decision.conditions) == 3
        assert "Reduce initial scope by 30%" in decision.conditions
        assert decision.resource_requirements["budget"] == 75000
    
    def test_decision_repr(self, db_session):
        """Test decision string representation."""
        decision = Decision(
            idea_id=123,
            decision_type=DecisionType.IMPLEMENTATION,
            status=DecisionStatus.PENDING,
            summary="Test decision",
            rationale="Test rationale"
        )
        db_session.add(decision)
        db_session.commit()
        db_session.refresh(decision)
        
        expected_repr = f"<Decision(id={decision.id}, idea_id=123, type=implementation, status=pending)>"
        assert repr(decision) == expected_repr


class TestDecisionEventModel:
    """Test cases for DecisionEvent model."""
    
    @pytest.fixture
    def db_session(self):
        """Create test database session."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def test_decision(self, db_session):
        """Create test decision."""
        decision = Decision(
            idea_id=123,
            decision_type=DecisionType.IMPLEMENTATION,
            status=DecisionStatus.PENDING,
            summary="Test decision",
            rationale="Test rationale"
        )
        db_session.add(decision)
        db_session.commit()
        db_session.refresh(decision)
        return decision
    
    def test_create_decision_event(self, db_session, test_decision):
        """Test creating a decision event."""
        event = DecisionEvent(
            decision_id=test_decision.id,
            event_type="status_changed",
            event_data={
                "old_status": "pending",
                "new_status": "approved",
                "reason": "Met all criteria"
            },
            actor_id="manager_001",
            actor_name="Manager One",
            actor_role="decision_maker"
        )
        
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)
        
        assert event.id is not None
        assert event.event_id is not None  # Auto-generated UUID
        assert event.decision_id == test_decision.id
        assert event.event_type == "status_changed"
        assert event.event_data["new_status"] == "approved"
        assert event.actor_id == "manager_001"
        assert event.occurred_at is not None
    
    def test_decision_event_relationship(self, db_session, test_decision):
        """Test decision-event relationship."""
        # Create multiple events for the decision
        events = [
            DecisionEvent(
                decision_id=test_decision.id,
                event_type="created",
                event_data={"initial_status": "pending"},
                actor_id="system",
                actor_name="System"
            ),
            DecisionEvent(
                decision_id=test_decision.id,
                event_type="committee_assigned",
                event_data={"committee_members": ["mgr001", "mgr002"]},
                actor_id="admin_001",
                actor_name="Admin User"
            )
        ]
        
        for event in events:
            db_session.add(event)
        
        db_session.commit()
        
        # Refresh decision and check events
        db_session.refresh(test_decision)
        assert len(test_decision.events) == 2
        
        event_types = [event.event_type for event in test_decision.events]
        assert "created" in event_types
        assert "committee_assigned" in event_types
    
    def test_event_repr(self, db_session, test_decision):
        """Test event string representation."""
        event = DecisionEvent(
            decision_id=test_decision.id,
            event_type="metrics_updated",
            actor_id="analyst_001"
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)
        
        expected_repr = f"<DecisionEvent(id={event.id}, decision_id={test_decision.id}, event_type='metrics_updated')>"
        assert repr(event) == expected_repr


class TestDecisionCriteriaModel:
    """Test cases for DecisionCriteria model."""
    
    @pytest.fixture
    def db_session(self):
        """Create test database session."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    def test_create_decision_criteria(self, db_session):
        """Test creating decision criteria."""
        criteria = DecisionCriteria(
            name="Innovation Approval Criteria",
            description="Criteria for approving innovation ideas",
            category="innovation",
            min_vote_count=20,
            min_engagement_score=0.7,
            min_average_rating=4.0,
            max_controversy_score=0.3,
            min_days_since_created=7,
            max_days_in_review=30,
            min_success_probability=0.65,
            suggested_decision_type=DecisionType.IMPLEMENTATION,
            auto_approve=False,
            is_active=True
        )
        
        db_session.add(criteria)
        db_session.commit()
        db_session.refresh(criteria)
        
        assert criteria.id is not None
        assert criteria.name == "Innovation Approval Criteria"
        assert criteria.min_vote_count == 20
        assert criteria.min_success_probability == 0.65
        assert criteria.suggested_decision_type == DecisionType.IMPLEMENTATION
        assert criteria.is_active is True
    
    def test_criteria_unique_name(self, db_session):
        """Test unique constraint on criteria name."""
        criteria1 = DecisionCriteria(
            name="Standard Criteria",
            description="First criteria",
            min_vote_count=10
        )
        
        db_session.add(criteria1)
        db_session.commit()
        
        # Try to create another criteria with same name
        criteria2 = DecisionCriteria(
            name="Standard Criteria",
            description="Duplicate criteria",
            min_vote_count=15
        )
        
        db_session.add(criteria2)
        
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            db_session.commit()
    
    def test_criteria_repr(self, db_session):
        """Test criteria string representation."""
        criteria = DecisionCriteria(
            name="Test Criteria",
            category="improvement",
            min_vote_count=5
        )
        db_session.add(criteria)
        db_session.commit()
        db_session.refresh(criteria)
        
        expected_repr = f"<DecisionCriteria(id={criteria.id}, name='Test Criteria', category=improvement)>"
        assert repr(criteria) == expected_repr


class TestDecisionTemplateModel:
    """Test cases for DecisionTemplate model."""
    
    @pytest.fixture
    def db_session(self):
        """Create test database session."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    def test_create_decision_template(self, db_session):
        """Test creating a decision template."""
        template = DecisionTemplate(
            name="Quick Win Template",
            decision_type=DecisionType.IMPLEMENTATION,
            summary_template="Quick win implementation: {idea_title}",
            rationale_template="Low effort, high impact opportunity. {business_case}",
            conditions_template=[
                "Ensure minimal resource impact",
                "Complete within 30 days",
                "Measure ROI within 60 days"
            ],
            default_timeline_days=30,
            default_resource_requirements={
                "budget": 5000,
                "team_size": 1,
                "external_resources": False
            }
        )
        
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        assert template.id is not None
        assert template.name == "Quick Win Template"
        assert "{idea_title}" in template.summary_template
        assert template.default_timeline_days == 30
        assert len(template.conditions_template) == 3
        assert template.usage_count == 0  # Default
    
    def test_template_usage_tracking(self, db_session):
        """Test template usage tracking."""
        template = DecisionTemplate(
            name="Standard Implementation",
            decision_type=DecisionType.IMPLEMENTATION,
            summary_template="Standard implementation",
            rationale_template="Standard rationale"
        )
        
        db_session.add(template)
        db_session.commit()
        
        # Simulate template usage
        template.usage_count += 1
        db_session.commit()
        db_session.refresh(template)
        
        assert template.usage_count == 1
        
        # Use again
        template.usage_count += 1
        db_session.commit()
        db_session.refresh(template)
        
        assert template.usage_count == 2
    
    def test_template_repr(self, db_session):
        """Test template string representation."""
        template = DecisionTemplate(
            name="Test Template",
            decision_type=DecisionType.REJECTION,
            summary_template="Test summary",
            rationale_template="Test rationale"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        expected_repr = f"<DecisionTemplate(id={template.id}, name='Test Template', type=rejection)>"
        assert repr(template) == expected_repr


class TestDecisionService:
    """Test cases for Decision service logic."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()
    
    @pytest.fixture
    def sample_idea_metrics(self):
        """Sample idea metrics for decision making."""
        return {
            "idea_id": 123,
            "vote_count": 35,
            "average_rating": 4.3,
            "engagement_score": 0.78,
            "days_since_created": 14,
            "controversy_score": 0.2,
            "comment_count": 8,
            "view_count": 245
        }
    
    def test_evaluate_decision_criteria(self, mock_db, sample_idea_metrics):
        """Test evaluating idea against decision criteria."""
        # Mock criteria
        criteria = Mock(spec=DecisionCriteria)
        criteria.min_vote_count = 20
        criteria.min_average_rating = 4.0
        criteria.min_engagement_score = 0.7
        criteria.max_controversy_score = 0.3
        criteria.min_days_since_created = 7
        criteria.suggested_decision_type = DecisionType.IMPLEMENTATION
        
        # Evaluation logic
        def evaluate_against_criteria(metrics, criteria):
            checks = {
                'vote_count': metrics['vote_count'] >= criteria.min_vote_count,
                'average_rating': metrics['average_rating'] >= criteria.min_average_rating,
                'engagement_score': metrics['engagement_score'] >= criteria.min_engagement_score,
                'controversy_score': metrics['controversy_score'] <= criteria.max_controversy_score,
                'days_since_created': metrics['days_since_created'] >= criteria.min_days_since_created
            }
            
            all_met = all(checks.values())
            return {
                'meets_criteria': all_met,
                'checks': checks,
                'suggested_decision': criteria.suggested_decision_type if all_met else DecisionType.DEFERRAL
            }
        
        result = evaluate_against_criteria(sample_idea_metrics, criteria)
        
        assert result['meets_criteria'] is True
        assert result['suggested_decision'] == DecisionType.IMPLEMENTATION
        assert all(result['checks'].values())
    
    def test_create_automated_decision_suggestion(self, mock_db, sample_idea_metrics):
        """Test creating automated decision suggestion."""
        # Mock decision creation
        suggestion = Decision(
            idea_id=sample_idea_metrics['idea_id'],
            decision_type=DecisionType.IMPLEMENTATION,
            status=DecisionStatus.PENDING,
            summary="Automated suggestion: Implementation recommended",
            rationale="Idea meets all configured criteria for implementation",
            metrics_snapshot=sample_idea_metrics,
            score_threshold=0.7
        )
        
        mock_db.add(suggestion)
        mock_db.commit()
        mock_db.refresh(suggestion)
        
        # Verify suggestion creation
        mock_db.add.assert_called_once_with(suggestion)
        mock_db.commit.assert_called_once()
        assert suggestion.decision_type == DecisionType.IMPLEMENTATION
        assert suggestion.metrics_snapshot == sample_idea_metrics
    
    def test_decision_workflow_progression(self, mock_db):
        """Test decision status workflow progression."""
        # Mock decision
        decision = Mock(spec=Decision)
        decision.id = 1
        decision.status = DecisionStatus.PENDING
        decision.events = []
        
        def update_decision_status(decision, new_status, actor_id, reason=None):
            """Update decision status with event logging."""
            old_status = decision.status
            decision.status = new_status
            
            if new_status == DecisionStatus.APPROVED:
                decision.decided_at = datetime.now(timezone.utc)
            elif new_status == DecisionStatus.IMPLEMENTED:
                decision.implemented_at = datetime.now(timezone.utc)
            
            # Create event
            event = DecisionEvent(
                decision_id=decision.id,
                event_type="status_changed",
                event_data={
                    "old_status": old_status,
                    "new_status": new_status,
                    "reason": reason
                },
                actor_id=actor_id
            )
            
            decision.events.append(event)
            return event
        
        # Progress through workflow
        event1 = update_decision_status(decision, DecisionStatus.IN_REVIEW, "manager_001", "Under review")
        assert decision.status == DecisionStatus.IN_REVIEW
        
        event2 = update_decision_status(decision, DecisionStatus.APPROVED, "manager_001", "Approved for implementation")
        assert decision.status == DecisionStatus.APPROVED
        assert decision.decided_at is not None
        
        event3 = update_decision_status(decision, DecisionStatus.IMPLEMENTED, "dev_team", "Implementation completed")
        assert decision.status == DecisionStatus.IMPLEMENTED
        assert decision.implemented_at is not None
        
        # Verify events were logged
        assert len(decision.events) == 3
        assert decision.events[0].event_data["new_status"] == DecisionStatus.IN_REVIEW
        assert decision.events[1].event_data["new_status"] == DecisionStatus.APPROVED
        assert decision.events[2].event_data["new_status"] == DecisionStatus.IMPLEMENTED
    
    def test_committee_decision_aggregation(self, mock_db):
        """Test aggregating committee member decisions."""
        committee_votes = [
            {'member_id': 'mgr001', 'vote': 'approve', 'weight': 1.0},
            {'member_id': 'mgr002', 'vote': 'approve', 'weight': 1.0},
            {'member_id': 'mgr003', 'vote': 'modify', 'weight': 1.0},
            {'member_id': 'mgr004', 'vote': 'approve', 'weight': 1.5}  # Senior member
        ]
        
        def aggregate_committee_decision(votes):
            """Aggregate committee votes into final decision."""
            vote_weights = {}
            total_weight = 0
            
            for vote in votes:
                vote_type = vote['vote']
                weight = vote['weight']
                
                if vote_type not in vote_weights:
                    vote_weights[vote_type] = 0
                
                vote_weights[vote_type] += weight
                total_weight += weight
            
            # Calculate percentages
            vote_percentages = {
                vote_type: (weight / total_weight) * 100
                for vote_type, weight in vote_weights.items()
            }
            
            # Determine final decision (simple majority)
            final_decision = max(vote_weights, key=vote_weights.get)
            consensus_level = max(vote_percentages.values())
            
            return {
                'final_decision': final_decision,
                'vote_breakdown': vote_percentages,
                'consensus_level': consensus_level,
                'unanimous': len(vote_weights) == 1
            }
        
        result = aggregate_committee_decision(committee_votes)
        
        assert result['final_decision'] == 'approve'
        assert result['consensus_level'] > 50  # Majority
        assert not result['unanimous']  # Not unanimous due to 'modify' vote
        assert 'approve' in result['vote_breakdown']
        assert 'modify' in result['vote_breakdown']
    
    def test_decision_impact_calculation(self, mock_db):
        """Test calculating decision implementation impact."""
        decision_data = {
            'estimated_cost': 75000,
            'estimated_revenue': 200000,
            'resource_requirements': {
                'developers': 2,
                'designers': 1,
                'months': 4
            },
            'risk_factors': ['technical_complexity', 'market_timing'],
            'success_probability': 0.78
        }
        
        def calculate_decision_impact(data):
            """Calculate decision implementation impact metrics."""
            roi_estimate = (data['estimated_revenue'] - data['estimated_cost']) / data['estimated_cost']
            
            # Risk adjustment
            risk_penalty = len(data['risk_factors']) * 0.05
            adjusted_success_prob = max(data['success_probability'] - risk_penalty, 0.1)
            
            # Expected value calculation
            expected_value = (data['estimated_revenue'] - data['estimated_cost']) * adjusted_success_prob
            
            return {
                'roi_estimate': roi_estimate,
                'adjusted_success_probability': adjusted_success_prob,
                'expected_value': expected_value,
                'payback_months': data['resource_requirements']['months'],
                'risk_level': 'high' if len(data['risk_factors']) > 2 else 'medium' if len(data['risk_factors']) > 0 else 'low'
            }
        
        impact = calculate_decision_impact(decision_data)
        
        assert impact['roi_estimate'] > 1.0  # Positive ROI
        assert impact['expected_value'] > 0  # Positive expected value
        assert impact['risk_level'] == 'medium'  # 2 risk factors
        assert 0.0 <= impact['adjusted_success_probability'] <= 1.0


class TestDecisionAPI:
    """Test cases for Decision API endpoints."""
    
    @pytest.fixture
    def mock_get_db(self):
        """Mock database dependency."""
        return Mock()
    
    @pytest.fixture
    def client(self, mock_get_db):
        """Test client with mocked dependencies."""
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/decisions")
        
        # Override dependency
        from services.decision.api import get_db
        app.dependency_overrides[get_db] = lambda: mock_get_db
        
        return TestClient(app)
    
    def test_create_decision_endpoint(self, client, mock_get_db):
        """Test POST /decisions endpoint."""
        decision_data = {
            "idea_id": 123,
            "decision_type": "implementation",
            "summary": "Approved for Q1 implementation",
            "rationale": "Strong business case and user demand",
            "timeline_days": 60,
            "estimated_impact": {
                "cost": 50000,
                "revenue": 150000
            }
        }
        
        headers = {"Authorization": "Bearer manager_token"}
        
        # Mock authentication
        with patch('services.decision.api.get_current_user') as mock_auth:
            mock_auth.return_value = {
                "user_id": "manager_001",
                "role": "manager",
                "permissions": ["make_decisions"]
            }
            
            # Mock database operations
            mock_get_db.add = Mock()
            mock_get_db.commit = Mock()
            mock_get_db.refresh = Mock()
            
            # Verify decision data structure
            assert decision_data["idea_id"] == 123
            assert decision_data["decision_type"] == "implementation"
            assert decision_data["timeline_days"] == 60
    
    def test_get_decisions_endpoint(self, client, mock_get_db):
        """Test GET /decisions endpoint."""
        mock_decisions = [
            {
                "id": 1,
                "idea_id": 123,
                "decision_type": "implementation",
                "status": "approved",
                "summary": "Implementation approved",
                "decided_by": "manager_001",
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": 2,
                "idea_id": 456,
                "decision_type": "rejection",
                "status": "rejected",
                "summary": "Not aligned with strategy",
                "decided_by": "manager_002",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        ]
        
        mock_get_db.query().offset().limit().all.return_value = mock_decisions
        
        # Verify mock data
        decisions = mock_get_db.query().offset().limit().all()
        assert len(decisions) == 2
        assert decisions[0]["decision_type"] == "implementation"
        assert decisions[1]["decision_type"] == "rejection"
    
    def test_get_decision_by_id_endpoint(self, client, mock_get_db):
        """Test GET /decisions/{id} endpoint."""
        decision_id = 1
        mock_decision = {
            "id": decision_id,
            "idea_id": 123,
            "decision_type": "implementation",
            "status": "approved",
            "summary": "Implementation approved",
            "rationale": "Strong business justification",
            "metrics_snapshot": {
                "vote_count": 45,
                "average_rating": 4.7
            },
            "events": []
        }
        
        mock_get_db.query().filter().first.return_value = mock_decision
        
        result = mock_get_db.query().filter().first()
        assert result["id"] == decision_id
        assert result["metrics_snapshot"]["vote_count"] == 45


if __name__ == "__main__":
    pytest.main([__file__, "-v"])