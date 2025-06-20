"""Machine Learning models for idea clustering and analysis using MLlib."""
from pyspark.sql import SparkSession, DataFrame
from pyspark.ml import Pipeline
from pyspark.ml.feature import (
    Tokenizer, StopWordsRemover, CountVectorizer,
    IDF, Word2Vec, StandardScaler, VectorAssembler,
    StringIndexer, OneHotEncoder
)
from pyspark.ml.clustering import KMeans, BisectingKMeans, LDA
from pyspark.ml.classification import RandomForestClassifier, LogisticRegression
from pyspark.ml.evaluation import MulticlassClassificationEvaluator, ClusteringEvaluator
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.sql.functions import (
    col, concat_ws, array, udf, explode,
    collect_list, size, mean, stddev
)
from pyspark.sql.types import ArrayType, StringType, FloatType
import logging
import os
from typing import Optional, List, Dict, Any
import numpy as np
from .spark_session import get_spark_session, read_from_postgres

logger = logging.getLogger(__name__)


class IdeaClusteringModel:
    """ML model for clustering similar ideas."""
    
    def __init__(self, spark: Optional[SparkSession] = None):
        self.spark = spark or get_spark_session()
        self.model_path = os.getenv("ML_MODEL_PATH", "/tmp/ml-models")
        
    def prepare_text_features(self, df: DataFrame) -> DataFrame:
        """
        Prepare text features for clustering.
        
        Args:
            df: DataFrame with idea text data
            
        Returns:
            DataFrame with text features
        """
        # Combine title and description
        df_with_text = df.withColumn(
            "combined_text",
            concat_ws(" ", col("title"), col("description"))
        )
        
        # Text processing pipeline
        tokenizer = Tokenizer(inputCol="combined_text", outputCol="words")
        remover = StopWordsRemover(inputCol="words", outputCol="filtered_words")
        
        # TF-IDF features
        cv = CountVectorizer(
            inputCol="filtered_words",
            outputCol="raw_features",
            vocabSize=5000,
            minDF=2.0
        )
        idf = IDF(inputCol="raw_features", outputCol="tfidf_features")
        
        # Word2Vec features
        word2vec = Word2Vec(
            vectorSize=100,
            minCount=1,
            inputCol="filtered_words",
            outputCol="word2vec_features"
        )
        
        # Build pipeline
        pipeline = Pipeline(stages=[tokenizer, remover, cv, idf, word2vec])
        
        # Fit and transform
        model = pipeline.fit(df_with_text)
        return model.transform(df_with_text)
    
    def prepare_numerical_features(self, df: DataFrame) -> DataFrame:
        """
        Prepare numerical features for clustering.
        
        Args:
            df: DataFrame with idea metrics
            
        Returns:
            DataFrame with numerical features
        """
        # Select numerical features
        numerical_cols = [
            "vote_count", "average_rating", "view_count",
            "days_since_created", "comment_count"
        ]
        
        # Assemble features
        assembler = VectorAssembler(
            inputCols=numerical_cols,
            outputCol="numerical_features"
        )
        
        # Scale features
        scaler = StandardScaler(
            inputCol="numerical_features",
            outputCol="scaled_numerical_features"
        )
        
        # Build pipeline
        pipeline = Pipeline(stages=[assembler, scaler])
        
        # Fit and transform
        model = pipeline.fit(df)
        return model.transform(df)
    
    def cluster_ideas(self, df: DataFrame, n_clusters: int = 10) -> DataFrame:
        """
        Cluster ideas using K-means.
        
        Args:
            df: DataFrame with ideas
            n_clusters: Number of clusters
            
        Returns:
            DataFrame with cluster assignments
        """
        try:
            # Prepare features
            df_with_text = self.prepare_text_features(df)
            df_with_features = self.prepare_numerical_features(df_with_text)
            
            # Combine all features
            feature_assembler = VectorAssembler(
                inputCols=["tfidf_features", "word2vec_features", "scaled_numerical_features"],
                outputCol="features"
            )
            
            df_final = feature_assembler.transform(df_with_features)
            
            # K-means clustering
            kmeans = KMeans(
                k=n_clusters,
                seed=42,
                featuresCol="features",
                predictionCol="cluster_id"
            )
            
            # Train model
            kmeans_model = kmeans.fit(df_final)
            
            # Make predictions
            clustered_df = kmeans_model.transform(df_final)
            
            # Evaluate clustering
            evaluator = ClusteringEvaluator(
                predictionCol="cluster_id",
                featuresCol="features",
                metricName="silhouette"
            )
            silhouette = evaluator.evaluate(clustered_df)
            logger.info(f"Clustering silhouette score: {silhouette}")
            
            # Save model
            kmeans_model.write().overwrite().save(f"{self.model_path}/kmeans_idea_clustering")
            
            return clustered_df.select(
                "idea_id", "title", "category", "cluster_id",
                "vote_count", "average_rating"
            )
            
        except Exception as e:
            logger.error(f"Error clustering ideas: {e}")
            raise
    
    def topic_modeling(self, df: DataFrame, n_topics: int = 10) -> DataFrame:
        """
        Perform topic modeling using LDA.
        
        Args:
            df: DataFrame with ideas
            n_topics: Number of topics
            
        Returns:
            DataFrame with topic assignments
        """
        try:
            # Prepare text features
            df_with_text = df.withColumn(
                "combined_text",
                concat_ws(" ", col("title"), col("description"))
            )
            
            # Text processing
            tokenizer = Tokenizer(inputCol="combined_text", outputCol="words")
            remover = StopWordsRemover(inputCol="words", outputCol="filtered_words")
            cv = CountVectorizer(
                inputCol="filtered_words",
                outputCol="features",
                vocabSize=5000,
                minDF=2.0
            )
            
            # Build pipeline
            pipeline = Pipeline(stages=[tokenizer, remover, cv])
            model = pipeline.fit(df_with_text)
            df_features = model.transform(df_with_text)
            
            # LDA model
            lda = LDA(k=n_topics, seed=42, maxIter=20)
            lda_model = lda.fit(df_features)
            
            # Transform data
            df_topics = lda_model.transform(df_features)
            
            # Get topic distribution
            df_with_topics = df_topics.select(
                "idea_id", "title", "topicDistribution"
            )
            
            # Save model
            lda_model.write().overwrite().save(f"{self.model_path}/lda_topic_model")
            
            # Log topics
            topics = lda_model.describeTopics(maxTermsPerTopic=10)
            logger.info(f"Discovered {n_topics} topics")
            
            return df_with_topics
            
        except Exception as e:
            logger.error(f"Error in topic modeling: {e}")
            raise


