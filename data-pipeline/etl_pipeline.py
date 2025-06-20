"""ETL pipeline for MindMesh data processing and transformation."""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import re
from dataclasses import dataclass
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ETLConfig:
    """Configuration for ETL pipeline."""
    source_path: str
    target_path: str
    batch_size: int = 1000
    max_workers: int = 4
    quality_threshold: float = 0.8
    enable_validation: bool = True
    enable_deduplication: bool = True
    enable_enrichment: bool = True


class DataExtractor:
    """Extract data from various sources."""
    
    def __init__(self, config: ETLConfig):
        self.config = config
    
    def extract_user_interactions(self, source_path: str) -> pd.DataFrame:
        """Extract user interaction data."""
        logger.info(f"Extracting user interactions from {source_path}")
        
        try:
            # Support multiple formats
            if source_path.endswith('.parquet'):
                df = pd.read_parquet(source_path)
            elif source_path.endswith('.csv'):
                df = pd.read_csv(source_path)
            elif source_path.endswith('.json'):
                df = pd.read_json(source_path, lines=True)
            else:
                raise ValueError(f"Unsupported file format: {source_path}")
            
            logger.info(f"Extracted {len(df)} user interaction records")
            return df
            
        except Exception as e:
            logger.error(f"Error extracting user interactions: {e}")
            raise
    
    def extract_thought_data(self, source_path: str) -> pd.DataFrame:
        """Extract thought capture data."""
        logger.info(f"Extracting thought data from {source_path}")
        
        try:
            df = pd.read_json(source_path, lines=True)
            
            # Parse nested JSON fields if present
            if 'metadata' in df.columns:
                metadata_df = pd.json_normalize(df['metadata'])
                df = pd.concat([df.drop('metadata', axis=1), metadata_df], axis=1)
            
            logger.info(f"Extracted {len(df)} thought records")
            return df
            
        except Exception as e:
            logger.error(f"Error extracting thought data: {e}")
            raise
    
    def extract_system_metrics(self, source_path: str) -> pd.DataFrame:
        """Extract system performance metrics."""
        logger.info(f"Extracting system metrics from {source_path}")
        
        try:
            df = pd.read_parquet(source_path)
            
            # Convert timestamp columns
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            logger.info(f"Extracted {len(df)} metric records")
            return df
            
        except Exception as e:
            logger.error(f"Error extracting system metrics: {e}")
            raise
    
    def extract_batch(self, source_paths: List[str]) -> Dict[str, pd.DataFrame]:
        """Extract data from multiple sources in parallel."""
        logger.info(f"Starting batch extraction from {len(source_paths)} sources")
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit extraction tasks
            future_to_source = {}
            
            for source_path in source_paths:
                if 'interactions' in source_path:
                    future = executor.submit(self.extract_user_interactions, source_path)
                elif 'thoughts' in source_path:
                    future = executor.submit(self.extract_thought_data, source_path)
                elif 'metrics' in source_path:
                    future = executor.submit(self.extract_system_metrics, source_path)
                else:
                    continue
                
                future_to_source[future] = source_path
            
            # Collect results
            for future in as_completed(future_to_source):
                source_path = future_to_source[future]
                try:
                    results[source_path] = future.result()
                except Exception as e:
                    logger.error(f"Error extracting from {source_path}: {e}")
        
        logger.info(f"Batch extraction completed: {len(results)} sources processed")
        return results


