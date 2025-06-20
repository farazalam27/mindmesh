"""Unit tests for Analytics service."""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock, call
import json

# Mock PySpark imports since they might not be available in test environment
try:
    from pyspark.sql import SparkSession, DataFrame as SparkDataFrame
    from pyspark.ml.clustering import KMeans, KMeansModel
    from pyspark.ml.classification import RandomForestClassifier, RandomForestClassificationModel
    from pyspark.ml.feature import VectorAssembler
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False
    # Create mock classes
    SparkSession = Mock
    SparkDataFrame = Mock
    KMeans = Mock
    KMeansModel = Mock
    RandomForestClassifier = Mock
    RandomForestClassificationModel = Mock
    VectorAssembler = Mock

# Import your actual modules
from services.analytics.ml_models import (
    IdeaClusteringModel, IdeaSuccessPredictionModel, MLPipeline
)
from services.analytics.spark_session import get_spark_session


class TestSparkSession:
    """Test cases for Spark session management."""
    
    @patch('services.analytics.spark_session.SparkSession')
    def test_get_spark_session(self, mock_spark_session):
        """Test Spark session creation."""
        mock_session = Mock()
        mock_spark_session.builder.appName.return_value.config.return_value.getOrCreate.return_value = mock_session
        
        session = get_spark_session()
        
        assert session is not None
        mock_spark_session.builder.appName.assert_called_once()
    
    @patch('services.analytics.spark_session.SparkSession')
    def test_spark_session_configuration(self, mock_spark_session):
        """Test Spark session configuration."""
        mock_builder = Mock()
        mock_spark_session.builder = mock_builder
        mock_builder.appName.return_value = mock_builder
        mock_builder.config.return_value = mock_builder
        mock_builder.getOrCreate.return_value = Mock()
        
        get_spark_session()
        
        # Verify configuration calls
        mock_builder.appName.assert_called_with("MindMesh Analytics")
        mock_builder.config.assert_called()


