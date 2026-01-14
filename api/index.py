from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import sys
import os
import traceback

# Create specific Vercel app
app = FastAPI(title="PolyWrite Vercel Entrypoint")

@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "Vercel entrypoint is active"}

@app.get("/api/debug")
async def debug_info():
    """
    Validation endpoint to check environment and imports
    """
    debug_data = {
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "path": sys.path,
        "env_vars": [k for k in os.environ.keys()], # We list keys only
        "directory_listing": []
    }
    
    try:
        debug_data["directory_listing"] = os.listdir(".")
    except Exception as e:
        debug_data["directory_listing_error"] = str(e)
        
    return debug_data

@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def catch_all(path_name: str, request: Request):
    """
    Proxy all other requests to the main app, loading it dynamically
    """
    try:
        # Add root to sys.path if needed
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
            
        # Import main app dynamically
        from src.main import app as main_app
        
        # NOTE: In a real Vercel environment, we can't easily proxy the request 
        # to another FastAPI instance inside a handler without complex ASGI checks.
        # But we CAN check if import works.
        
        return {
            "status": "loaded", 
            "message": "Main app loaded successfully but dynamic dispatch is limited in this debug mode.",
            "instructions": "Deployment is working! Use direct routes."
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Failed to load main application",
                "error": str(e),
                "traceback": traceback.format_exc().split('\n')
            }
        )
