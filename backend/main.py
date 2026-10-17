"""Unified FastAPI Server for Anything-to-MCP Studio.
Mounts CampusCare Demo API, Studio Code Generator, and AI Agent Runner.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from backend.agent_runner import run_agent_task
from backend.demo_api import get_spec, router as demo_router
from backend.generator import generate_mcp_code

# ---------------------------------------------------------------------------
# FastAPI Application & CORS Configuration
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Anything-to-MCP Studio API",
    version="1.0.0",
    description="Studio backend compiling OpenAPI specs into FastMCP servers and executing AI Warden tasks.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the Demo API router (provides /api/issues, /specs/{version}, etc.)
app.include_router(demo_router)


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------
class GenerateRequest(BaseModel):
    spec: Optional[Dict[str, Any]] = Field(None, description="Raw OpenAPI 3.x specification dictionary")
    preset: Optional[str] = Field(None, description="Built-in preset name: 'v1', 'v2', 'messy', 'external'", example="v1")
    read_only: bool = Field(False, description="Filter out all mutating methods (POST/PUT/DELETE/PATCH)")
    api_base_url: Optional[str] = Field(None, description="Override target API base URL", example="http://localhost:8000")
    heal_with_ai: bool = Field(False, description="Use Gemini 2.5 Flash to heal missing or messy operationIds and descriptions")
    gemini_key: Optional[str] = Field(None, description="Optional Google GenAI Gemini API key for healing or agent execution")
    selected_endpoints: Optional[List[str]] = Field(None, description="Selective list of endpoints to compile (e.g. ['GET /api/issues'])")


class AgentRequest(BaseModel):
    prompt: str = Field(..., description="User prompt or instruction for the AI Warden agent", example="List all open hostel complaints")
    api_token: Optional[str] = Field("hostel-secret-123", description="Bearer token for CampusCare authentication")
    gemini_key: Optional[str] = Field(None, description="Optional Gemini API key (uses fallback matcher if omitted)")
    api_base_url: Optional[str] = Field(None, description="Base URL of the target API")


# ---------------------------------------------------------------------------
# Studio Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", summary="Health Check")
def health_check():
    """Verify backend service liveness."""
    return {
        "status": "ok",
        "service": "Anything-to-MCP Studio",
        "version": "1.0.0",
    }


@app.post("/studio/generate", summary="Compile OpenAPI Spec to FastMCP Server")
def studio_generate(req: GenerateRequest):
    """Compile an OpenAPI specification into a standalone Python FastMCP server."""
    # Determine which spec to compile
    if req.spec:
        target_spec = req.spec
    elif req.preset:
        target_spec = get_spec(req.preset)
    else:
        target_spec = get_spec("v1")

    gemini_api_key = req.gemini_key or os.environ.get("GEMINI_API_KEY", "")

    result = generate_mcp_code(
        spec=target_spec,
        read_only=req.read_only,
        api_base_url=req.api_base_url or "",
        heal_with_ai=req.heal_with_ai,
        gemini_key=gemini_api_key,
        selected_endpoints=req.selected_endpoints,
    )
    return result


@app.post("/studio/agent", summary="Execute AI Warden Agent Task")
def studio_agent(req: AgentRequest):
    """Run an agent instruction against the currently compiled FastMCP server tools."""
    gemini_api_key = req.gemini_key or os.environ.get("GEMINI_API_KEY", "")
    token = req.api_token or os.environ.get("DEMO_API_KEY", "hostel-secret-123")

    result = run_agent_task(
        user_prompt=req.prompt,
        api_token=token,
        gemini_key=gemini_api_key,
        api_base_url=req.api_base_url or "",
    )
    return result


@app.get("/studio/current-server", summary="Get Currently Generated MCP Server")
def studio_current_server():
    """Return the code and metadata of the active generated MCP server."""
    possible_paths = [
        Path(__file__).parent / "generated_mcp_server.py",
        Path(r"C:\Users\vjcha\OneDrive\SUSANTH\anything-to-mcp-studio\backend\generated_mcp_server.py"),
        Path(r"C:\Users\vjcha\.gemini\antigravity\scratch\backend\generated_mcp_server.py"),
    ]

    target_path = None
    for p in possible_paths:
        if p.exists():
            target_path = p
            break

    # If file does not exist, auto-generate default v1 spec
    if not target_path or not target_path.exists():
        spec_v1 = get_spec("v1")
        gen_res = generate_mcp_code(spec=spec_v1, read_only=False)
        return {
            "status": "ready",
            "code": gen_res["code"],
            "tools": gen_res["tools"],
            "stats": gen_res["stats"],
            "file_path": str(possible_paths[0]),
        }

    code_content = target_path.read_text(encoding="utf-8")

    # Extract TOOLS_REGISTRY if present
    tools = []
    try:
        from backend.agent_runner import load_generated_mcp_module

        mod = load_generated_mcp_module()
        tools = getattr(mod, "TOOLS_REGISTRY", [])
    except Exception:
        pass

    return {
        "status": "ready",
        "code": code_content,
        "tools": tools,
        "file_path": str(target_path),
    }


# ---------------------------------------------------------------------------
# Server Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