class TestIdeaClusteringModel:
    """Test cases for IdeaClusteringModel."""
    
    @pytest.fixture
    def mock_spark(self):
        """Mock Spark session."""
        return Mock(spec=SparkSession)
    
    @pytest.fixture
    def clustering_model(self, mock_spark):
        """Create clustering model with mocked Spark."""
        return IdeaClusteringModel(spark=mock_spark)
    
    @pytest.fixture
    def mock_dataframe(self):
        """Mock Spark DataFrame."""
        df = Mock(spec=SparkDataFrame)
        df.withColumn.return_value = df
        df.select.return_value = df
        return df
    
    def test_clustering_model_initialization(self, mock_spark):
        """Test clustering model initialization."""
        model = IdeaClusteringModel(spark=mock_spark)
        
        assert model.spark == mock_spark
        assert "/tmp/ml-models" in model.model_path
    
    def test_prepare_text_features(self, clustering_model, mock_dataframe):
        """Test text feature preparation."""
        # Mock pipeline stages
        with patch('services.analytics.ml_models.Tokenizer') as mock_tokenizer, \
             patch('services.analytics.ml_models.StopWordsRemover') as mock_remover, \
             patch('services.analytics.ml_models.CountVectorizer') as mock_cv, \
             patch('services.analytics.ml_models.IDF') as mock_idf, \
             patch('services.analytics.ml_models.Word2Vec') as mock_word2vec, \
             patch('services.analytics.ml_models.Pipeline') as mock_pipeline:
            
            # Mock pipeline
            mock_pipeline_instance = Mock()
            mock_pipeline.return_value = mock_pipeline_instance
            mock_pipeline_instance.fit.return_value.transform.return_value = mock_dataframe
            
            result = clustering_model.prepare_text_features(mock_dataframe)
            
            # Verify pipeline stages were created
            mock_tokenizer.assert_called_once()
            mock_remover.assert_called_once()
            mock_cv.assert_called_once()
            mock_idf.assert_called_once()
            mock_word2vec.assert_called_once()
            mock_pipeline.assert_called_once()
            
            assert result == mock_dataframe
    
    def test_prepare_numerical_features(self, clustering_model, mock_dataframe):
        """Test numerical feature preparation."""
        with patch('services.analytics.ml_models.VectorAssembler') as mock_assembler, \
             patch('services.analytics.ml_models.StandardScaler') as mock_scaler, \
             patch('services.analytics.ml_models.Pipeline') as mock_pipeline:
            
            # Mock pipeline
            mock_pipeline_instance = Mock()
            mock_pipeline.return_value = mock_pipeline_instance
            mock_pipeline_instance.fit.return_value.transform.return_value = mock_dataframe
            
            result = clustering_model.prepare_numerical_features(mock_dataframe)
            
            # Verify feature assembly and scaling
            mock_assembler.assert_called_once()
            mock_scaler.assert_called_once()
            mock_pipeline.assert_called_once()
            
            assert result == mock_dataframe
    
    def test_cluster_ideas(self, clustering_model, mock_dataframe):
        """Test idea clustering."""
        with patch.object(clustering_model, 'prepare_text_features') as mock_text_prep, \
             patch.object(clustering_model, 'prepare_numerical_features') as mock_num_prep, \
             patch('services.analytics.ml_models.VectorAssembler') as mock_assembler, \
             patch('services.analytics.ml_models.KMeans') as mock_kmeans, \
             patch('services.analytics.ml_models.ClusteringEvaluator') as mock_evaluator:
            
            # Setup mocks
            mock_text_prep.return_value = mock_dataframe
            mock_num_prep.return_value = mock_dataframe
            
            mock_assembler_instance = Mock()
            mock_assembler.return_value = mock_assembler_instance
            mock_assembler_instance.transform.return_value = mock_dataframe
            
            mock_kmeans_instance = Mock()
            mock_kmeans.return_value = mock_kmeans_instance
            mock_kmeans_model = Mock()
            mock_kmeans_instance.fit.return_value = mock_kmeans_model
            mock_kmeans_model.transform.return_value = mock_dataframe
            
            mock_evaluator_instance = Mock()
            mock_evaluator.return_value = mock_evaluator_instance
            mock_evaluator_instance.evaluate.return_value = 0.75  # Good silhouette score
            
            result = clustering_model.cluster_ideas(mock_dataframe, n_clusters=5)
            
            # Verify clustering process
            mock_text_prep.assert_called_once_with(mock_dataframe)
            mock_num_prep.assert_called_once()
            mock_kmeans.assert_called_once()
            mock_evaluator.assert_called_once()
            
            assert result == mock_dataframe
    
    def test_topic_modeling(self, clustering_model, mock_dataframe):
        """Test topic modeling with LDA."""
        with patch('services.analytics.ml_models.Tokenizer') as mock_tokenizer, \
             patch('services.analytics.ml_models.StopWordsRemover') as mock_remover, \
             patch('services.analytics.ml_models.CountVectorizer') as mock_cv, \
             patch('services.analytics.ml_models.Pipeline') as mock_pipeline, \
             patch('services.analytics.ml_models.LDA') as mock_lda:
            
            # Mock pipeline
            mock_pipeline_instance = Mock()
            mock_pipeline.return_value = mock_pipeline_instance
            mock_pipeline_instance.fit.return_value.transform.return_value = mock_dataframe
            
            # Mock LDA
            mock_lda_instance = Mock()
            mock_lda.return_value = mock_lda_instance
            mock_lda_model = Mock()
            mock_lda_instance.fit.return_value = mock_lda_model
            mock_lda_model.transform.return_value = mock_dataframe
            mock_lda_model.describeTopics.return_value = Mock()
            
            result = clustering_model.topic_modeling(mock_dataframe, n_topics=5)
            
            # Verify topic modeling process
            mock_lda.assert_called_once_with(k=5, seed=42, maxIter=20)
            mock_lda_model.transform.assert_called_once()
            mock_lda_model.describeTopics.assert_called_once()
            
            assert result == mock_dataframe


