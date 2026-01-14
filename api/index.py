"""
Vercel Serverless Function Entry Point
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create a minimal app for Vercel
app = FastAPI(title="PolyWrite API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "service": "PolyWrite API",
        "status": "healthy",
        "version": "2.0.0",
        "docs": "/docs",
        "frontend": "/app"
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

# Try to import full app, fallback to minimal if dependencies fail
try:
    from src.routes import auth_router, rewrite_router
    app.include_router(auth_router)
    app.include_router(rewrite_router)
except Exception as e:
    @app.get("/error")
    async def show_error():
        return {"error": str(e), "message": "Some features unavailable"}
