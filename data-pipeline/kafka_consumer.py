"""Kafka consumer for real-time event processing in MindMesh."""

import json
import logging
import threading
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import time
import signal
import sys
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MindMeshKafkaConsumer:
    """High-performance Kafka consumer for MindMesh events."""
    
    def __init__(
        self,
        topics: List[str],
        group_id: str,
        bootstrap_servers: str = "localhost:9092",
        **consumer_config
    ):
        self.topics = topics
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers
        self.running = False
        self.consumer = None
        self.message_handlers = {}
        self.stats = defaultdict(int)
        
        # Default consumer configuration
        default_config = {
            'bootstrap_servers': [bootstrap_servers],
            'group_id': group_id,
            'key_deserializer': lambda k: k.decode('utf-8') if k else None,
            'value_deserializer': lambda v: json.loads(v.decode('utf-8')),
            'auto_offset_reset': 'latest',
            'enable_auto_commit': True,
            'auto_commit_interval_ms': 1000,
            'session_timeout_ms': 30000,
            'heartbeat_interval_ms': 3000,
            'max_poll_records': 500,
            'fetch_min_bytes': 1024,
            'fetch_max_wait_ms': 500
        }
        
        # Override with user config
        default_config.update(consumer_config)
        
        try:
            self.consumer = KafkaConsumer(**default_config)
            self.consumer.subscribe(topics)
            logger.info(f"Kafka consumer initialized for topics: {topics}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            raise
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def register_handler(self, event_type: str, handler: Callable[[Dict], None]):
        """Register a handler for specific event types."""
        self.message_handlers[event_type] = handler
        logger.info(f"Registered handler for event type: {event_type}")
    
    def start_consuming(self, poll_timeout_ms: int = 1000):
        """Start consuming messages from Kafka topics."""
        self.running = True
        logger.info(f"Starting to consume from topics: {self.topics}")
        
        try:
            while self.running:
                message_batch = self.consumer.poll(timeout_ms=poll_timeout_ms)
                
                if message_batch:
                    self._process_message_batch(message_batch)
                
                # Commit offsets periodically
                if self.stats['messages_processed'] % 100 == 0:
                    self.consumer.commit()
                
        except Exception as e:
            logger.error(f"Error during message consumption: {e}")
        finally:
            self._cleanup()
    
    def _process_message_batch(self, message_batch):
        """Process a batch of messages."""
        for topic_partition, messages in message_batch.items():
            for message in messages:
                try:
                    self._process_single_message(message)
                    self.stats['messages_processed'] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.stats['processing_errors'] += 1
    
    def _process_single_message(self, message):
        """Process a single Kafka message."""
        try:
            event_data = message.value
            event_type = event_data.get('event_type')
            
            # Update statistics
            self.stats[f'topic_{message.topic}'] += 1
            self.stats[f'event_type_{event_type}'] += 1
            
            # Route to appropriate handler
            if event_type in self.message_handlers:
                self.message_handlers[event_type](event_data)
            else:
                # Default processing
                self._default_message_handler(event_data, message.topic)
            
        except Exception as e:
            logger.error(f"Error processing message from topic {message.topic}: {e}")
            raise
    
    def _default_message_handler(self, event_data: Dict, topic: str):
        """Default handler for unregistered event types."""
        logger.debug(f"Processed message from topic {topic}: {event_data.get('event_type', 'unknown')}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop_consuming()
    
    def stop_consuming(self):
        """Stop consuming messages."""
        self.running = False
        logger.info("Stopping message consumption...")
    
    def _cleanup(self):
        """Cleanup resources."""
        if self.consumer:
            self.consumer.close()
        logger.info("Consumer cleanup complete")
    
    def get_stats(self) -> Dict[str, int]:
        """Get consumer statistics."""
        return dict(self.stats)


class UserInteractionProcessor:
    """Process user interaction events."""
    
    def __init__(self, db_connection=None, redis_client=None):
        self.db_connection = db_connection
        self.redis_client = redis_client
        self.interaction_counts = defaultdict(int)
    
    def process_interaction(self, event: Dict[str, Any]):
        """Process user interaction event."""
        try:
            user_id = event['user_id']
            interaction_type = event['interaction_type']
            content_id = event.get('content_id')
            timestamp = event['timestamp']
            
            # Update real-time counters
            self.interaction_counts[f"{user_id}_{interaction_type}"] += 1
            
            # Store in database (if available)
            if self.db_connection:
                self._store_interaction(event)
            
            # Update cache (if available)
            if self.redis_client:
                self._update_cache(user_id, interaction_type)
            
            # Generate real-time insights
            self._generate_insights(event)
            
            logger.debug(f"Processed interaction: {user_id} -> {interaction_type}")
            
        except Exception as e:
            logger.error(f"Error processing user interaction: {e}")
    
    def _store_interaction(self, event: Dict):
        """Store interaction in database."""
        # Database storage logic would go here
        pass
    
    def _update_cache(self, user_id: str, interaction_type: str):
        """Update Redis cache with interaction data."""
        # Cache update logic would go here
        pass
    
    def _generate_insights(self, event: Dict):
        """Generate real-time insights from interaction."""
        user_id = event['user_id']
        
        # Check for patterns
        total_interactions = sum(
            count for key, count in self.interaction_counts.items()
            if key.startswith(user_id)
        )
        
        if total_interactions > 0 and total_interactions % 10 == 0:
            logger.info(f"User {user_id} reached {total_interactions} interactions")


class ThoughtProcessor:
    """Process thought capture events."""
    
    def __init__(self, sentiment_analyzer=None, nlp_processor=None):
        self.sentiment_analyzer = sentiment_analyzer
        self.nlp_processor = nlp_processor
        self.thought_patterns = defaultdict(list)
    
    def process_thought(self, event: Dict[str, Any]):
        """Process thought capture event."""
        try:
            user_id = event['user_id']
            thought_text = event['thought_text']
            sentiment_score = event.get('sentiment_score')
            tags = event.get('tags', [])
            
            # Analyze sentiment if not provided
            if sentiment_score is None and self.sentiment_analyzer:
                sentiment_score = self.sentiment_analyzer.analyze(thought_text)
            
            # Extract insights
            insights = self._extract_insights(thought_text, sentiment_score, tags)
            
            # Store pattern
            self.thought_patterns[user_id].append({
                'timestamp': event['timestamp'],
                'sentiment': sentiment_score,
                'tags': tags,
                'insights': insights
            })
            
            # Trigger alerts if needed
            self._check_wellness_alerts(user_id, sentiment_score)
            
            logger.debug(f"Processed thought for user {user_id}: sentiment={sentiment_score}")
            
        except Exception as e:
            logger.error(f"Error processing thought: {e}")
    
    def _extract_insights(self, text: str, sentiment: float, tags: List[str]) -> Dict:
        """Extract insights from thought text."""
        insights = {
            'word_count': len(text.split()),
            'character_count': len(text),
            'sentiment_category': self._categorize_sentiment(sentiment),
            'dominant_tags': tags[:3]  # Top 3 tags
        }
        
        # Add NLP insights if processor available
        if self.nlp_processor:
            insights.update(self.nlp_processor.analyze(text))
        
        return insights
    
    def _categorize_sentiment(self, score: float) -> str:
        """Categorize sentiment score."""
        if score is None:
            return 'neutral'
        elif score > 0.3:
            return 'positive'
        elif score < -0.3:
            return 'negative'
        else:
            return 'neutral'
    
    def _check_wellness_alerts(self, user_id: str, sentiment: float):
        """Check if wellness alerts should be triggered."""
        if sentiment is not None and sentiment < -0.7:
            logger.warning(f"Low sentiment detected for user {user_id}: {sentiment}")
            # In production, this would trigger appropriate interventions


class SystemMetricsProcessor:
    """Process system performance metrics."""
    
    def __init__(self, metrics_store=None):
        self.metrics_store = metrics_store
        self.metrics_buffer = []
        self.alert_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'response_time': 2000.0,  # milliseconds
            'error_rate': 5.0  # percentage
        }
    
    def process_metric(self, event: Dict[str, Any]):
        """Process system metric event."""
        try:
            metric_name = event['metric_name']
            metric_value = event['metric_value']
            component = event['component']
            timestamp = event['timestamp']
            
            # Buffer metric for batch processing
            self.metrics_buffer.append(event)
            
            # Check for alerts
            self._check_metric_alerts(metric_name, metric_value, component)
            
            # Flush buffer if it's full
            if len(self.metrics_buffer) >= 100:
                self._flush_metrics_buffer()
            
            logger.debug(f"Processed metric: {component}.{metric_name} = {metric_value}")
            
        except Exception as e:
            logger.error(f"Error processing system metric: {e}")
    
    def _check_metric_alerts(self, metric_name: str, value: float, component: str):
        """Check if metric value triggers alerts."""
        threshold = self.alert_thresholds.get(metric_name)
        
        if threshold and value > threshold:
            logger.warning(
                f"ALERT: {component}.{metric_name} = {value} exceeds threshold {threshold}"
            )
            # In production, this would trigger alerting systems
    
    def _flush_metrics_buffer(self):
        """Flush metrics buffer to storage."""
        if self.metrics_store and self.metrics_buffer:
            try:
                self.metrics_store.bulk_insert(self.metrics_buffer)
                self.metrics_buffer.clear()
                logger.debug("Flushed metrics buffer to storage")
            except Exception as e:
                logger.error(f"Error flushing metrics buffer: {e}")


class RecommendationProcessor:
    """Process recommendation events."""
    
    def __init__(self, feedback_store=None):
        self.feedback_store = feedback_store
        self.recommendation_stats = defaultdict(lambda: defaultdict(int))
    
    def process_recommendation(self, event: Dict[str, Any]):
        """Process recommendation event."""
        try:
            user_id = event['user_id']
            algorithm = event['algorithm']
            confidence_score = event['confidence_score']
            content_count = event['content_count']
            
            # Update statistics
            self.recommendation_stats[algorithm]['generated'] += 1
            self.recommendation_stats[algorithm]['total_confidence'] += confidence_score
            
            # Store for A/B testing and feedback collection
            if self.feedback_store:
                self._store_recommendation_data(event)
            
            logger.debug(
                f"Processed recommendation: {algorithm} for {user_id} "
                f"(confidence: {confidence_score})"
            )
            
        except Exception as e:
            logger.error(f"Error processing recommendation: {e}")
    
    def _store_recommendation_data(self, event: Dict):
        """Store recommendation data for analysis."""
        # Storage logic for recommendation tracking
        pass
    
    def get_algorithm_performance(self) -> Dict:
        """Get performance metrics for recommendation algorithms."""
        performance = {}
        
        for algorithm, stats in self.recommendation_stats.items():
            if stats['generated'] > 0:
                avg_confidence = stats['total_confidence'] / stats['generated']
                performance[algorithm] = {
                    'recommendations_generated': stats['generated'],
                    'average_confidence': avg_confidence
                }
        
        return performance


def create_mindmesh_consumer() -> MindMeshKafkaConsumer:
    """Create and configure MindMesh consumer with all processors."""
    topics = ['user-interactions', 'thought-captures', 'system-metrics', 'recommendations']
    consumer = MindMeshKafkaConsumer(topics, 'mindmesh-consumer-group')
    
    # Initialize processors
    interaction_processor = UserInteractionProcessor()
    thought_processor = ThoughtProcessor()
    metrics_processor = SystemMetricsProcessor()
    recommendation_processor = RecommendationProcessor()
    
    # Register handlers
    consumer.register_handler('user_interaction', interaction_processor.process_interaction)
    consumer.register_handler('thought_capture', thought_processor.process_thought)
    consumer.register_handler('system_metric', metrics_processor.process_metric)
    consumer.register_handler('recommendation_generated', recommendation_processor.process_recommendation)
    
    return consumer


if __name__ == "__main__":
    # Example usage
    consumer = create_mindmesh_consumer()
    
    try:
        logger.info("Starting MindMesh event processing...")
        consumer.start_consuming()
    except KeyboardInterrupt:
        logger.info("Shutting down consumer...")
    finally:
        stats = consumer.get_stats()
        logger.info(f"Final consumer statistics: {stats}")
        consumer.stop_consuming()