class TestIdeaSuccessPredictionModel:
    """Test cases for IdeaSuccessPredictionModel."""
    
    @pytest.fixture
    def mock_spark(self):
        """Mock Spark session."""
        return Mock(spec=SparkSession)
    
    @pytest.fixture
    def prediction_model(self, mock_spark):
        """Create prediction model with mocked Spark."""
        return IdeaSuccessPredictionModel(spark=mock_spark)
    
    @pytest.fixture
    def mock_dataframe(self):
        """Mock Spark DataFrame."""
        df = Mock(spec=SparkDataFrame)
        df.withColumn.return_value = df
        df.select.return_value = df
        df.randomSplit.return_value = [df, df]  # train, test
        return df
    
    def test_prediction_model_initialization(self, mock_spark):
        """Test prediction model initialization."""
        model = IdeaSuccessPredictionModel(spark=mock_spark)
        
        assert model.spark == mock_spark
        assert "/tmp/ml-models" in model.model_path
    
    def test_prepare_features(self, prediction_model, mock_dataframe):
        """Test feature preparation for prediction."""
        with patch('services.analytics.ml_models.StringIndexer') as mock_indexer, \
             patch('services.analytics.ml_models.OneHotEncoder') as mock_encoder, \
             patch('services.analytics.ml_models.VectorAssembler') as mock_assembler, \
             patch('services.analytics.ml_models.Pipeline') as mock_pipeline:
            
            # Mock pipeline
            mock_pipeline_instance = Mock()
            mock_pipeline.return_value = mock_pipeline_instance
            mock_pipeline_instance.fit.return_value.transform.return_value = mock_dataframe
            
            result = prediction_model.prepare_features(mock_dataframe)
            
            # Verify feature preparation
            mock_indexer.assert_called_once()
            mock_encoder.assert_called_once()
            mock_assembler.assert_called_once()
            mock_pipeline.assert_called_once()
            
            assert result == mock_dataframe
    
    def test_train_prediction_model(self, prediction_model, mock_dataframe):
        """Test training prediction model."""
        with patch.object(prediction_model, 'prepare_features') as mock_prep, \
             patch('services.analytics.ml_models.RandomForestClassifier') as mock_rf, \
             patch('services.analytics.ml_models.MulticlassClassificationEvaluator') as mock_evaluator:
            
            # Setup mocks
            mock_prep.return_value = mock_dataframe
            
            mock_rf_instance = Mock()
            mock_rf.return_value = mock_rf_instance
            mock_rf_model = Mock()
            mock_rf_instance.fit.return_value = mock_rf_model
            mock_rf_model.transform.return_value = mock_dataframe
            mock_rf_model.featureImportances = [0.3, 0.2, 0.5]
            
            mock_evaluator_instance = Mock()
            mock_evaluator.return_value = mock_evaluator_instance
            mock_evaluator_instance.evaluate.return_value = 0.85  # Good accuracy
            
            result = prediction_model.train_prediction_model(mock_dataframe)
            
            # Verify training process
            mock_prep.assert_called_once_with(mock_dataframe)
            mock_rf.assert_called_once()
            mock_rf_model.transform.assert_called_once()
            mock_evaluator.assert_called_once()
            
            assert result == mock_rf_model
    
    def test_predict_idea_success(self, prediction_model, mock_dataframe):
        """Test predicting idea success."""
        with patch.object(prediction_model, 'prepare_features') as mock_prep, \
             patch('services.analytics.ml_models.RandomForestClassificationModel') as mock_model_class:
            
            # Setup mocks
            mock_prep.return_value = mock_dataframe
            
            mock_model = Mock()
            mock_model_class.load.return_value = mock_model
            mock_model.transform.return_value = mock_dataframe
            
            result = prediction_model.predict_idea_success(mock_dataframe)
            
            # Verify prediction process
            mock_prep.assert_called_once_with(mock_dataframe)
            mock_model.transform.assert_called_once()
            
            assert result == mock_dataframe


