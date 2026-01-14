from fastapi import FastAPI
from fastapi.responses import JSONResponse
import sys
import os
import traceback
import importlib

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
        "env_vars": [k for k in os.environ.keys()], # Don't leak values
        "directory_listing": []
    }
    
    try:
        debug_data["directory_listing"] = os.listdir(".")
    except Exception as e:
        debug_data["directory_listing_error"] = str(e)
        
    return debug_data

@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def catch_all(path_name: str, request: Request): # type: ignore
    """
    Proxy all other requests to the main app, loading it dynamically
    """
    try:
        # Add root to sys.path if needed
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
            
        # Import main app dynamically
        # This prevents top-level import errors from crashing the whole function
        from src.main import app as main_app
        
        # We can't easily dispatch to another FastAPI app instance from within a handler
        # effectively in this simpler way without mounting check.
        # But we can try to mount it if it's not mounted.
        pass
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

    # If import succeeded, logic is tricky because we are already inside a request.
    # The better pattern for Vercel is to have the module level 'app' be the one Vercel uses.
    # so we must import at module level but wrap it in try/except.
    
    return {"error": "Dynamic loading implementation gap. Use /api/health to verify deployments first."}

# ATTEMPT MODULE LEVEL LOAD for standard usage
try:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from src.main import app as real_app
    # If successful, replacing 'app' entirely might work if Vercel loads 'app' from this module
    app = real_app
except Exception as e:
    # If failed, 'app' remains the debug app defined above
    print(f"Failed to load main app: {e}")
    # We add a startup event to log this to Vercel logs
    @app.on_event("startup")
    async def startup_event():
        print("Application failed to load. Running in diagnostic mode.")
        print(traceback.format_exc())

