"""Event sourcing implementation for Decision service."""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from .models import Decision, DecisionEvent, DecisionStatus
from .schemas import DecisionEventCreate

logger = logging.getLogger(__name__)


class EventStore:
    """Event store for decision events."""
    
    @staticmethod
    def record_event(
        db: Session,
        decision_id: int,
        event_type: str,
        event_data: Dict[str, Any],
        actor_id: str,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None
    ) -> DecisionEvent:
        """
        Record a new event for a decision.
        
        Args:
            db: Database session
            decision_id: ID of the decision
            event_type: Type of event
            event_data: Event data payload
            actor_id: ID of the actor
            actor_name: Name of the actor
            actor_role: Role of the actor
            
        Returns:
            Created DecisionEvent
        """
        try:
            event = DecisionEvent(
                decision_id=decision_id,
                event_type=event_type,
                event_data=event_data,
                actor_id=actor_id,
                actor_name=actor_name,
                actor_role=actor_role
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            
            logger.info(f"Recorded event {event_type} for decision {decision_id}")
            return event
            
        except Exception as e:
            logger.error(f"Error recording event: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def get_decision_history(db: Session, decision_id: int) -> List[DecisionEvent]:
        """
        Get complete event history for a decision.
        
        Args:
            db: Database session
            decision_id: ID of the decision
            
        Returns:
            List of events ordered by time
        """
        return db.query(DecisionEvent).filter(
            DecisionEvent.decision_id == decision_id
        ).order_by(DecisionEvent.occurred_at.asc()).all()
    
    @staticmethod
    def replay_events(db: Session, decision_id: int) -> Decision:
        """
        Replay all events to reconstruct decision state.
        
        Args:
            db: Database session
            decision_id: ID of the decision
            
        Returns:
            Reconstructed Decision object
        """
        decision = db.query(Decision).filter(Decision.id == decision_id).first()
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        
        events = EventStore.get_decision_history(db, decision_id)
        
        # Apply each event to reconstruct state
        for event in events:
            EventStore._apply_event(decision, event)
        
        return decision
    
    @staticmethod
    def _apply_event(decision: Decision, event: DecisionEvent):
        """Apply an event to a decision object."""
        if event.event_type == "status_changed":
            decision.status = event.event_data.get("new_status")
            if decision.status == DecisionStatus.APPROVED:
                decision.decided_at = event.occurred_at
            elif decision.status == DecisionStatus.IMPLEMENTED:
                decision.implemented_at = event.occurred_at
                
        elif event.event_type == "metrics_updated":
            decision.metrics_snapshot = event.event_data.get("metrics", {})
            
        elif event.event_type == "implementation_plan_updated":
            decision.implementation_plan = event.event_data.get("plan")
            
        elif event.event_type == "committee_assigned":
            decision.decision_committee = event.event_data.get("committee", [])
            
        elif event.event_type == "conditions_updated":
            decision.conditions = event.event_data.get("conditions", [])


class DecisionEventHandlers:
    """Event handlers for decision-related events."""
    
    @staticmethod
    def on_decision_created(
        db: Session,
        decision: Decision,
        actor_id: str,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None
    ):
        """Handle decision creation event."""
        event_data = {
            "idea_id": decision.idea_id,
            "decision_type": decision.decision_type,
            "initial_status": decision.status,
            "summary": decision.summary
        }
        
        EventStore.record_event(
            db=db,
            decision_id=decision.id,
            event_type="decision_created",
            event_data=event_data,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role
        )
    
    @staticmethod
    def on_status_changed(
        db: Session,
        decision: Decision,
        old_status: DecisionStatus,
        new_status: DecisionStatus,
        actor_id: str,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        reason: Optional[str] = None
    ):
        """Handle decision status change event."""
        event_data = {
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason
        }
        
        # Update decision status
        decision.status = new_status
        if new_status == DecisionStatus.APPROVED:
            decision.decided_at = datetime.utcnow()
            decision.decided_by = actor_id
        elif new_status == DecisionStatus.IMPLEMENTED:
            decision.implemented_at = datetime.utcnow()
        
        EventStore.record_event(
            db=db,
            decision_id=decision.id,
            event_type="status_changed",
            event_data=event_data,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role
        )
    
    @staticmethod
    def on_metrics_snapshot_taken(
        db: Session,
        decision: Decision,
        metrics: Dict[str, Any],
        actor_id: str
    ):
        """Handle metrics snapshot event."""
        event_data = {
            "metrics": metrics,
            "snapshot_time": datetime.utcnow().isoformat()
        }
        
        # Update decision metrics
        decision.metrics_snapshot = metrics
        
        EventStore.record_event(
            db=db,
            decision_id=decision.id,
            event_type="metrics_snapshot_taken",
            event_data=event_data,
            actor_id=actor_id
        )
    
    @staticmethod
    def on_committee_assigned(
        db: Session,
        decision: Decision,
        committee_members: List[str],
        actor_id: str,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None
    ):
        """Handle committee assignment event."""
        event_data = {
            "committee": committee_members,
            "committee_size": len(committee_members)
        }
        
        # Update decision committee
        decision.decision_committee = committee_members
        
        EventStore.record_event(
            db=db,
            decision_id=decision.id,
            event_type="committee_assigned",
            event_data=event_data,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role
        )
    
    @staticmethod
    def on_implementation_plan_updated(
        db: Session,
        decision: Decision,
        plan: str,
        timeline_days: Optional[int],
        resource_requirements: Dict[str, Any],
        actor_id: str,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None
    ):
        """Handle implementation plan update event."""
        event_data = {
            "plan": plan,
            "timeline_days": timeline_days,
            "resource_requirements": resource_requirements
        }
        
        # Update decision
        decision.implementation_plan = plan
        if timeline_days:
            decision.timeline_days = timeline_days
        decision.resource_requirements = resource_requirements
        
        EventStore.record_event(
            db=db,
            decision_id=decision.id,
            event_type="implementation_plan_updated",
            event_data=event_data,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role
        )


class EventProjections:
    """Event projections for analytics and reporting."""
    
    @staticmethod
    def get_decision_timeline(db: Session, decision_id: int) -> List[Dict[str, Any]]:
        """
        Get timeline view of decision events.
        
        Args:
            db: Database session
            decision_id: ID of the decision
            
        Returns:
            List of timeline entries
        """
        events = EventStore.get_decision_history(db, decision_id)
        
        timeline = []
        for event in events:
            timeline.append({
                "timestamp": event.occurred_at.isoformat(),
                "event_type": event.event_type,
                "actor": {
                    "id": event.actor_id,
                    "name": event.actor_name,
                    "role": event.actor_role
                },
                "details": event.event_data
            })
        
        return timeline
    
    @staticmethod
    def get_decision_audit_trail(
        db: Session,
        decision_id: int,
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for a decision.
        
        Args:
            db: Database session
            decision_id: ID of the decision
            event_types: Optional filter for event types
            
        Returns:
            Audit trail entries
        """
        query = db.query(DecisionEvent).filter(
            DecisionEvent.decision_id == decision_id
        )
        
        if event_types:
            query = query.filter(DecisionEvent.event_type.in_(event_types))
        
        events = query.order_by(DecisionEvent.occurred_at.desc()).all()
        
        audit_trail = []
        for event in events:
            audit_trail.append({
                "event_id": event.event_id,
                "timestamp": event.occurred_at.isoformat(),
                "event_type": event.event_type,
                "actor": f"{event.actor_name or event.actor_id} ({event.actor_role or 'Unknown'})",
                "changes": event.event_data
            })
        
        return audit_trail
    
    @staticmethod
    def get_actor_activity(
        db: Session,
        actor_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get activity summary for an actor.
        
        Args:
            db: Database session
            actor_id: ID of the actor
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Activity summary
        """
        query = db.query(DecisionEvent).filter(
            DecisionEvent.actor_id == actor_id
        )
        
        if start_date:
            query = query.filter(DecisionEvent.occurred_at >= start_date)
        if end_date:
            query = query.filter(DecisionEvent.occurred_at <= end_date)
        
        events = query.all()
        
        # Aggregate activity
        activity_summary = {
            "actor_id": actor_id,
            "total_actions": len(events),
            "actions_by_type": {},
            "decisions_affected": set(),
            "recent_actions": []
        }
        
        for event in events:
            # Count by type
            event_type = event.event_type
            activity_summary["actions_by_type"][event_type] = \
                activity_summary["actions_by_type"].get(event_type, 0) + 1
            
            # Track affected decisions
            activity_summary["decisions_affected"].add(event.decision_id)
        
        # Convert set to list for JSON serialization
        activity_summary["decisions_affected"] = list(activity_summary["decisions_affected"])
        
        # Get recent actions
        recent_events = sorted(events, key=lambda e: e.occurred_at, reverse=True)[:10]
        activity_summary["recent_actions"] = [
            {
                "timestamp": e.occurred_at.isoformat(),
                "event_type": e.event_type,
                "decision_id": e.decision_id
            }
            for e in recent_events
        ]
        
        return activity_summary