class TestMLPipeline:
    """Test cases for complete ML Pipeline."""
    
    @pytest.fixture
    def mock_spark(self):
        """Mock Spark session."""
        return Mock(spec=SparkSession)
    
    @pytest.fixture
    def ml_pipeline(self, mock_spark):
        """Create ML pipeline with mocked Spark."""
        return MLPipeline(spark=mock_spark)
    
    @pytest.fixture
    def mock_dataframe(self):
        """Mock Spark DataFrame."""
        df = Mock(spec=SparkDataFrame)
        df.join.return_value = df
        df.filter.return_value = df
        df.count.return_value = 10
        return df
    
    def test_pipeline_initialization(self, mock_spark):
        """Test ML pipeline initialization."""
        pipeline = MLPipeline(spark=mock_spark)
        
        assert pipeline.spark == mock_spark
        assert hasattr(pipeline, 'clustering_model')
        assert hasattr(pipeline, 'prediction_model')
    
    def test_run_complete_pipeline(self, ml_pipeline, mock_dataframe):
        """Test running complete ML pipeline."""
        with patch('services.analytics.ml_models.read_from_postgres') as mock_read, \
             patch('services.analytics.ml_models.write_to_postgres') as mock_write, \
             patch.object(ml_pipeline.clustering_model, 'cluster_ideas') as mock_cluster, \
             patch.object(ml_pipeline.clustering_model, 'topic_modeling') as mock_topics, \
             patch.object(ml_pipeline.prediction_model, 'train_prediction_model') as mock_train, \
             patch.object(ml_pipeline.prediction_model, 'predict_idea_success') as mock_predict:
            
            # Setup mocks
            mock_read.return_value = mock_dataframe
            mock_cluster.return_value = mock_dataframe
            mock_topics.return_value = mock_dataframe
            mock_predict.return_value = mock_dataframe
            
            ml_pipeline.run_complete_pipeline()
            
            # Verify pipeline steps
            assert mock_read.call_count == 2  # ideas and metrics
            mock_cluster.assert_called_once()
            mock_topics.assert_called_once()
            mock_train.assert_called_once()
            mock_predict.assert_called_once()
            assert mock_write.call_count >= 3  # clusters, topics, predictions


