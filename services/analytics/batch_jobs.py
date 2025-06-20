"""Batch analytics jobs for MindMesh platform."""
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, count, avg, sum as spark_sum, stddev,
    max as spark_max, min as spark_min, 
    datediff, current_date, date_sub,
    when, lit, row_number, dense_rank,
    collect_list, array_distinct, size
)
from pyspark.sql.window import Window
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from .spark_session import get_spark_session, read_from_postgres, write_to_postgres

logger = logging.getLogger(__name__)


class AnalyticsBatchProcessor:
    """Batch analytics processor for idea and voting data."""
    
    def __init__(self, spark: Optional[SparkSession] = None):
        self.spark = spark or get_spark_session()
        
    def calculate_idea_metrics(self, lookback_days: int = 30) -> DataFrame:
        """
        Calculate comprehensive metrics for ideas.
        
        Args:
            lookback_days: Number of days to look back for metrics
            
        Returns:
            DataFrame with idea metrics
        """
        try:
            # Read ideas and votes data
            ideas_df = read_from_postgres(self.spark, "ideas")
            votes_df = read_from_postgres(self.spark, "votes")
            comments_df = read_from_postgres(self.spark, "comments")
            
            # Filter for recent data
            cutoff_date = date_sub(current_date(), lookback_days)
            
            # Aggregate vote metrics
            vote_metrics = votes_df.groupBy("idea_id").agg(
                count(when(col("vote_type") == "upvote", 1)).alias("upvote_count"),
                count(when(col("vote_type") == "downvote", 1)).alias("downvote_count"),
                count(when(col("vote_type") == "rating", 1)).alias("rating_count"),
                avg(when(col("vote_type") == "rating", col("rating"))).alias("avg_rating"),
                stddev(when(col("vote_type") == "rating", col("rating"))).alias("rating_stddev"),
                count("*").alias("total_votes"),
                count(col("user_id").isNotNull()).alias("unique_voters")
            ).withColumn(
                "engagement_score",
                col("upvote_count") * 2 + col("rating_count") * 1.5 - col("downvote_count")
            )
            
            # Aggregate comment metrics
            comment_metrics = comments_df.filter(
                col("is_deleted") == False
            ).groupBy("idea_id").agg(
                count("*").alias("comment_count"),
                count(col("user_id").isNotNull()).alias("unique_commenters")
            )
            
            # Calculate time-based metrics
            ideas_with_age = ideas_df.withColumn(
                "days_since_created",
                datediff(current_date(), col("created_at"))
            ).withColumn(
                "is_recent",
                when(col("days_since_created") <= 7, lit(True)).otherwise(lit(False))
            )
            
            # Join all metrics
            idea_metrics = ideas_with_age \
                .join(vote_metrics, "idea_id", "left") \
                .join(comment_metrics, "idea_id", "left") \
                .fillna(0, subset=[
                    "upvote_count", "downvote_count", "rating_count",
                    "total_votes", "unique_voters", "comment_count",
                    "unique_commenters", "engagement_score"
                ]) \
                .fillna(0.0, subset=["avg_rating", "rating_stddev"]) \
                .withColumn(
                    "discussion_rate",
                    when(col("unique_voters") > 0, 
                         col("comment_count") / col("unique_voters")
                    ).otherwise(0)
                ) \
                .withColumn(
                    "controversy_score",
                    when(col("total_votes") > 10,
                         col("downvote_count") / col("total_votes") * col("rating_stddev")
                    ).otherwise(0)
                )
            
            return idea_metrics
            
        except Exception as e:
            logger.error(f"Error calculating idea metrics: {e}")
            raise
    
    def calculate_user_analytics(self) -> DataFrame:
        """Calculate user-level analytics."""
        try:
            ideas_df = read_from_postgres(self.spark, "ideas")
            votes_df = read_from_postgres(self.spark, "votes")
            comments_df = read_from_postgres(self.spark, "comments")
            
            # Ideas per user
            ideas_per_user = ideas_df.groupBy("user_id").agg(
                count("*").alias("ideas_created"),
                count(when(col("status") == "published", 1)).alias("ideas_published"),
                count(when(col("status") == "implemented", 1)).alias("ideas_implemented"),
                avg("vote_count").alias("avg_votes_per_idea")
            )
            
            # Voting patterns
            voting_patterns = votes_df.groupBy("user_id").agg(
                count("*").alias("total_votes_cast"),
                count(when(col("vote_type") == "upvote", 1)).alias("upvotes_given"),
                count(when(col("vote_type") == "downvote", 1)).alias("downvotes_given"),
                count(when(col("vote_type") == "rating", 1)).alias("ratings_given"),
                avg(when(col("vote_type") == "rating", col("rating"))).alias("avg_rating_given")
            ).withColumn(
                "positivity_ratio",
                when(col("downvotes_given") > 0,
                     col("upvotes_given") / col("downvotes_given")
                ).otherwise(col("upvotes_given"))
            )
            
            # Comment activity
            comment_activity = comments_df.filter(
                col("is_deleted") == False
            ).groupBy("user_id").agg(
                count("*").alias("comments_made"),
                count(col("idea_id").isNotNull()).alias("unique_ideas_commented")
            )
            
            # Combine user metrics
            user_analytics = ideas_per_user \
                .join(voting_patterns, "user_id", "full") \
                .join(comment_activity, "user_id", "full") \
                .fillna(0) \
                .withColumn(
                    "engagement_level",
                    when(
                        (col("ideas_created") + col("total_votes_cast") + col("comments_made")) > 50,
                        lit("high")
                    ).when(
                        (col("ideas_created") + col("total_votes_cast") + col("comments_made")) > 10,
                        lit("medium")
                    ).otherwise(lit("low"))
                ) \
                .withColumn(
                    "user_score",
                    col("ideas_created") * 10 + 
                    col("ideas_implemented") * 50 +
                    col("total_votes_cast") * 1 +
                    col("comments_made") * 2
                )
            
            return user_analytics
            
        except Exception as e:
            logger.error(f"Error calculating user analytics: {e}")
            raise
    
    def identify_top_performers(self, metric: str = "user_score", top_n: int = 100) -> DataFrame:
        """Identify top performing users based on various metrics."""
        user_analytics = self.calculate_user_analytics()
        
        window_spec = Window.orderBy(col(metric).desc())
        
        return user_analytics \
            .withColumn("rank", row_number().over(window_spec)) \
            .filter(col("rank") <= top_n) \
            .select(
                "user_id", "rank", metric,
                "ideas_created", "ideas_implemented",
                "total_votes_cast", "comments_made",
                "engagement_level"
            )
    
    def calculate_category_insights(self) -> DataFrame:
        """Calculate insights by idea category."""
        try:
            idea_metrics = self.calculate_idea_metrics()
            
            category_insights = idea_metrics.groupBy("category").agg(
                count("*").alias("total_ideas"),
                avg("upvote_count").alias("avg_upvotes"),
                avg("downvote_count").alias("avg_downvotes"),
                avg("avg_rating").alias("overall_avg_rating"),
                avg("engagement_score").alias("avg_engagement_score"),
                avg("comment_count").alias("avg_comments"),
                count(when(col("status") == "implemented", 1)).alias("implemented_count"),
                count(when(col("is_recent"), 1)).alias("recent_ideas")
            ).withColumn(
                "implementation_rate",
                col("implemented_count") / col("total_ideas")
            ).withColumn(
                "category_rank",
                dense_rank().over(Window.orderBy(col("avg_engagement_score").desc()))
            )
            
            return category_insights
            
        except Exception as e:
            logger.error(f"Error calculating category insights: {e}")
            raise
    
    def generate_weekly_report(self) -> Dict[str, DataFrame]:
        """Generate comprehensive weekly analytics report."""
        try:
            # This week vs last week comparison
            current_week_start = date_sub(current_date(), 7)
            last_week_start = date_sub(current_date(), 14)
            
            ideas_df = read_from_postgres(self.spark, "ideas")
            
            # Weekly idea creation trend
            weekly_ideas = ideas_df.filter(
                col("created_at") >= last_week_start
            ).withColumn(
                "week",
                when(col("created_at") >= current_week_start, "current").otherwise("previous")
            ).groupBy("week").agg(
                count("*").alias("ideas_created"),
                count(when(col("status") == "published", 1)).alias("ideas_published")
            )
            
            # Top ideas of the week
            idea_metrics = self.calculate_idea_metrics(lookback_days=7)
            top_ideas = idea_metrics.orderBy(
                col("engagement_score").desc()
            ).limit(10).select(
                "idea_id", "title", "category", "user_name",
                "upvote_count", "downvote_count", "avg_rating",
                "comment_count", "engagement_score"
            )
            
            # Active users this week
            user_analytics = self.calculate_user_analytics()
            active_users = user_analytics.filter(
                (col("ideas_created") > 0) | 
                (col("total_votes_cast") > 0) | 
                (col("comments_made") > 0)
            ).count()
            
            # Category performance
            category_insights = self.calculate_category_insights()
            
            return {
                "weekly_trend": weekly_ideas,
                "top_ideas": top_ideas,
                "active_users_count": active_users,
                "category_insights": category_insights
            }
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
            raise
    
    def run_all_batch_jobs(self):
        """Run all batch analytics jobs."""
        try:
            logger.info("Starting batch analytics jobs...")
            
            # 1. Calculate and save idea metrics
            idea_metrics = self.calculate_idea_metrics()
            write_to_postgres(idea_metrics, "idea_metrics_batch", mode="overwrite")
            logger.info("Saved idea metrics")
            
            # 2. Calculate and save user analytics
            user_analytics = self.calculate_user_analytics()
            write_to_postgres(user_analytics, "user_analytics_batch", mode="overwrite")
            logger.info("Saved user analytics")
            
            # 3. Identify and save top performers
            top_performers = self.identify_top_performers()
            write_to_postgres(top_performers, "top_performers_batch", mode="overwrite")
            logger.info("Saved top performers")
            
            # 4. Calculate and save category insights
            category_insights = self.calculate_category_insights()
            write_to_postgres(category_insights, "category_insights_batch", mode="overwrite")
            logger.info("Saved category insights")
            
            logger.info("Completed all batch analytics jobs successfully")
            
        except Exception as e:
            logger.error(f"Error running batch jobs: {e}")
            raise


# Utility function to schedule batch jobs
def run_scheduled_batch_job():
    """Run scheduled batch analytics job."""
    processor = AnalyticsBatchProcessor()
    processor.run_all_batch_jobs()
    
    # Stop Spark session after batch job
    from .spark_session import stop_spark_session
    stop_spark_session()


if __name__ == "__main__":
    run_scheduled_batch_job()