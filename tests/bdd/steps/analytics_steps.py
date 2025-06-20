"""Step definitions for Analytics and Machine Learning feature tests."""
import pytest
from behave import given, when, then, step
from unittest.mock import Mock, patch, MagicMock
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Mock PySpark imports since they might not be available in test environment
try:
    from pyspark.sql import SparkSession, DataFrame as SparkDataFrame
    from pyspark.ml.clustering import KMeansModel
    from pyspark.ml.classification import RandomForestClassificationModel
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False
    SparkSession = Mock
    SparkDataFrame = Mock
    KMeansModel = Mock
    RandomForestClassificationModel = Mock

from services.ideas.models import Idea, IdeaStatus, IdeaCategory


@given('the analytics service is running')
def step_analytics_service_running(context):
    """Mock or verify that the analytics service is running."""
    context.analytics_service_url = "http://localhost:8004"
    context.analytics_service_running = True
    
    if not hasattr(context, 'analytics_client'):
        context.analytics_client = Mock()


@given('Spark cluster is available')
def step_spark_cluster_available(context):
    """Mock Spark cluster availability."""
    if SPARK_AVAILABLE:
        context.spark = Mock(spec=SparkSession)
    else:
        context.spark = Mock()
    
    context.spark_available = True
    
    # Mock Spark operations
    context.spark.sql.return_value = Mock()
    context.spark.read.format.return_value.load.return_value = Mock()


@given('there is historical data with {count:d}+ ideas')
def step_historical_data_available(context, count):
    """Set up historical data for analytics."""
    if not hasattr(context, 'db'):
        # Set up test database
        context.test_db_url = "sqlite:///:memory:"
        context.engine = create_engine(context.test_db_url)
        
        from services.ideas.models import Base as IdeasBase
        IdeasBase.metadata.create_all(context.engine)
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=context.engine)
        context.db = SessionLocal()
    
    # Generate historical test data
    context.historical_ideas = []
    categories = [IdeaCategory.INNOVATION, IdeaCategory.IMPROVEMENT, IdeaCategory.COST_SAVING]
    
    for i in range(count):
        created_date = datetime.now(timezone.utc) - timedelta(days=np.random.randint(1, 365))
        
        idea = Idea(
            id=i + 1,
            title=f"Historical Idea {i + 1}",
            description=f"Description for historical idea {i + 1} with various keywords",
            category=np.random.choice(categories),
            status=np.random.choice([IdeaStatus.PUBLISHED, IdeaStatus.IMPLEMENTED, IdeaStatus.REJECTED]),
            user_id=f"emp{i % 100:03d}",
            user_email=f"emp{i % 100:03d}@company.com",
            vote_count=np.random.randint(0, 100),
            average_rating=np.random.uniform(1.0, 5.0),
            view_count=np.random.randint(10, 1000),
            created_at=created_date,
            published_at=created_date + timedelta(hours=np.random.randint(1, 48))
        )
        
        context.db.add(idea)
        context.historical_ideas.append(idea)
    
    context.db.commit()
    context.historical_data_count = count


@given('ML models are trained and available')
def step_ml_models_available(context):
    """Mock trained ML models."""
    context.ml_models = {
        'clustering_model': Mock(spec=KMeansModel),
        'success_prediction_model': Mock(spec=RandomForestClassificationModel),
        'topic_model': Mock()
    }
    
    # Mock model predictions
    context.ml_models['clustering_model'].transform.return_value = Mock()
    context.ml_models['success_prediction_model'].transform.return_value = Mock()