class TestAnalyticsUtilities:
    """Test cases for analytics utility functions."""
    
    def test_engagement_score_calculation(self):
        """Test engagement score calculation."""
        def calculate_engagement_score(metrics):
            """Calculate engagement score from various metrics."""
            weights = {
                'vote_count': 0.3,
                'average_rating': 0.25,
                'view_count': 0.2,
                'comment_count': 0.15,
                'days_active': 0.1
            }
            
            # Normalize metrics (0-1 scale)
            normalized = {
                'vote_count': min(metrics.get('vote_count', 0) / 100, 1.0),
                'average_rating': metrics.get('average_rating', 0) / 5.0,
                'view_count': min(metrics.get('view_count', 0) / 1000, 1.0),
                'comment_count': min(metrics.get('comment_count', 0) / 50, 1.0),
                'days_active': min(metrics.get('days_active', 0) / 30, 1.0)
            }
            
            # Calculate weighted score
            score = sum(normalized[key] * weights[key] for key in weights)
            return score
        
        # Test with high engagement metrics
        high_metrics = {
            'vote_count': 75,
            'average_rating': 4.5,
            'view_count': 800,
            'comment_count': 25,
            'days_active': 20
        }
        
        high_score = calculate_engagement_score(high_metrics)
        assert 0.7 <= high_score <= 1.0
        
        # Test with low engagement metrics
        low_metrics = {
            'vote_count': 5,
            'average_rating': 2.0,
            'view_count': 50,
            'comment_count': 2,
            'days_active': 2
        }
        
        low_score = calculate_engagement_score(low_metrics)
        assert 0.0 <= low_score <= 0.3
        assert high_score > low_score
    
    def test_controversy_score_calculation(self):
        """Test controversy score calculation."""
        def calculate_controversy_score(upvotes, downvotes, ratings):
            """Calculate how controversial an idea is."""
            if upvotes + downvotes == 0:
                return 0.0
            
            # Vote polarization
            total_votes = upvotes + downvotes
            vote_ratio = min(upvotes, downvotes) / total_votes
            
            # Rating variance (if available)
            rating_variance = 0.0
            if ratings:
                mean_rating = sum(ratings) / len(ratings)
                rating_variance = sum((r - mean_rating) ** 2 for r in ratings) / len(ratings)
                rating_variance = min(rating_variance / 4.0, 1.0)  # Normalize
            
            # Combined controversy score
            controversy = (vote_ratio * 0.7) + (rating_variance * 0.3)
            return controversy
        
        # Test highly controversial (close vote split)
        controversial_score = calculate_controversy_score(
            upvotes=50, 
            downvotes=45, 
            ratings=[1, 2, 5, 4, 1, 5, 3, 2, 5, 1]
        )
        assert controversial_score > 0.3
        
        # Test non-controversial (clear winner)
        clear_score = calculate_controversy_score(
            upvotes=80, 
            downvotes=5, 
            ratings=[4, 4, 5, 4, 5, 4, 4, 5, 4, 5]
        )
        assert clear_score < 0.2
        assert controversial_score > clear_score
    
    def test_trend_analysis(self):
        """Test trend analysis calculations."""
        def analyze_trends(time_series_data, window_days=7):
            """Analyze trends in time series data."""
            if len(time_series_data) < 2:
                return {'trend': 'insufficient_data', 'growth_rate': 0.0}
            
            # Calculate moving averages
            recent_avg = sum(time_series_data[-window_days:]) / min(len(time_series_data), window_days)
            older_avg = sum(time_series_data[:-window_days]) / max(len(time_series_data) - window_days, 1)
            
            if older_avg == 0:
                growth_rate = 1.0 if recent_avg > 0 else 0.0
            else:
                growth_rate = (recent_avg - older_avg) / older_avg
            
            # Determine trend
            if growth_rate > 0.1:
                trend = 'rising'
            elif growth_rate < -0.1:
                trend = 'declining'
            else:
                trend = 'stable'
            
            return {
                'trend': trend,
                'growth_rate': growth_rate,
                'recent_average': recent_avg,
                'historical_average': older_avg
            }
        
        # Test rising trend
        rising_data = [10, 12, 15, 18, 22, 25, 30, 35, 40, 45, 50, 55, 60, 65]
        rising_result = analyze_trends(rising_data)
        assert rising_result['trend'] == 'rising'
        assert rising_result['growth_rate'] > 0
        
        # Test declining trend
        declining_data = [60, 58, 55, 50, 45, 40, 35, 30, 25, 20, 18, 15, 12, 10]
        declining_result = analyze_trends(declining_data)
        assert declining_result['trend'] == 'declining'
        assert declining_result['growth_rate'] < 0
        
        # Test stable trend
        stable_data = [25, 26, 24, 25, 27, 25, 26, 24, 25, 26, 25, 24, 26, 25]
        stable_result = analyze_trends(stable_data)
        assert stable_result['trend'] == 'stable'
        assert abs(stable_result['growth_rate']) < 0.1


