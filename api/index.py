"""
Ultra-minimal Vercel handler for debugging
"""
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok", "message": "PolyWrite API is running"}

@app.get("/api")
async def api():
    return {"status": "ok"}