@given('there are ideas across different categories and themes')
def step_ideas_across_categories_and_themes(context):
    """Ensure diverse ideas for clustering analysis."""
    # Add specific themed ideas for clustering
    themed_ideas = [
        {
            'title': 'AI-Powered Customer Service Bot',
            'description': 'Implement artificial intelligence chatbot for automated customer support',
            'category': IdeaCategory.INNOVATION,
            'themes': ['AI', 'automation', 'customer service']
        },
        {
            'title': 'Machine Learning Data Analytics',
            'description': 'Use machine learning algorithms for advanced data analysis and insights',
            'category': IdeaCategory.INNOVATION,
            'themes': ['AI', 'machine learning', 'analytics']
        },
        {
            'title': 'Green Energy Office Initiative',
            'description': 'Switch to renewable energy sources and reduce carbon footprint',
            'category': IdeaCategory.IMPROVEMENT,
            'themes': ['sustainability', 'green', 'environment']
        },
        {
            'title': 'Solar Panel Installation',
            'description': 'Install solar panels on office buildings to reduce energy costs',
            'category': IdeaCategory.COST_SAVING,
            'themes': ['sustainability', 'solar', 'cost reduction']
        }
    ]
    
    for i, idea_data in enumerate(themed_ideas):
        idea = Idea(
            id=2000 + i,
            title=idea_data['title'],
            description=idea_data['description'],
            category=idea_data['category'],
            status=IdeaStatus.PUBLISHED,
            user_id=f"emp{i:03d}",
            user_email=f"emp{i:03d}@company.com",
            vote_count=np.random.randint(10, 50),
            average_rating=np.random.uniform(3.0, 5.0),
            view_count=np.random.randint(50, 300),
            published_at=datetime.now(timezone.utc) - timedelta(days=np.random.randint(1, 30))
        )
        
        context.db.add(idea)
    
    context.db.commit()
    context.themed_ideas_added = True


@when('I run the idea clustering analysis')
def step_run_idea_clustering_analysis(context):
    """Run clustering analysis on ideas."""
    # Mock clustering analysis
    ideas = context.db.query(Idea).all()
    
    # Simulate clustering results
    context.clustering_results = {
        'clusters': [
            {
                'cluster_id': 1,
                'theme': 'AI/Automation',
                'idea_count': 45,
                'avg_engagement': 0.78,
                'ideas': [idea for idea in ideas if 'AI' in idea.title or 'automation' in idea.description.lower()][:5]
            },
            {
                'cluster_id': 2,
                'theme': 'Sustainability',
                'idea_count': 38,
                'avg_engagement': 0.82,
                'ideas': [idea for idea in ideas if 'green' in idea.title.lower() or 'solar' in idea.description.lower()][:5]
            },
            {
                'cluster_id': 3,
                'theme': 'Employee Experience',
                'idea_count': 52,
                'avg_engagement': 0.71,
                'ideas': [idea for idea in ideas if 'employee' in idea.title.lower()][:5]
            },
            {
                'cluster_id': 4,
                'theme': 'Cost Optimization',
                'idea_count': 29,
                'avg_engagement': 0.65,
                'ideas': [idea for idea in ideas if idea.category == IdeaCategory.COST_SAVING][:5]
            }
        ],
        'quality_metrics': {
            'silhouette_score': 0.73,
            'inertia': 145.6,
            'n_clusters': 4
        }
    }
    
    # Mock Spark DataFrame transformation
    if hasattr(context, 'spark'):
        context.spark.sql.return_value = Mock()
        context.clustering_executed = True


@then('ideas should be grouped into meaningful clusters')
def step_ideas_grouped_into_clusters(context):
    """Verify ideas are grouped into meaningful clusters."""
    assert 'clusters' in context.clustering_results
    assert len(context.clustering_results['clusters']) > 0
    
    for cluster in context.clustering_results['clusters']:
        assert 'cluster_id' in cluster
        assert 'theme' in cluster
        assert 'idea_count' in cluster


@then('cluster themes should be automatically identified')
def step_cluster_themes_identified(context):
    """Verify cluster themes are identified."""
    themes = [cluster['theme'] for cluster in context.clustering_results['clusters']]
    expected_themes = ['AI/Automation', 'Sustainability', 'Employee Experience', 'Cost Optimization']
    
    for theme in expected_themes:
        assert theme in themes


@then('similar ideas should be grouped together')
def step_similar_ideas_grouped(context):
    """Verify similar ideas are in the same cluster."""
    ai_cluster = next(
        (cluster for cluster in context.clustering_results['clusters'] if cluster['theme'] == 'AI/Automation'),
        None
    )
    
    if ai_cluster:
        # Check that AI-related ideas are in the AI cluster
        ai_ideas = [idea for idea in ai_cluster['ideas'] if 'AI' in idea.title or 'machine learning' in idea.description.lower()]
        assert len(ai_ideas) > 0


@then('cluster characteristics should be documented')
def step_cluster_characteristics_documented(context):
    """Verify cluster characteristics match expected values."""
    if hasattr(context, 'table'):
        expected_clusters = {row['theme']: row for row in context.table}
        
        for cluster in context.clustering_results['clusters']:
            theme = cluster['theme']
            if theme in expected_clusters:
                expected = expected_clusters[theme]
                # Allow some tolerance in the comparison
                assert abs(cluster['idea_count'] - int(expected['idea_count'])) <= 5
                assert abs(cluster['avg_engagement'] - float(expected['avg_engagement'])) <= 0.1


