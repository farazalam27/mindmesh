"""
PySpark batch processing jobs for MindMesh analytics.
Processes idea submissions, votes, and generates insights.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, count, sum as spark_sum, avg, stddev, max as spark_max,
    min as spark_min, when, desc, asc, window, to_timestamp,
    collect_list, struct, explode, split, regexp_replace,
    lower, trim, size, array_contains, udf
)
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType, ArrayType, DoubleType
from pyspark.ml.feature import VectorAssembler, StandardScaler, Tokenizer, StopWordsRemover
from pyspark.ml.clustering import KMeans
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import ClusteringEvaluator, BinaryClassificationEvaluator

logger = logging.getLogger(__name__)


class MindMeshSparkJobs:
    """PySpark batch processing jobs for MindMesh analytics."""
    
    def __init__(self, spark_session: SparkSession):
        self.spark = spark_session
        self.postgres_url = "jdbc:postgresql://postgres:5432/mindmesh"
        self.postgres_properties = {
            "user": "mindmesh_user",
            "password": "mindmesh_password",
            "driver": "org.postgresql.Driver"
        }
    
    def run_daily_analytics(self) -> Dict[str, Any]:
        """Run daily analytics batch job."""
        logger.info("Starting daily analytics batch job")
        
        results = {}
        
        # Load data
        ideas_df = self._load_ideas_data()
        votes_df = self._load_votes_data()
        
        # Generate analytics
        results['voting_trends'] = self._analyze_voting_trends(votes_df)
        results['idea_performance'] = self._analyze_idea_performance(ideas_df, votes_df)
        results['user_engagement'] = self._analyze_user_engagement(ideas_df, votes_df)
        results['topic_clustering'] = self._perform_topic_clustering(ideas_df)
        results['success_prediction'] = self._predict_idea_success(ideas_df, votes_df)
        
        # Save results
        self._save_analytics_results(results)
        
        logger.info("Daily analytics batch job completed")
        return results
    
    def _load_ideas_data(self) -> DataFrame:
        """Load ideas data from PostgreSQL."""
        return self.spark.read.jdbc(
            url=self.postgres_url,
            table="ideas",
            properties=self.postgres_properties
        )
    
    def _load_votes_data(self) -> DataFrame:
        """Load votes data from PostgreSQL."""
        return self.spark.read.jdbc(
            url=self.postgres_url,
            table="votes",
            properties=self.postgres_properties
        )
    
    def _analyze_voting_trends(self, votes_df: DataFrame) -> Dict[str, Any]:
        """Analyze voting patterns and trends."""
        logger.info("Analyzing voting trends")
        
        # Convert timestamp
        votes_df = votes_df.withColumn("vote_timestamp", to_timestamp(col("created_at")))
        
        # Daily voting trends
        daily_trends = votes_df.groupBy(
            window(col("vote_timestamp"), "1 day")
        ).agg(
            count("*").alias("total_votes"),
            spark_sum(when(col("vote_type") == "upvote", 1).otherwise(0)).alias("upvotes"),
            spark_sum(when(col("vote_type") == "downvote", 1).otherwise(0)).alias("downvotes")
        ).orderBy("window")
        
        # Peak voting hours
        hourly_trends = votes_df.groupBy(
            window(col("vote_timestamp"), "1 hour")
        ).agg(
            count("*").alias("votes_count")
        ).orderBy(desc("votes_count"))
        
        # Vote velocity (votes per minute for trending ideas)
        vote_velocity = votes_df.filter(
            col("vote_timestamp") > (datetime.now() - timedelta(hours=24))
        ).groupBy("idea_id").agg(
            count("*").alias("recent_votes"),
            ((count("*") / 1440.0)).alias("votes_per_minute")  # 24 hours = 1440 minutes
        ).orderBy(desc("votes_per_minute"))
        
        return {
            "daily_trends": daily_trends.collect(),
            "peak_hours": hourly_trends.limit(5).collect(),
            "trending_ideas": vote_velocity.limit(10).collect()
        }
    
    def _analyze_idea_performance(self, ideas_df: DataFrame, votes_df: DataFrame) -> Dict[str, Any]:
        """Analyze idea performance metrics."""
        logger.info("Analyzing idea performance")
        
        # Join ideas with vote aggregations
        vote_stats = votes_df.groupBy("idea_id").agg(
            count("*").alias("total_votes"),
            spark_sum(when(col("vote_type") == "upvote", 1).otherwise(0)).alias("upvotes"),
            spark_sum(when(col("vote_type") == "downvote", 1).otherwise(0)).alias("downvotes")
        )
        
        performance_df = ideas_df.join(vote_stats, ideas_df.id == vote_stats.idea_id, "left").fillna(0)
        
        # Calculate performance metrics
        performance_df = performance_df.withColumn(
            "upvote_ratio", 
            when(col("total_votes") > 0, col("upvotes") / col("total_votes")).otherwise(0)
        ).withColumn(
            "net_score", 
            col("upvotes") - col("downvotes")
        ).withColumn(
            "engagement_score",
            col("total_votes") + col("comment_count") * 2
        )
        
        # Top performing ideas
        top_ideas = performance_df.orderBy(desc("engagement_score")).limit(20)
        
        # Performance by category
        category_performance = performance_df.groupBy("category").agg(
            avg("upvote_ratio").alias("avg_upvote_ratio"),
            avg("engagement_score").alias("avg_engagement"),
            count("*").alias("idea_count")
        ).orderBy(desc("avg_engagement"))
        
        return {
            "top_ideas": top_ideas.collect(),
            "category_performance": category_performance.collect(),
            "overall_stats": performance_df.agg(
                avg("upvote_ratio").alias("avg_upvote_ratio"),
                avg("engagement_score").alias("avg_engagement")
            ).collect()[0].asDict()
        }
    
    def _analyze_user_engagement(self, ideas_df: DataFrame, votes_df: DataFrame) -> Dict[str, Any]:
        """Analyze user engagement patterns."""
        logger.info("Analyzing user engagement")
        
        # User idea creation stats
        user_ideas = ideas_df.groupBy("created_by").agg(
            count("*").alias("ideas_created"),
            avg("comment_count").alias("avg_comments_received")
        )
        
        # User voting stats
        user_votes = votes_df.groupBy("user_id").agg(
            count("*").alias("votes_cast"),
            spark_sum(when(col("vote_type") == "upvote", 1).otherwise(0)).alias("upvotes_given"),
            spark_sum(when(col("vote_type") == "downvote", 1).otherwise(0)).alias("downvotes_given")
        )
        
        # Most active users
        active_users = user_ideas.join(user_votes, user_ideas.created_by == user_votes.user_id, "outer")\
            .fillna(0)\
            .withColumn("engagement_score", col("ideas_created") * 5 + col("votes_cast"))\
            .orderBy(desc("engagement_score"))
        
        # User cohort analysis (new vs returning)
        user_first_activity = ideas_df.groupBy("created_by").agg(
            spark_min("created_at").alias("first_idea")
        )
        
        return {
            "most_active_users": active_users.limit(20).collect(),
            "engagement_distribution": user_ideas.describe().collect(),
            "voting_patterns": user_votes.describe().collect()
        }
    
    def _perform_topic_clustering(self, ideas_df: DataFrame) -> Dict[str, Any]:
        """Perform ML-based topic clustering on ideas."""
        logger.info("Performing topic clustering")
        
        # Prepare text data
        text_df = ideas_df.select("id", "title", "description").withColumn(
            "combined_text", 
            lower(trim(regexp_replace(col("title") + " " + col("description"), "[^a-zA-Z\\s]", "")))
        )
        
        # Tokenization and stop word removal
        tokenizer = Tokenizer(inputCol="combined_text", outputCol="words")
        tokenized_df = tokenizer.transform(text_df)
        
        remover = StopWordsRemover(inputCol="words", outputCol="filtered_words")
        filtered_df = remover.transform(tokenized_df)
        
        # Simple word count vectorization (in production, use TF-IDF or Word2Vec)
        from pyspark.ml.feature import CountVectorizer
        cv = CountVectorizer(inputCol="filtered_words", outputCol="features", minDF=2.0, vocabSize=1000)
        cv_model = cv.fit(filtered_df)
        vectorized_df = cv_model.transform(filtered_df)
        
        # K-means clustering
        kmeans = KMeans(k=8, seed=42, featuresCol="features", predictionCol="cluster")
        model = kmeans.fit(vectorized_df)
        clustered_df = model.transform(vectorized_df)
        
        # Analyze clusters
        cluster_stats = clustered_df.groupBy("cluster").agg(
            count("*").alias("idea_count"),
            collect_list("title").alias("sample_titles")
        )
        
        # Get top words for each cluster
        vocabulary = cv_model.vocabulary
        centers = model.clusterCenters()
        
        cluster_topics = []
        for i, center in enumerate(centers):
            top_indices = center.argsort()[-10:][::-1]  # Top 10 words
            top_words = [vocabulary[idx] for idx in top_indices if idx < len(vocabulary)]
            cluster_topics.append({
                "cluster_id": i,
                "top_words": top_words,
                "center_values": [float(center[idx]) for idx in top_indices]
            })
        
        return {
            "cluster_stats": cluster_stats.collect(),
            "cluster_topics": cluster_topics,
            "silhouette_score": ClusteringEvaluator().evaluate(clustered_df)
        }
    
    def _predict_idea_success(self, ideas_df: DataFrame, votes_df: DataFrame) -> Dict[str, Any]:
        """Train model to predict idea success."""
        logger.info("Training idea success prediction model")
        
        # Prepare training data
        vote_stats = votes_df.groupBy("idea_id").agg(
            count("*").alias("total_votes"),
            spark_sum(when(col("vote_type") == "upvote", 1).otherwise(0)).alias("upvotes")
        )
        
        # Define success criteria (e.g., >10 upvotes and >70% upvote ratio)
        success_df = ideas_df.join(vote_stats, ideas_df.id == vote_stats.idea_id, "left")\
            .fillna(0)\
            .withColumn("upvote_ratio", 
                       when(col("total_votes") > 0, col("upvotes") / col("total_votes")).otherwise(0))\
            .withColumn("is_successful", 
                       when((col("upvotes") >= 10) & (col("upvote_ratio") >= 0.7), 1.0).otherwise(0.0))
        
        # Feature engineering
        feature_df = success_df.withColumn("title_length", size(split(col("title"), "\\s+")))\
            .withColumn("description_length", size(split(col("description"), "\\s+")))\
            .withColumn("has_question_mark", when(col("title").contains("?"), 1.0).otherwise(0.0))\
            .withColumn("hour_created", 
                       col("created_at").cast("timestamp").cast("long") % 86400 / 3600)
        
        # Vector assembly
        feature_cols = ["title_length", "description_length", "has_question_mark", "hour_created"]
        assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
        feature_vector_df = assembler.transform(feature_df)
        
        # Split data
        train_df, test_df = feature_vector_df.randomSplit([0.8, 0.2], seed=42)
        
        # Train Random Forest model
        rf = RandomForestClassifier(featuresCol="features", labelCol="is_successful", seed=42)
        rf_model = rf.fit(train_df)
        
        # Evaluate model
        predictions = rf_model.transform(test_df)
        evaluator = BinaryClassificationEvaluator(labelCol="is_successful", metricName="areaUnderROC")
        auc = evaluator.evaluate(predictions)
        
        # Feature importance
        feature_importance = list(zip(feature_cols, rf_model.featureImportances.toArray()))
        
        return {
            "model_auc": float(auc),
            "feature_importance": feature_importance,
            "prediction_samples": predictions.select("title", "is_successful", "prediction", "probability").limit(10).collect()
        }
    
    def _save_analytics_results(self, results: Dict[str, Any]) -> None:
        """Save analytics results to PostgreSQL."""
        logger.info("Saving analytics results")
        
        # Convert results to DataFrame and save
        analytics_summary = self.spark.createDataFrame([{
            "run_date": datetime.now(),
            "job_type": "daily_analytics",
            "results_json": str(results),  # In production, use proper JSON serialization
            "status": "completed"
        }])
        
        analytics_summary.write.jdbc(
            url=self.postgres_url,
            table="analytics_runs",
            mode="append",
            properties=self.postgres_properties
        )