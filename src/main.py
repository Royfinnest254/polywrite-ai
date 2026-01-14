"""
PolyWrite Backend - Main Application

A trust and semantic-governance layer for AI-assisted writing.

Run with: uvicorn src.main:app --reload
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .config import get_settings
from .routes import auth_router, rewrite_router


# Create FastAPI app
app = FastAPI(
    title="PolyWrite API",
    description="""
## PolyWrite Backend

A trust and semantic-governance layer for AI-assisted writing.

### Core Principles

1. **Identity**: Every action is tied to a user identity
2. **No Anonymous AI**: Anonymous users cannot access AI functionality
3. **Proposals Only**: AI NEVER overwrites content - it proposes changes
4. **Semantic Validation**: Meaning is validated before any edit is allowed
5. **Rate Limiting**: Per-user rate limits protect the system
6. **Auditability**: All AI interactions are logged

### Features

- Entity & invariant locking (numbers, dates, names)
- Contradiction & polarity flip detection
- Claim & fact detection with citation flagging
- Document-level intelligence scanning
- Voice & tone preservation
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


# CORS middleware (configure for your frontend origin in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(auth_router)
app.include_router(rewrite_router)


# Mount frontend static files (if directory exists)
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/app", StaticFiles(directory=frontend_path, html=True), name="frontend")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "PolyWrite API",
        "status": "healthy",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    settings = get_settings()
    return {
        "status": "healthy",
        "supabase_configured": bool(settings.supabase_url),
        "rate_limits": {
            "per_minute": settings.rate_limit_requests_per_minute,
            "per_day": settings.rate_limit_requests_per_day
        },
        "thresholds": {
            "safe": settings.threshold_safe,
            "risky": settings.threshold_risky
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the traceback to console/logs, but NOT to the client
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