class DataTransformer:
    """Transform and clean extracted data."""
    
    def __init__(self, config: ETLConfig):
        self.config = config
    
    def transform_user_interactions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform user interaction data."""
        logger.info("Transforming user interaction data")
        
        try:
            # Standardize column names
            df.columns = df.columns.str.lower().str.replace(' ', '_')
            
            # Convert timestamps
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Add derived columns
            df['hour'] = df['timestamp'].dt.hour
            df['day_of_week'] = df['timestamp'].dt.dayofweek
            df['is_weekend'] = df['day_of_week'].isin([5, 6])
            
            # Clean interaction types
            if 'interaction_type' in df.columns:
                df['interaction_type'] = df['interaction_type'].str.lower().str.strip()
            
            # Calculate session duration if needed
            if 'session_start' in df.columns and 'session_end' in df.columns:
                df['session_duration'] = (
                    pd.to_datetime(df['session_end']) - 
                    pd.to_datetime(df['session_start'])
                ).dt.total_seconds()
            
            # Remove outliers
            df = self._remove_outliers(df, ['session_duration', 'engagement_score'])
            
            logger.info(f"Transformed {len(df)} user interaction records")
            return df
            
        except Exception as e:
            logger.error(f"Error transforming user interactions: {e}")
            raise
    
    def transform_thought_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform thought capture data."""
        logger.info("Transforming thought data")
        
        try:
            # Clean text data
            if 'thought_text' in df.columns:
                df['thought_text'] = df['thought_text'].apply(self._clean_text)
                df['word_count'] = df['thought_text'].str.split().str.len()
                df['char_count'] = df['thought_text'].str.len()
            
            # Normalize sentiment scores
            if 'sentiment_score' in df.columns:
                df['sentiment_score'] = df['sentiment_score'].clip(-1, 1)
                df['sentiment_category'] = df['sentiment_score'].apply(
                    lambda x: 'positive' if x > 0.3 else 'negative' if x < -0.3 else 'neutral'
                )
            
            # Process tags
            if 'tags' in df.columns:
                df['tag_count'] = df['tags'].apply(
                    lambda x: len(x) if isinstance(x, list) else 0
                )
                df['has_personal_tag'] = df['tags'].apply(
                    lambda x: 'personal' in x if isinstance(x, list) else False
                )
            
            # Extract time-based features
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['hour'] = df['timestamp'].dt.hour
                df['day_of_week'] = df['timestamp'].dt.dayofweek
            
            logger.info(f"Transformed {len(df)} thought records")
            return df
            
        except Exception as e:
            logger.error(f"Error transforming thought data: {e}")
            raise
    
    def transform_system_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform system performance metrics."""
        logger.info("Transforming system metrics")
        
        try:
            # Standardize metric names
            if 'metric_name' in df.columns:
                df['metric_name'] = df['metric_name'].str.lower().str.replace(' ', '_')
            
            # Convert timestamp
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Add time-based aggregations
            df['minute'] = df['timestamp'].dt.floor('min')
            df['hour'] = df['timestamp'].dt.floor('H')
            
            # Calculate rolling averages
            df = df.sort_values('timestamp')
            df['metric_value_ma_5'] = df.groupby('metric_name')['metric_value'].rolling(5).mean().reset_index(drop=True)
            df['metric_value_ma_15'] = df.groupby('metric_name')['metric_value'].rolling(15).mean().reset_index(drop=True)
            
            # Detect anomalies
            df['is_anomaly'] = df.groupby('metric_name')['metric_value'].apply(
                lambda x: np.abs(x - x.mean()) > 3 * x.std()
            ).reset_index(drop=True)
            
            logger.info(f"Transformed {len(df)} metric records")
            return df
            
        except Exception as e:
            logger.error(f"Error transforming system metrics: {e}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """Clean text data."""
        if not isinstance(text, str):
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove special characters (keep basic punctuation)
        text = re.sub(r'[^a-zA-Z0-9\s.,!?;:]', '', text)
        
        return text
    
    def _remove_outliers(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Remove outliers using IQR method."""
        for column in columns:
            if column in df.columns and df[column].dtype in ['float64', 'int64']:
                Q1 = df[column].quantile(0.25)
                Q3 = df[column].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                before_count = len(df)
                df = df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]
                after_count = len(df)
                
                if before_count > after_count:
                    logger.info(f"Removed {before_count - after_count} outliers from {column}")
        
        return df


