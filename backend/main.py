"""FastAPI application entry point for Anything-to-MCP Studio backend.
"""

from fastapi import FastAPI

app = FastAPI(title="Anything-to-MCP Studio API")

@app.get("/health")
def health_check():
    return {"status": "ok"}