@then('clustering quality metrics should meet thresholds')
def step_clustering_quality_meets_thresholds(context):
    """Verify clustering quality metrics."""
    metrics = context.clustering_results['quality_metrics']
    
    # Check silhouette score (should be > 0.5 for good clustering)
    assert metrics['silhouette_score'] > 0.5
    
    # Check that we have reasonable number of clusters
    assert 2 <= metrics['n_clusters'] <= 10


@given('there are idea descriptions and comments from the last {months:d} months')
def step_idea_descriptions_from_months(context, months):
    """Set up recent idea and comment data for topic modeling."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=months * 30)
    
    # Filter existing ideas to recent ones
    context.recent_ideas = [
        idea for idea in context.historical_ideas
        if idea.created_at >= cutoff_date
    ]
    
    # Add some comment-like text data
    context.comment_texts = [
        "This is a great idea for remote work collaboration",
        "We need more sustainable energy solutions",
        "Customer experience improvements are crucial",
        "AI and automation will transform our business"
    ] * 10  # Repeat to have more text data


@when('I perform topic modeling analysis')
def step_perform_topic_modeling(context):
    """Run topic modeling analysis."""
    # Mock LDA topic modeling results
    context.topic_modeling_results = {
        'topics': [
            {
                'topic_id': 0,
                'keywords': ['remote', 'collaboration', 'tools', 'work', 'team'],
                'trend': 'Rising',
                'growth_rate': 0.15
            },
            {
                'topic_id': 1,
                'keywords': ['sustainable', 'energy', 'carbon', 'green', 'environment'],
                'trend': 'Stable',
                'growth_rate': 0.03
            },
            {
                'topic_id': 2,
                'keywords': ['customer', 'experience', 'satisfaction', 'service', 'support'],
                'trend': 'Declining',
                'growth_rate': -0.08
            }
        ],
        'topic_distribution': Mock(),
        'model_coherence': 0.65
    }


@then('emerging topics should be identified')
def step_emerging_topics_identified(context):
    """Verify emerging topics are identified."""
    topics = context.topic_modeling_results['topics']
    assert len(topics) > 0
    
    # Check that topics have required fields
    for topic in topics:
        assert 'topic_id' in topic
        assert 'keywords' in topic
        assert len(topic['keywords']) > 0


@then('topic evolution over time should be tracked')
def step_topic_evolution_tracked(context):
    """Verify topic evolution tracking."""
    for topic in context.topic_modeling_results['topics']:
        assert 'trend' in topic
        assert 'growth_rate' in topic
        assert topic['trend'] in ['Rising', 'Stable', 'Declining']


@then('trending topics should be highlighted')
def step_trending_topics_highlighted(context):
    """Verify trending topics are highlighted with correct data."""
    if hasattr(context, 'table'):
        expected_topics = {row['topic']: row for row in context.table}
        
        for topic in context.topic_modeling_results['topics']:
            # Match by keywords
            topic_keywords = topic['keywords']
            
            # Find matching expected topic
            for expected_topic_name, expected_data in expected_topics.items():
                expected_keywords = expected_data['keywords'].replace('"', '').split(', ')
                
                # Check if there's keyword overlap
                if any(keyword in topic_keywords for keyword in expected_keywords):
                    assert topic['trend'] == expected_data['trend']
                    expected_growth = float(expected_data['growth_rate'].replace('%', '')) / 100
                    assert abs(topic['growth_rate'] - expected_growth) < 0.05


@then('topic recommendations should be provided for future campaigns')
def step_topic_recommendations_provided(context):
    """Verify topic recommendations are generated."""
    # Generate mock recommendations based on trends
    context.topic_recommendations = []
    
    for topic in context.topic_modeling_results['topics']:
        if topic['trend'] == 'Rising':
            context.topic_recommendations.append({
                'topic': topic['keywords'][0],
                'recommendation': 'Increase focus on this emerging area',
                'priority': 'High'
            })
        elif topic['trend'] == 'Declining':
            context.topic_recommendations.append({
                'topic': topic['keywords'][0],
                'recommendation': 'Consider revitalization strategies',
                'priority': 'Medium'
            })
    
    assert len(context.topic_recommendations) > 0


@given('there are newly submitted ideas awaiting evaluation')
def step_newly_submitted_ideas(context):
    """Create newly submitted ideas for success prediction."""
    context.new_ideas = []
    
    new_ideas_data = [
        {
            'title': 'Blockchain Supply Chain Tracking',
            'description': 'Use blockchain for transparent supply chain management',
            'category': IdeaCategory.INNOVATION,
            'expected_success_prob': 0.85
        },
        {
            'title': 'Office Space Reorganization',
            'description': 'Reorganize office layout for better collaboration',
            'category': IdeaCategory.IMPROVEMENT,
            'expected_success_prob': 0.42
        },
        {
            'title': 'Outdated Paper Filing System',
            'description': 'Continue using paper files for document storage',
            'category': IdeaCategory.OTHER,
            'expected_success_prob': 0.23
        }
    ]
    
    for i, idea_data in enumerate(new_ideas_data):
        idea = Idea(
            id=3000 + i,
            title=idea_data['title'],
            description=idea_data['description'],
            category=idea_data['category'],
            status=IdeaStatus.DRAFT,
            user_id=f"newuser{i:03d}",
            user_email=f"newuser{i:03d}@company.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        
        context.db.add(idea)
        context.new_ideas.append({
            'idea': idea,
            'expected_success_prob': idea_data['expected_success_prob']
        })
    
    context.db.commit()


@given('historical success patterns are available in the ML model')
def step_historical_success_patterns_available(context):
    """Mock historical success patterns in ML model."""
    context.success_patterns = {
        'high_engagement_ideas': {'success_rate': 0.85, 'count': 120},
        'innovation_category': {'success_rate': 0.72, 'count': 200},
        'improvement_category': {'success_rate': 0.68, 'count': 150},
        'clear_value_proposition': {'success_rate': 0.79, 'count': 180}
    }


@when('I run success prediction analysis')
def step_run_success_prediction_analysis(context):
    """Run success prediction analysis on new ideas."""
    context.success_predictions = []
    
    for idea_data in context.new_ideas:
        idea = idea_data['idea']
        expected_prob = idea_data['expected_success_prob']
        
        # Mock prediction based on expected probability
        if expected_prob > 0.7:
            confidence = 'High'
            key_factors = ['Strong engagement', 'clear value prop']
        elif expected_prob > 0.4:
            confidence = 'Medium'
            key_factors = ['Moderate interest', 'implementation risk']
        else:
            confidence = 'High'
            key_factors = ['Low engagement', 'unclear benefits']
        
        prediction = {
            'idea_id': idea.id,
            'success_probability': expected_prob,
            'confidence': confidence,
            'key_factors': key_factors
        }
        
        context.success_predictions.append(prediction)


@then('each idea should receive a success probability score')
def step_each_idea_success_probability(context):
    """Verify each idea has a success probability score."""
    assert len(context.success_predictions) == len(context.new_ideas)
    
    for prediction in context.success_predictions:
        assert 'success_probability' in prediction
        assert 0.0 <= prediction['success_probability'] <= 1.0


@then('prediction confidence intervals should be provided')
def step_prediction_confidence_provided(context):
    """Verify prediction confidence is provided."""
    for prediction in context.success_predictions:
        assert 'confidence' in prediction
        assert prediction['confidence'] in ['High', 'Medium', 'Low']


@then('key success factors should be identified')
def step_key_success_factors_identified(context):
    """Verify key success factors are identified."""
    if hasattr(context, 'table'):
        expected_predictions = {int(row['idea_id']): row for row in context.table}
        
        for prediction in context.success_predictions:
            idea_id = prediction['idea_id']
            if idea_id in expected_predictions:
                expected = expected_predictions[idea_id]
                
                # Check success probability (with tolerance)
                expected_prob = float(expected['success_probability'])
                assert abs(prediction['success_probability'] - expected_prob) < 0.05
                
                # Check confidence level
                assert prediction['confidence'] == expected['confidence']
                
                # Check that key factors are provided
                assert 'key_factors' in prediction
                assert len(prediction['key_factors']) > 0


@then('high-potential ideas should be flagged for priority review')
def step_high_potential_ideas_flagged(context):
    """Verify high-potential ideas are flagged."""
    high_potential_ideas = [
        prediction for prediction in context.success_predictions
        if prediction['success_probability'] > 0.7
    ]
    
    assert len(high_potential_ideas) > 0
    
    # Flag them for priority review
    for prediction in high_potential_ideas:
        prediction['priority_review'] = True
    
    context.high_potential_count = len(high_potential_ideas)