class TestAnalyticsPerformance:
    """Test cases for analytics performance and optimization."""
    
    def test_batch_processing_optimization(self):
        """Test batch processing optimization."""
        def process_ideas_in_batches(ideas, batch_size=100):
            """Process ideas in batches for better performance."""
            results = []
            
            for i in range(0, len(ideas), batch_size):
                batch = ideas[i:i + batch_size]
                
                # Simulate batch processing
                batch_results = []
                for idea in batch:
                    # Mock processing
                    processed_idea = {
                        'id': idea['id'],
                        'processed': True,
                        'engagement_score': idea.get('vote_count', 0) * 0.1
                    }
                    batch_results.append(processed_idea)
                
                results.extend(batch_results)
            
            return results
        
        # Test with large dataset
        large_dataset = [{'id': i, 'vote_count': i % 50} for i in range(1000)]
        
        results = process_ideas_in_batches(large_dataset, batch_size=100)
        
        assert len(results) == 1000
        assert all(result['processed'] for result in results)
        assert results[50]['engagement_score'] == 5.0  # 50 * 0.1
    
    def test_caching_strategy(self):
        """Test analytics caching strategy."""
        cache = {}
        
        def get_analytics_with_cache(idea_id, force_refresh=False):
            """Get analytics with caching."""
            cache_key = f"analytics_{idea_id}"
            
            # Check cache first
            if not force_refresh and cache_key in cache:
                cached_data = cache[cache_key]
                # Check if cache is still valid (e.g., less than 1 hour old)
                if (datetime.now() - cached_data['timestamp']).seconds < 3600:
                    return cached_data['data']
            
            # Calculate fresh analytics (mock)
            fresh_analytics = {
                'engagement_score': 0.75,
                'trend': 'rising',
                'prediction_score': 0.82
            }
            
            # Store in cache
            cache[cache_key] = {
                'data': fresh_analytics,
                'timestamp': datetime.now()
            }
            
            return fresh_analytics
        
        # Test cache miss
        result1 = get_analytics_with_cache(123)
        assert result1['engagement_score'] == 0.75
        assert len(cache) == 1
        
        # Test cache hit
        result2 = get_analytics_with_cache(123)
        assert result2 == result1  # Should be same data from cache
        
        # Test force refresh
        result3 = get_analytics_with_cache(123, force_refresh=True)
        assert result3['engagement_score'] == 0.75  # Fresh calculation


class TestAnalyticsDataQuality:
    """Test cases for analytics data quality checks."""
    
    def test_data_validation(self):
        """Test data validation for analytics."""
        def validate_analytics_data(data):
            """Validate data quality for analytics processing."""
            errors = []
            warnings = []
            
            # Check required fields
            required_fields = ['id', 'title', 'created_at', 'vote_count']
            for field in required_fields:
                if field not in data:
                    errors.append(f"Missing required field: {field}")
            
            # Check data types
            if 'vote_count' in data and not isinstance(data['vote_count'], (int, float)):
                errors.append("vote_count must be numeric")
            
            if 'average_rating' in data:
                rating = data['average_rating']
                if not isinstance(rating, (int, float)) or not (0 <= rating <= 5):
                    errors.append("average_rating must be numeric between 0 and 5")
            
            # Check data ranges
            if 'vote_count' in data and data['vote_count'] < 0:
                errors.append("vote_count cannot be negative")
            
            # Data quality warnings
            if 'title' in data and len(data['title']) < 3:
                warnings.append("Title is very short")
            
            if 'vote_count' in data and data['vote_count'] > 1000:
                warnings.append("Unusually high vote count")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
        
        # Test valid data
        valid_data = {
            'id': 123,
            'title': 'Valid Test Idea',
            'created_at': datetime.now(),
            'vote_count': 25,
            'average_rating': 4.2
        }
        
        result = validate_analytics_data(valid_data)
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
        
        # Test invalid data
        invalid_data = {
            'id': 124,
            'title': 'AB',  # Too short
            'vote_count': -5,  # Negative
            'average_rating': 6.0  # Out of range
        }
        
        result = validate_analytics_data(invalid_data)
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
        assert "Missing required field: created_at" in result['errors']
        assert "vote_count cannot be negative" in result['errors']
        assert "average_rating must be numeric between 0 and 5" in result['errors']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])