class DataValidator:
    """Validate data quality and consistency."""
    
    def __init__(self, config: ETLConfig):
        self.config = config
    
    def validate_user_interactions(self, df: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
        """Validate user interaction data."""
        logger.info("Validating user interaction data")
        
        validation_results = {
            'total_records': len(df),
            'passed': True,
            'issues': []
        }
        
        # Check required columns
        required_columns = ['user_id', 'timestamp', 'interaction_type']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            validation_results['issues'].append(f"Missing required columns: {missing_columns}")
            validation_results['passed'] = False
        
        # Check for null values in critical columns
        for column in required_columns:
            if column in df.columns:
                null_count = df[column].isnull().sum()
                if null_count > 0:
                    null_percentage = (null_count / len(df)) * 100
                    validation_results['issues'].append(
                        f"Column {column} has {null_count} null values ({null_percentage:.2f}%)"
                    )
                    
                    if null_percentage > 10:  # More than 10% nulls
                        validation_results['passed'] = False
        
        # Check timestamp validity
        if 'timestamp' in df.columns:
            future_timestamps = df[df['timestamp'] > datetime.now()]
            if len(future_timestamps) > 0:
                validation_results['issues'].append(
                    f"Found {len(future_timestamps)} future timestamps"
                )
        
        # Check data types
        if 'user_id' in df.columns and df['user_id'].dtype != 'object':
            validation_results['issues'].append("user_id should be string type")
        
        return validation_results['passed'], validation_results
    
    def validate_thought_data(self, df: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
        """Validate thought capture data."""
        logger.info("Validating thought data")
        
        validation_results = {
            'total_records': len(df),
            'passed': True,
            'issues': []
        }
        
        # Check required columns
        required_columns = ['user_id', 'thought_text', 'timestamp']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            validation_results['issues'].append(f"Missing required columns: {missing_columns}")
            validation_results['passed'] = False
        
        # Check thought text quality
        if 'thought_text' in df.columns:
            empty_thoughts = df[df['thought_text'].str.strip() == '']
            if len(empty_thoughts) > 0:
                validation_results['issues'].append(
                    f"Found {len(empty_thoughts)} empty thoughts"
                )
            
            # Check for suspiciously long thoughts (potential data corruption)
            long_thoughts = df[df['thought_text'].str.len() > 10000]
            if len(long_thoughts) > 0:
                validation_results['issues'].append(
                    f"Found {len(long_thoughts)} suspiciously long thoughts (>10k chars)"
                )
        
        # Check sentiment score range
        if 'sentiment_score' in df.columns:
            invalid_sentiment = df[
                (df['sentiment_score'] < -1) | (df['sentiment_score'] > 1)
            ]
            if len(invalid_sentiment) > 0:
                validation_results['issues'].append(
                    f"Found {len(invalid_sentiment)} invalid sentiment scores (not in [-1, 1])"
                )
        
        return validation_results['passed'], validation_results
    
    def validate_system_metrics(self, df: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
        """Validate system metrics data."""
        logger.info("Validating system metrics data")
        
        validation_results = {
            'total_records': len(df),
            'passed': True,
            'issues': []
        }
        
        # Check required columns
        required_columns = ['metric_name', 'metric_value', 'timestamp', 'component']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            validation_results['issues'].append(f"Missing required columns: {missing_columns}")
            validation_results['passed'] = False
        
        # Check for negative values where they shouldn't be
        if 'metric_value' in df.columns:
            negative_values = df[df['metric_value'] < 0]
            if len(negative_values) > 0:
                validation_results['issues'].append(
                    f"Found {len(negative_values)} negative metric values"
                )
        
        # Check for extreme values
        if 'metric_value' in df.columns:
            extreme_values = df[df['metric_value'] > 1000000]  # Arbitrary large number
            if len(extreme_values) > 0:
                validation_results['issues'].append(
                    f"Found {len(extreme_values)} extreme metric values (>1M)"
                )
        
        return validation_results['passed'], validation_results


class DataLoader:
    """Load transformed data to target destinations."""
    
    def __init__(self, config: ETLConfig):
        self.config = config
    
    def load_to_parquet(self, df: pd.DataFrame, target_path: str, partition_cols: Optional[List[str]] = None):
        """Load data to Parquet format."""
        logger.info(f"Loading {len(df)} records to {target_path}")
        
        try:
            Path(target_path).parent.mkdir(parents=True, exist_ok=True)
            
            if partition_cols:
                # Partitioned write
                df.to_parquet(
                    target_path,
                    partition_cols=partition_cols,
                    index=False,
                    compression='snappy'
                )
            else:
                # Single file write
                df.to_parquet(target_path, index=False, compression='snappy')
            
            logger.info(f"Successfully loaded data to {target_path}")
            
        except Exception as e:
            logger.error(f"Error loading data to {target_path}: {e}")
            raise
    
    def load_to_database(self, df: pd.DataFrame, table_name: str, connection_string: str):
        """Load data to database."""
        logger.info(f"Loading {len(df)} records to database table {table_name}")
        
        try:
            # This would use SQLAlchemy or similar for actual database loading
            # For now, we'll just log the operation
            logger.info(f"Would load {len(df)} records to {table_name}")
            
        except Exception as e:
            logger.error(f"Error loading data to database: {e}")
            raise
    
    def load_batch(self, datasets: Dict[str, pd.DataFrame], target_base_path: str):
        """Load multiple datasets in parallel."""
        logger.info(f"Loading {len(datasets)} datasets to {target_base_path}")
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = []
            
            for dataset_name, df in datasets.items():
                target_path = f"{target_base_path}/{dataset_name}.parquet"
                
                # Determine partitioning strategy
                partition_cols = None
                if 'timestamp' in df.columns and len(df) > 10000:
                    df['date'] = df['timestamp'].dt.date
                    partition_cols = ['date']
                
                future = executor.submit(self.load_to_parquet, df, target_path, partition_cols)
                futures.append(future)
            
            # Wait for all loads to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error in batch load: {e}")
        
        logger.info("Batch loading completed")


class ETLPipeline:
    """Main ETL pipeline orchestrator."""
    
    def __init__(self, config: ETLConfig):
        self.config = config
        self.extractor = DataExtractor(config)
        self.transformer = DataTransformer(config)
        self.validator = DataValidator(config)
        self.loader = DataLoader(config)
        self.metrics = {
            'start_time': None,
            'end_time': None,
            'records_processed': 0,
            'validation_failures': 0,
            'errors': []
        }
    
    def run_pipeline(self, source_paths: List[str], target_path: str) -> Dict[str, Any]:
        """Run the complete ETL pipeline."""
        self.metrics['start_time'] = datetime.now()
        logger.info(f"Starting ETL pipeline with {len(source_paths)} sources")
        
        try:
            # Extract
            logger.info("=== EXTRACTION PHASE ===")
            raw_datasets = self.extractor.extract_batch(source_paths)
            
            # Transform
            logger.info("=== TRANSFORMATION PHASE ===")
            transformed_datasets = {}
            
            for source_path, df in raw_datasets.items():
                if 'interactions' in source_path:
                    transformed_df = self.transformer.transform_user_interactions(df)
                elif 'thoughts' in source_path:
                    transformed_df = self.transformer.transform_thought_data(df)
                elif 'metrics' in source_path:
                    transformed_df = self.transformer.transform_system_metrics(df)
                else:
                    transformed_df = df
                
                transformed_datasets[source_path] = transformed_df
                self.metrics['records_processed'] += len(transformed_df)
            
            # Validate
            if self.config.enable_validation:
                logger.info("=== VALIDATION PHASE ===")
                validated_datasets = {}
                
                for source_path, df in transformed_datasets.items():
                    if 'interactions' in source_path:
                        is_valid, validation_info = self.validator.validate_user_interactions(df)
                    elif 'thoughts' in source_path:
                        is_valid, validation_info = self.validator.validate_thought_data(df)
                    elif 'metrics' in source_path:
                        is_valid, validation_info = self.validator.validate_system_metrics(df)
                    else:
                        is_valid, validation_info = True, {'passed': True, 'issues': []}
                    
                    if is_valid or not self.config.enable_validation:
                        validated_datasets[source_path] = df
                    else:
                        logger.warning(f"Validation failed for {source_path}: {validation_info}")
                        self.metrics['validation_failures'] += 1
                
                transformed_datasets = validated_datasets
            
            # Load
            logger.info("=== LOADING PHASE ===")
            self.loader.load_batch(transformed_datasets, target_path)
            
            self.metrics['end_time'] = datetime.now()
            duration = self.metrics['end_time'] - self.metrics['start_time']
            
            logger.info(f"ETL pipeline completed successfully in {duration}")
            logger.info(f"Processed {self.metrics['records_processed']} records")
            
            return {
                'success': True,
                'duration': duration.total_seconds(),
                'records_processed': self.metrics['records_processed'],
                'validation_failures': self.metrics['validation_failures'],
                'datasets_loaded': len(transformed_datasets)
            }
            
        except Exception as e:
            self.metrics['end_time'] = datetime.now()
            self.metrics['errors'].append(str(e))
            logger.error(f"ETL pipeline failed: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'records_processed': self.metrics['records_processed'],
                'validation_failures': self.metrics['validation_failures']
            }


if __name__ == "__main__":
    # Example usage
    config = ETLConfig(
        source_path="/data/raw",
        target_path="/data/processed",
        batch_size=1000,
        max_workers=4,
        enable_validation=True
    )
    
    pipeline = ETLPipeline(config)
    
    # Example source paths
    source_paths = [
        "/data/raw/user_interactions.parquet",
        "/data/raw/thought_captures.json",
        "/data/raw/system_metrics.parquet"
    ]
    
    results = pipeline.run_pipeline(source_paths, "/data/processed")
    print(f"Pipeline results: {results}")