"""
Vercel Diagnostic Handler
Captures import errors and exposes them via API
"""
import sys
import os
import traceback

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Try importing the real app
    from src.main import app
except Exception as e:
    # If it fails, create a fallback app that reports the error
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI(title="PolyWrite Diagnostic Mode")
    
    error_trace = traceback.format_exc()
    
    @app.get("/{catchall:path}")
    async def catch_all(catchall: str):
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Failed to load application",
                "error": str(e),
                "traceback": error_trace.split('\n')
            }
        )
