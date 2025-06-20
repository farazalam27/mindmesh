"""Real-time vote processing using Spark Structured Streaming."""
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, count, avg, sum as spark_sum, window, 
    current_timestamp, expr, to_json, struct, 
    from_json, when, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, 
    IntegerType, FloatType, TimestampType
)
import logging
import os
from typing import Optional
from .spark_session import get_spark_session

logger = logging.getLogger(__name__)

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
VOTE_TOPIC = os.getenv("VOTE_TOPIC", "vote-events")
ANALYTICS_TOPIC = os.getenv("ANALYTICS_TOPIC", "vote-analytics")


# Define schemas
vote_event_schema = StructType([
    StructField("event_id", StringType(), True),
    StructField("event_type", StringType(), True),  # vote_cast, vote_removed, vote_updated
    StructField("idea_id", IntegerType(), True),
    StructField("user_id", StringType(), True),
    StructField("vote_type", StringType(), True),  # upvote, downvote, rating
    StructField("rating", FloatType(), True),
    StructField("timestamp", TimestampType(), True),
    StructField("ip_address", StringType(), True),
    StructField("user_agent", StringType(), True)
])


class VoteStreamProcessor:
    """Process vote events in real-time using Spark Structured Streaming."""
    
    def __init__(self, spark: Optional[SparkSession] = None):
        self.spark = spark or get_spark_session()
        self.checkpoints_base = os.getenv("CHECKPOINTS_DIR", "/tmp/spark-streaming-checkpoints")
    
    def read_vote_stream(self) -> DataFrame:
        """Read vote events from Kafka."""
        try:
            return self.spark \
                .readStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
                .option("subscribe", VOTE_TOPIC) \
                .option("startingOffsets", "latest") \
                .option("failOnDataLoss", "false") \
                .load() \
                .select(
                    from_json(col("value").cast("string"), vote_event_schema).alias("data")
                ) \
                .select("data.*") \
                .withColumn("processing_time", current_timestamp())
        except Exception as e:
            logger.error(f"Error reading vote stream: {e}")
            raise
    
    def aggregate_votes_by_window(self, df: DataFrame, window_duration: str = "5 minutes") -> DataFrame:
        """
        Aggregate votes by time window.
        
        Args:
            df: Input DataFrame with vote events
            window_duration: Window duration for aggregation
            
        Returns:
            Aggregated DataFrame
        """
        return df \
            .withWatermark("timestamp", "10 minutes") \
            .groupBy(
                window(col("timestamp"), window_duration),
                col("idea_id")
            ) \
            .agg(
                count(when(col("vote_type") == "upvote", 1)).alias("upvotes"),
                count(when(col("vote_type") == "downvote", 1)).alias("downvotes"),
                count(when(col("vote_type") == "rating", 1)).alias("ratings"),
                avg(when(col("vote_type") == "rating", col("rating"))).alias("avg_rating"),
                count("*").alias("total_events")
            ) \
            .select(
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("idea_id"),
                col("upvotes"),
                col("downvotes"),
                col("ratings"),
                col("avg_rating"),
                col("total_events"),
                expr("upvotes - downvotes").alias("net_votes")
            )
    
    def calculate_trending_ideas(self, df: DataFrame) -> DataFrame:
        """
        Calculate trending ideas based on recent vote velocity.
        
        Args:
            df: Aggregated vote DataFrame
            
        Returns:
            DataFrame with trending scores
        """
        # Calculate trending score based on recent activity
        return df \
            .withColumn(
                "trending_score",
                expr("""
                    (upvotes * 2 + ratings * 1.5 - downvotes) * 
                    exp(-0.1 * (unix_timestamp(current_timestamp()) - unix_timestamp(window_end)) / 3600)
                """)
            ) \
            .filter(col("trending_score") > 0) \
            .orderBy(col("trending_score").desc())
    
    def detect_anomalies(self, df: DataFrame) -> DataFrame:
        """
        Detect voting anomalies (potential manipulation).
        
        Args:
            df: Vote events DataFrame
            
        Returns:
            DataFrame with anomaly flags
        """
        # Group by user and time window to detect rapid voting
        user_activity = df \
            .withWatermark("timestamp", "10 minutes") \
            .groupBy(
                window(col("timestamp"), "1 minute"),
                col("user_id")
            ) \
            .agg(
                count("*").alias("vote_count"),
                count(distinct=col("idea_id")).alias("unique_ideas"),
                count(distinct=col("ip_address")).alias("unique_ips")
            ) \
            .withColumn(
                "is_anomaly",
                when(
                    (col("vote_count") > 20) |  # Too many votes per minute
                    (col("unique_ips") > 5),     # Multiple IPs per user
                    lit(True)
                ).otherwise(lit(False))
            )
        
        return user_activity.filter(col("is_anomaly") == True)
    
    def write_to_kafka(self, df: DataFrame, topic: str, checkpoint_path: str):
        """Write streaming DataFrame to Kafka."""
        return df \
            .select(
                to_json(struct([col(c) for c in df.columns])).alias("value")
            ) \
            .writeStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
            .option("topic", topic) \
            .option("checkpointLocation", f"{self.checkpoints_base}/{checkpoint_path}") \
            .outputMode("update") \
            .start()
    
    def write_to_console(self, df: DataFrame, output_mode: str = "update"):
        """Write streaming DataFrame to console for debugging."""
        return df \
            .writeStream \
            .format("console") \
            .outputMode(output_mode) \
            .option("truncate", False) \
            .start()
    
    def write_to_postgres(self, df: DataFrame, table_name: str, checkpoint_path: str):
        """Write streaming DataFrame to PostgreSQL."""
        def write_batch(batch_df, batch_id):
            """Write each batch to PostgreSQL."""
            if batch_df.count() > 0:
                try:
                    from .spark_session import write_to_postgres
                    write_to_postgres(batch_df, table_name, mode="append")
                    logger.info(f"Written batch {batch_id} to {table_name}")
                except Exception as e:
                    logger.error(f"Error writing batch {batch_id}: {e}")
        
        return df \
            .writeStream \
            .foreachBatch(write_batch) \
            .option("checkpointLocation", f"{self.checkpoints_base}/{checkpoint_path}") \
            .outputMode("update") \
            .start()
    
    def start_vote_processing(self):
        """Start all vote processing streams."""
        try:
            # Read vote stream
            vote_stream = self.read_vote_stream()
            
            # 1. Real-time vote aggregation
            vote_aggregates = self.aggregate_votes_by_window(vote_stream)
            aggregate_query = self.write_to_kafka(
                vote_aggregates, 
                "vote-aggregates", 
                "vote-aggregates-checkpoint"
            )
            
            # 2. Trending ideas calculation
            trending_ideas = self.calculate_trending_ideas(vote_aggregates)
            trending_query = self.write_to_postgres(
                trending_ideas,
                "trending_ideas",
                "trending-ideas-checkpoint"
            )
            
            # 3. Anomaly detection
            anomalies = self.detect_anomalies(vote_stream)
            anomaly_query = self.write_to_kafka(
                anomalies,
                "vote-anomalies",
                "vote-anomalies-checkpoint"
            )
            
            logger.info("Started all streaming queries successfully")
            
            return {
                "aggregate_query": aggregate_query,
                "trending_query": trending_query,
                "anomaly_query": anomaly_query
            }
            
        except Exception as e:
            logger.error(f"Error starting vote processing: {e}")
            raise
    
    def stop_all_streams(self):
        """Stop all active streaming queries."""
        for query in self.spark.streams.active:
            try:
                query.stop()
                logger.info(f"Stopped streaming query: {query.name}")
            except Exception as e:
                logger.error(f"Error stopping query {query.name}: {e}")


# Utility function to run streaming job
def run_streaming_job():
    """Run the vote stream processing job."""
    processor = VoteStreamProcessor()
    queries = processor.start_vote_processing()
    
    try:
        # Wait for all queries to terminate
        for query in queries.values():
            query.awaitTermination()
    except KeyboardInterrupt:
        logger.info("Stopping streaming job...")
        processor.stop_all_streams()
    except Exception as e:
        logger.error(f"Streaming job error: {e}")
        processor.stop_all_streams()
        raise


if __name__ == "__main__":
    run_streaming_job()