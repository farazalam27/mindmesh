"""PySpark session configuration for Analytics service."""
from pyspark.sql import SparkSession
from pyspark.conf import SparkConf
import os
import logging

logger = logging.getLogger(__name__)

# Spark configuration
SPARK_APP_NAME = os.getenv("SPARK_APP_NAME", "MindMeshAnalytics")
SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")
SPARK_EXECUTOR_MEMORY = os.getenv("SPARK_EXECUTOR_MEMORY", "2g")
SPARK_DRIVER_MEMORY = os.getenv("SPARK_DRIVER_MEMORY", "1g")
SPARK_CHECKPOINT_DIR = os.getenv("SPARK_CHECKPOINT_DIR", "/tmp/spark-checkpoint")


def create_spark_session(app_name: str = SPARK_APP_NAME) -> SparkSession:
    """
    Create and configure Spark session.
    
    Args:
        app_name: Name of the Spark application
        
    Returns:
        Configured SparkSession
    """
    try:
        # Configure Spark
        conf = SparkConf().setAppName(app_name) \
            .setMaster(SPARK_MASTER) \
            .set("spark.executor.memory", SPARK_EXECUTOR_MEMORY) \
            .set("spark.driver.memory", SPARK_DRIVER_MEMORY) \
            .set("spark.sql.adaptive.enabled", "true") \
            .set("spark.sql.adaptive.coalescePartitions.enabled", "true") \
            .set("spark.sql.streaming.checkpointLocation", SPARK_CHECKPOINT_DIR)
        
        # Additional configurations for structured streaming
        conf.set("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true")
        conf.set("spark.sql.shuffle.partitions", "200")
        
        # Create session
        spark = SparkSession.builder \
            .config(conf=conf) \
            .enableHiveSupport() \
            .getOrCreate()
        
        # Set log level
        spark.sparkContext.setLogLevel("WARN")
        
        logger.info(f"Spark session created successfully: {app_name}")
        return spark
        
    except Exception as e:
        logger.error(f"Failed to create Spark session: {e}")
        raise


def get_spark_session() -> SparkSession:
    """
    Get or create a Spark session.
    
    Returns:
        Active SparkSession
    """
    try:
        # Try to get existing session
        spark = SparkSession.getActiveSession()
        if spark is None:
            spark = create_spark_session()
        return spark
    except Exception as e:
        logger.error(f"Error getting Spark session: {e}")
        return create_spark_session()


def stop_spark_session():
    """Stop the active Spark session."""
    try:
        spark = SparkSession.getActiveSession()
        if spark:
            spark.stop()
            logger.info("Spark session stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping Spark session: {e}")


# Utility functions for Spark operations
def create_database_connection_properties():
    """Create database connection properties for Spark."""
    return {
        "driver": "org.postgresql.Driver",
        "user": os.getenv("DB_USER", "user"),
        "password": os.getenv("DB_PASSWORD", "password"),
        "fetchsize": "1000",
        "batchsize": "1000"
    }


def read_from_postgres(spark: SparkSession, table_name: str, database_url: str = None):
    """
    Read data from PostgreSQL table.
    
    Args:
        spark: SparkSession instance
        table_name: Name of the table to read
        database_url: JDBC URL for the database
        
    Returns:
        DataFrame with table data
    """
    if database_url is None:
        database_url = os.getenv(
            "ANALYTICS_JDBC_URL",
            "jdbc:postgresql://localhost:5432/mindmesh"
        )
    
    properties = create_database_connection_properties()
    
    try:
        df = spark.read.jdbc(
            url=database_url,
            table=table_name,
            properties=properties
        )
        return df
    except Exception as e:
        logger.error(f"Error reading from PostgreSQL table {table_name}: {e}")
        raise


def write_to_postgres(df, table_name: str, mode: str = "append", database_url: str = None):
    """
    Write DataFrame to PostgreSQL table.
    
    Args:
        df: DataFrame to write
        table_name: Name of the target table
        mode: Write mode (append, overwrite, etc.)
        database_url: JDBC URL for the database
    """
    if database_url is None:
        database_url = os.getenv(
            "ANALYTICS_JDBC_URL",
            "jdbc:postgresql://localhost:5432/mindmesh"
        )
    
    properties = create_database_connection_properties()
    
    try:
        df.write.jdbc(
            url=database_url,
            table=table_name,
            mode=mode,
            properties=properties
        )
        logger.info(f"Successfully wrote data to table {table_name}")
    except Exception as e:
        logger.error(f"Error writing to PostgreSQL table {table_name}: {e}")
        raise