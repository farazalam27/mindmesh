"""Main FastAPI application for Voting service."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import uvicorn
from contextlib import asynccontextmanager
import os

from .api import router
from .models import Base
from .api import engine
from .redis_client import redis_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifecycle events."""
    # Startup
    logger.info("Starting Voting service...")
    try:
        # Initialize database
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
        
        # Test Redis connection
        redis_client.client.ping()
        logger.info("Redis connection verified")
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Voting service...")
    redis_client.close()


# Create FastAPI app
app = FastAPI(
    title="Voting Service",
    description="Microservice for managing votes and ratings in MindMesh platform",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded", "error": str(exc.detail)},
        headers=getattr(exc, "headers", {})
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check Redis
    redis_healthy = True
    try:
        redis_client.client.ping()
    except:
        redis_healthy = False
    
    return {
        "status": "healthy" if redis_healthy else "degraded",
        "service": "voting",
        "version": "1.0.0",
        "dependencies": {
            "redis": "healthy" if redis_healthy else "unhealthy",
            "database": "healthy"  # Add actual DB check if needed
        }
    }


# Include routers
app.include_router(router)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8002))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV", "development") == "development",
        log_level="info"
    )