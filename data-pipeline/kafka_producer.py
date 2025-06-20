"""Kafka producer for real-time event streaming in MindMesh."""

import json
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MindMeshKafkaProducer:
    """High-performance Kafka producer for MindMesh events."""
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        client_id: str = "mindmesh-producer",
        **producer_config
    ):
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        
        # Default producer configuration for high throughput
        default_config = {
            'bootstrap_servers': [bootstrap_servers],
            'client_id': client_id,
            'value_serializer': lambda v: json.dumps(v, default=str).encode('utf-8'),
            'key_serializer': lambda k: str(k).encode('utf-8') if k else None,
            'acks': 'all',  # Wait for all replicas
            'retries': 3,
            'batch_size': 16384,  # 16KB batch size
            'linger_ms': 10,  # Wait 10ms to batch messages
            'compression_type': 'snappy',  # Compress messages
            'max_in_flight_requests_per_connection': 5,
            'enable_idempotence': True,  # Prevent duplicates
        }
        
        # Override with user config
        default_config.update(producer_config)
        
        try:
            self.producer = KafkaProducer(**default_config)
            logger.info(f"Kafka producer initialized with servers: {bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            raise
    
    def send_event(
        self,
        topic: str,
        event_data: Dict[str, Any],
        key: Optional[str] = None,
        partition: Optional[int] = None
    ) -> bool:
        """Send a single event to Kafka topic."""
        try:
            # Add metadata to event
            enriched_event = self._enrich_event(event_data)
            
            # Send to Kafka
            future = self.producer.send(
                topic=topic,
                value=enriched_event,
                key=key,
                partition=partition
            )
            
            # Add callback for monitoring
            future.add_callback(self._on_send_success)
            future.add_errback(self._on_send_error)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send event to topic {topic}: {e}")
            return False
    
    def send_user_interaction(
        self,
        user_id: str,
        interaction_type: str,
        content_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Send user interaction event."""
        event = {
            'event_type': 'user_interaction',
            'user_id': user_id,
            'interaction_type': interaction_type,
            'content_id': content_id,
            'metadata': metadata or {}
        }
        
        return self.send_event(
            topic='user-interactions',
            event_data=event,
            key=user_id
        )
    
    def send_thought_capture(
        self,
        user_id: str,
        thought_text: str,
        sentiment_score: Optional[float] = None,
        tags: Optional[list] = None
    ) -> bool:
        """Send thought capture event."""
        event = {
            'event_type': 'thought_capture',
            'user_id': user_id,
            'thought_text': thought_text,
            'sentiment_score': sentiment_score,
            'tags': tags or [],
            'word_count': len(thought_text.split())
        }
        
        return self.send_event(
            topic='thought-captures',
            event_data=event,
            key=user_id
        )
    
    def send_system_metric(
        self,
        metric_name: str,
        metric_value: float,
        component: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Send system performance metric."""
        event = {
            'event_type': 'system_metric',
            'metric_name': metric_name,
            'metric_value': metric_value,
            'component': component,
            'metadata': metadata or {}
        }
        
        return self.send_event(
            topic='system-metrics',
            event_data=event,
            key=component
        )
    
    def send_recommendation_event(
        self,
        user_id: str,
        recommended_content: list,
        algorithm: str,
        confidence_score: float
    ) -> bool:
        """Send recommendation generated event."""
        event = {
            'event_type': 'recommendation_generated',
            'user_id': user_id,
            'recommended_content': recommended_content,
            'algorithm': algorithm,
            'confidence_score': confidence_score,
            'content_count': len(recommended_content)
        }
        
        return self.send_event(
            topic='recommendations',
            event_data=event,
            key=user_id
        )
    
    def send_batch_events(
        self,
        topic: str,
        events: list,
        key_field: Optional[str] = None
    ) -> int:
        """Send multiple events in batch."""
        successful_sends = 0
        
        for event in events:
            key = event.get(key_field) if key_field else None
            if self.send_event(topic, event, key):
                successful_sends += 1
        
        # Flush to ensure all messages are sent
        self.producer.flush(timeout=30)
        
        logger.info(f"Sent {successful_sends}/{len(events)} events to topic {topic}")
        return successful_sends
    
    def _enrich_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add metadata to event."""
        return {
            **event_data,
            'event_id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'producer_id': self.client_id,
            'version': '1.0'
        }
    
    def _on_send_success(self, record_metadata):
        """Callback for successful sends."""
        logger.debug(
            f"Message sent successfully to topic: {record_metadata.topic}, "
            f"partition: {record_metadata.partition}, "
            f"offset: {record_metadata.offset}"
        )
    
    def _on_send_error(self, exception):
        """Callback for send errors."""
        logger.error(f"Failed to send message: {exception}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get producer metrics."""
        metrics = self.producer.metrics()
        
        # Extract key metrics
        key_metrics = {
            'record_send_rate': metrics.get('producer-metrics', {}).get('record-send-rate', 0),
            'record_send_total': metrics.get('producer-metrics', {}).get('record-send-total', 0),
            'record_error_rate': metrics.get('producer-metrics', {}).get('record-error-rate', 0),
            'record_retry_rate': metrics.get('producer-metrics', {}).get('record-retry-rate', 0),
            'batch_size_avg': metrics.get('producer-metrics', {}).get('batch-size-avg', 0),
            'compression_rate_avg': metrics.get('producer-metrics', {}).get('compression-rate-avg', 0)
        }
        
        return key_metrics
    
    def health_check(self) -> bool:
        """Check if producer is healthy."""
        try:
            # Send a simple health check message
            test_event = {'health_check': True}
            future = self.producer.send('health-check', test_event)
            future.get(timeout=5)  # Wait for confirmation
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def close(self):
        """Close the producer and flush remaining messages."""
        try:
            logger.info("Closing Kafka producer...")
            self.producer.flush(timeout=30)
            self.producer.close(timeout=30)
            logger.info("Kafka producer closed successfully")
        except Exception as e:
            logger.error(f"Error closing producer: {e}")


class EventGenerator:
    """Generate sample events for testing and demonstration."""
    
    def __init__(self, producer: MindMeshKafkaProducer):
        self.producer = producer
    
    def generate_user_activity(self, num_users: int = 100, duration_seconds: int = 60):
        """Generate simulated user activity events."""
        import random
        
        user_ids = [f"user_{i}" for i in range(num_users)]
        interaction_types = ['view', 'like', 'share', 'comment', 'search', 'create']
        content_ids = [f"content_{i}" for i in range(500)]
        
        start_time = time.time()
        event_count = 0
        
        logger.info(f"Generating user activity for {duration_seconds} seconds...")
        
        while time.time() - start_time < duration_seconds:
            user_id = random.choice(user_ids)
            interaction_type = random.choice(interaction_types)
            content_id = random.choice(content_ids) if random.random() > 0.3 else None
            
            metadata = {
                'session_id': f"session_{random.randint(1, 1000)}",
                'device_type': random.choice(['mobile', 'desktop', 'tablet']),
                'location': random.choice(['US', 'CA', 'UK', 'DE', 'FR'])
            }
            
            if self.producer.send_user_interaction(
                user_id, interaction_type, content_id, metadata
            ):
                event_count += 1
            
            # Random delay between events
            time.sleep(random.uniform(0.1, 2.0))
        
        logger.info(f"Generated {event_count} user activity events")
    
    def generate_thought_stream(self, user_id: str, num_thoughts: int = 50):
        """Generate a stream of thoughts for a user."""
        import random
        
        sample_thoughts = [
            "I need to improve my productivity today",
            "This new framework looks promising for our project",
            "I should spend more time learning about machine learning",
            "The weather is perfect for a walk",
            "I wonder how this algorithm could be optimized",
            "Team collaboration has been excellent this week",
            "Need to remember to call mom later",
            "This book has some fascinating insights",
            "I should plan my vacation soon",
            "The new feature release went smoothly"
        ]
        
        tags_pool = ['work', 'personal', 'learning', 'health', 'family', 'technology']
        
        logger.info(f"Generating {num_thoughts} thoughts for user {user_id}")
        
        for i in range(num_thoughts):
            thought = random.choice(sample_thoughts)
            sentiment = random.uniform(-1.0, 1.0)
            tags = random.sample(tags_pool, random.randint(1, 3))
            
            self.producer.send_thought_capture(user_id, thought, sentiment, tags)
            time.sleep(random.uniform(0.5, 3.0))
        
        logger.info(f"Generated {num_thoughts} thoughts for user {user_id}")


if __name__ == "__main__":
    # Example usage
    producer = MindMeshKafkaProducer()
    
    try:
        # Test health check
        if producer.health_check():
            logger.info("Producer is healthy")
        
        # Generate sample events
        generator = EventGenerator(producer)
        
        # Generate user activity for 30 seconds
        generator.generate_user_activity(num_users=10, duration_seconds=30)
        
        # Generate thoughts for a specific user
        generator.generate_thought_stream("test_user_1", num_thoughts=10)
        
        # Show metrics
        metrics = producer.get_metrics()
        logger.info(f"Producer metrics: {metrics}")
        
    except KeyboardInterrupt:
        logger.info("Stopping event generation...")
    finally:
        producer.close()