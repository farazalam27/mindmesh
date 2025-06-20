"""Main FastAPI application for Decision service."""
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
    logger.info("Starting Decision service...")
    try:
        # Initialize database
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Decision service...")


# Create FastAPI app
app = FastAPI(
    title="Decision Service",
    description="Microservice for managing decisions and event sourcing in MindMesh platform",
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


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return JSONResponse(
        status_code=403,
        content={"detail": "Insufficient permissions"}
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Test database connection
    db_healthy = True
    try:
        from .api import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
    except:
        db_healthy = False
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "service": "decision",
        "version": "1.0.0",
        "dependencies": {
            "database": "healthy" if db_healthy else "unhealthy"
        }
    }


# Include routers
app.include_router(router)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8004))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV", "development") == "development",
        log_level="info"
    )