class IdeaSuccessPredictionModel:
    """ML model for predicting idea success."""
    
    def __init__(self, spark: Optional[SparkSession] = None):
        self.spark = spark or get_spark_session()
        self.model_path = os.getenv("ML_MODEL_PATH", "/tmp/ml-models")
    
    def prepare_features(self, df: DataFrame) -> DataFrame:
        """Prepare features for success prediction."""
        # Define success metric (e.g., implemented ideas or high engagement)
        df_labeled = df.withColumn(
            "is_successful",
            when(
                (col("status") == "implemented") | 
                (col("engagement_score") > df.agg(mean("engagement_score")).first()[0] * 2),
                1
            ).otherwise(0)
        )
        
        # Category encoding
        category_indexer = StringIndexer(
            inputCol="category",
            outputCol="category_index"
        )
        category_encoder = OneHotEncoder(
            inputCol="category_index",
            outputCol="category_encoded"
        )
        
        # Text length features
        df_with_lengths = df_labeled.withColumn(
            "title_length",
            size(split(col("title"), " "))
        ).withColumn(
            "description_length",
            size(split(col("description"), " "))
        )
        
        # Feature assembly
        feature_cols = [
            "days_since_created", "title_length", "description_length",
            "category_encoded"
        ]
        
        assembler = VectorAssembler(
            inputCols=feature_cols,
            outputCol="features"
        )
        
        # Build pipeline
        pipeline = Pipeline(stages=[
            category_indexer, category_encoder, assembler
        ])
        
        # Fit and transform
        model = pipeline.fit(df_with_lengths)
        return model.transform(df_with_lengths)
    
    def train_prediction_model(self, df: DataFrame) -> Any:
        """Train model to predict idea success."""
        try:
            # Prepare features
            df_features = self.prepare_features(df)
            
            # Split data
            train_data, test_data = df_features.randomSplit([0.8, 0.2], seed=42)
            
            # Random Forest Classifier
            rf = RandomForestClassifier(
                labelCol="is_successful",
                featuresCol="features",
                numTrees=100
            )
            
            # Train model
            rf_model = rf.fit(train_data)
            
            # Make predictions
            predictions = rf_model.transform(test_data)
            
            # Evaluate model
            evaluator = MulticlassClassificationEvaluator(
                labelCol="is_successful",
                predictionCol="prediction",
                metricName="accuracy"
            )
            accuracy = evaluator.evaluate(predictions)
            logger.info(f"Model accuracy: {accuracy}")
            
            # Feature importance
            feature_importance = rf_model.featureImportances
            logger.info(f"Feature importances: {feature_importance}")
            
            # Save model
            rf_model.write().overwrite().save(f"{self.model_path}/idea_success_predictor")
            
            return rf_model
            
        except Exception as e:
            logger.error(f"Error training prediction model: {e}")
            raise
    
    def predict_idea_success(self, df: DataFrame, model_path: str = None) -> DataFrame:
        """Predict success probability for new ideas."""
        try:
            # Load model
            if model_path is None:
                model_path = f"{self.model_path}/idea_success_predictor"
            
            from pyspark.ml.classification import RandomForestClassificationModel
            model = RandomForestClassificationModel.load(model_path)
            
            # Prepare features
            df_features = self.prepare_features(df)
            
            # Make predictions
            predictions = model.transform(df_features)
            
            # Extract probability of success
            extract_prob = udf(lambda prob: float(prob[1]), FloatType())
            
            result = predictions.select(
                "idea_id", "title", "category",
                extract_prob("probability").alias("success_probability"),
                "prediction"
            ).withColumn(
                "success_likelihood",
                when(col("success_probability") > 0.7, "High")
                .when(col("success_probability") > 0.4, "Medium")
                .otherwise("Low")
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error predicting idea success: {e}")
            raise


class MLPipeline:
    """Complete ML pipeline for idea analysis."""
    
    def __init__(self, spark: Optional[SparkSession] = None):
        self.spark = spark or get_spark_session()
        self.clustering_model = IdeaClusteringModel(spark)
        self.prediction_model = IdeaSuccessPredictionModel(spark)
    
    def run_complete_pipeline(self):
        """Run complete ML pipeline."""
        try:
            logger.info("Starting ML pipeline...")
            
            # Load data
            ideas_df = read_from_postgres(self.spark, "ideas")
            idea_metrics_df = read_from_postgres(self.spark, "idea_metrics_batch")
            
            # Join data
            df = ideas_df.join(idea_metrics_df, "idea_id", "left")
            
            # 1. Cluster ideas
            clustered_ideas = self.clustering_model.cluster_ideas(df)
            write_to_postgres(clustered_ideas, "idea_clusters", mode="overwrite")
            logger.info("Completed idea clustering")
            
            # 2. Topic modeling
            topics = self.clustering_model.topic_modeling(df)
            write_to_postgres(topics, "idea_topics", mode="overwrite")
            logger.info("Completed topic modeling")
            
            # 3. Train success prediction model
            self.prediction_model.train_prediction_model(df)
            logger.info("Trained success prediction model")
            
            # 4. Predict success for recent ideas
            recent_ideas = df.filter(col("days_since_created") <= 7)
            if recent_ideas.count() > 0:
                predictions = self.prediction_model.predict_idea_success(recent_ideas)
                write_to_postgres(predictions, "idea_success_predictions", mode="overwrite")
                logger.info("Completed success predictions")
            
            logger.info("ML pipeline completed successfully")
            
        except Exception as e:
            logger.error(f"Error in ML pipeline: {e}")
            raise


if __name__ == "__main__":
    pipeline = MLPipeline()
    pipeline.run_complete_pipeline()
    
    # Stop Spark session
    from .spark_session import stop_spark_session
    stop_spark_session()