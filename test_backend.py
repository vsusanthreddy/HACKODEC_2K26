"""Comprehensive verification test suite for Anything-to-MCP Studio backend.
"""

import os
import py_compile
import sys
from fastapi.testclient import TestClient

def run_tests():
    print("=== STARTING BACKEND VERIFICATION ===")

    # 1. Test Demo API & Specs
    from backend.demo_api import get_spec, ISSUES_DB, INITIAL_ISSUES, router
    from backend.main import app

    client = TestClient(app)

    print("\n--- Testing Specs ---")
    spec_v1 = get_spec("v1")
    assert len(spec_v1["paths"]) == 2, f"Expected 2 path keys in v1, got {len(spec_v1['paths'])}"
    assert "/api/issues" in spec_v1["paths"]
    assert "/api/issues/{issue_id}" in spec_v1["paths"]
    assert "get" in spec_v1["paths"]["/api/issues"]
    assert "post" in spec_v1["paths"]["/api/issues"]
    assert "delete" in spec_v1["paths"]["/api/issues/{issue_id}"]
    print("[PASS] Spec v1 structure verified (3 endpoints, resolve omitted)")

    spec_v2 = get_spec("v2")
    assert len(spec_v2["paths"]) == 3, f"Expected 3 path keys in v2, got {len(spec_v2['paths'])}"
    assert "/api/issues/{issue_id}/resolve" in spec_v2["paths"]
    assert "patch" in spec_v2["paths"]["/api/issues/{issue_id}/resolve"]
    print("[PASS] Spec v2 structure verified (all 4 endpoints including resolve)")

    spec_messy = get_spec("messy")
    for p, methods in spec_messy["paths"].items():
        for m, op in methods.items():
            assert "operationId" not in op, f"Found unexpected operationId in messy spec for {m} {p}"
    print("[PASS] Spec messy structure verified (no operationId)")

    spec_ext = get_spec("external")
    assert "jsonplaceholder" in spec_ext["servers"][0]["url"]
    print("[PASS] Spec external structure verified (JSONPlaceholder)")

    print("\n--- Testing Demo API Endpoints & Auth ---")
    # Reset
    r_reset = client.post("/api/reset")
    assert r_reset.status_code == 200 and r_reset.json()["count"] == 3
    print("[PASS] POST /api/reset works")

    # GET /api/issues with no token -> 200
    r_list = client.get("/api/issues")
    assert r_list.status_code == 200 and len(r_list.json()) == 3
    print("[PASS] GET /api/issues (no token) -> 200 OK")

    # GET /api/issues with valid token -> 200
    r_list_auth = client.get("/api/issues", headers={"Authorization": "Bearer hostel-secret-123"})
    assert r_list_auth.status_code == 200
    print("[PASS] GET /api/issues (valid Bearer token) -> 200 OK")

    # GET /api/issues with invalid token -> 401
    r_list_bad = client.get("/api/issues", headers={"Authorization": "Bearer bad-token"})
    assert r_list_bad.status_code == 401
    print("[PASS] GET /api/issues (invalid token) -> 401 Unauthorized")

    # POST /api/issues with no token -> 401
    r_post_unauth = client.post("/api/issues", json={"room": "401", "category": "Plumbing", "priority": "High", "description": "Pipe broken"})
    assert r_post_unauth.status_code == 401
    print("[PASS] POST /api/issues (no token) -> 401 Unauthorized")

    # POST /api/issues with valid token -> 201
    r_post = client.post(
        "/api/issues",
        json={"room": "401", "category": "Plumbing", "priority": "High", "description": "Pipe broken"},
        headers={"Authorization": "Bearer hostel-secret-123"},
    )
    assert r_post.status_code == 201
    created_id = r_post.json()["id"]
    assert created_id == 4
    print(f"[PASS] POST /api/issues (valid token) -> 201 Created (ID {created_id})")

    # PATCH /api/issues/{id}/resolve with valid token -> 200
    r_patch = client.patch(
        f"/api/issues/{created_id}/resolve",
        json={"warden_note": "Pipe fixed by plumber"},
        headers={"Authorization": "Bearer hostel-secret-123"},
    )
    assert r_patch.status_code == 200 and r_patch.json()["status"] == "Resolved"
    print(f"[PASS] PATCH /api/issues/{created_id}/resolve -> 200 Resolved")

    # DELETE /api/issues/{id} with valid token -> 200
    r_del = client.delete(
        f"/api/issues/{created_id}",
        headers={"Authorization": "Bearer hostel-secret-123"},
    )
    assert r_del.status_code == 200 and r_del.json()["success"] is True
    print(f"[PASS] DELETE /api/issues/{created_id} -> 200 OK")

    # Reset again for clean state
    client.post("/api/reset")

    print("\n--- Testing Generator (OpenAPI-to-FastMCP Compiler) ---")
    from backend.generator import generate_mcp_code

    # Spec v1, read_only=False
    gen_v1 = generate_mcp_code(spec=spec_v1, read_only=False)
    assert gen_v1["stats"]["generated_tools"] == 3, f"Expected 3 tools, got {gen_v1['stats']['generated_tools']}"
    assert gen_v1["stats"]["skipped_count"] == 0
    print(f"[PASS] Generator Spec v1 (read_only=False): 3 tools generated ({', '.join(t['name'] for t in gen_v1['tools'])})")

    # Spec v1, read_only=True
    gen_v1_ro = generate_mcp_code(spec=spec_v1, read_only=True)
    assert gen_v1_ro["stats"]["generated_tools"] == 1, f"Expected 1 tool, got {gen_v1_ro['stats']['generated_tools']}"
    assert gen_v1_ro["stats"]["skipped_count"] == 2
    assert gen_v1_ro["tools"][0]["name"] == "list_hostel_issues"
    print(f"[PASS] Generator Spec v1 (read_only=True): 1 tool generated (non-GET methods filtered)")

    # Spec v2, read_only=False
    gen_v2 = generate_mcp_code(spec=spec_v2, read_only=False)
    assert gen_v2["stats"]["generated_tools"] == 4, f"Expected 4 tools, got {gen_v2['stats']['generated_tools']}"
    print(f"[PASS] Generator Spec v2 (read_only=False): 4 tools generated ({', '.join(t['name'] for t in gen_v2['tools'])})")

    # Test compilation of generated_mcp_server.py
    server_path = os.path.join(os.path.dirname(__file__), "backend", "generated_mcp_server.py")
    py_compile.compile(server_path, doraise=True)
    print(f"[PASS] py_compile passed for {server_path}")

    print("\n--- Testing Agent Runner (AI Warden + Fallback) ---")
    from backend.agent_runner import run_agent_task

    # 1. List issues
    agent_res_list = run_agent_task(user_prompt="List all open hostel complaints", api_token="hostel-secret-123")
    assert len(agent_res_list["tool_calls"]) > 0
    assert agent_res_list["mode"] in {"fallback", "gemini"}
    print(f"[PASS] Agent Runner (list): mode={agent_res_list['mode']}, tool={agent_res_list['tool_calls'][0]['name']}")

    # 2. Resolve issue
    agent_res_res = run_agent_task(user_prompt="Resolve issue 1 with note: Wi-Fi router rebooted and firmware updated", api_token="hostel-secret-123")
    assert len(agent_res_res["tool_calls"]) > 0
    assert "resolve" in agent_res_res["tool_calls"][0]["name"]
    print(f"[PASS] Agent Runner (resolve): mode={agent_res_res['mode']}, tool={agent_res_res['tool_calls'][0]['name']}")

    print("\n--- Testing Studio Endpoints ---")
    # GET /health
    r_health = client.get("/health")
    assert r_health.status_code == 200 and r_health.json()["status"] == "ok"
    print("[PASS] GET /health -> 200 OK")

    # POST /studio/generate
    r_gen = client.post("/studio/generate", json={"preset": "v2", "read_only": False})
    assert r_gen.status_code == 200 and r_gen.json()["stats"]["generated_tools"] == 4
    print("[PASS] POST /studio/generate -> 200 OK (4 tools compiled)")

    # POST /studio/agent
    r_agent = client.post("/studio/agent", json={"prompt": "Show me all unresolved issues"})
    assert r_agent.status_code == 200 and len(r_agent.json()["tool_calls"]) > 0
    print("[PASS] POST /studio/agent -> 200 OK")

    # GET /studio/current-server
    r_curr = client.get("/studio/current-server")
    assert r_curr.status_code == 200 and len(r_curr.json()["tools"]) == 4
    print("[PASS] GET /studio/current-server -> 200 OK (4 tools active)")

    print("\n=== ALL TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_tests()
