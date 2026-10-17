"""CampusCare Hostel Issue Tracker API + Dynamic OpenAPI Spec Generator.
Demo service providing realistic hostel complaints and OpenAPI 3.0.3 specs.
"""

import copy
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# In-Memory Database
# ---------------------------------------------------------------------------
INITIAL_ISSUES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "room": "302",
        "category": "Internet",
        "priority": "High",
        "description": "Wi-Fi router dead since morning",
        "status": "Open",
        "warden_note": "",
    },
    {
        "id": 2,
        "room": "Block-B Mess",
        "category": "Plumbing",
        "priority": "Medium",
        "description": "Water cooler leaking near dining hall",
        "status": "Open",
        "warden_note": "",
    },
    {
        "id": 3,
        "room": "104",
        "category": "Electrical",
        "priority": "Low",
        "description": "Ceiling fan regulator broken",
        "status": "Resolved",
        "warden_note": "Replaced capacitor",
    },
]

ISSUES_DB: List[Dict[str, Any]] = [dict(issue) for issue in INITIAL_ISSUES]


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------
class CreateIssueRequest(BaseModel):
    room: str = Field(..., description="Hostel room number or location", example="302")
    category: str = Field(..., description="Issue category (Internet, Plumbing, Electrical, General)", example="Internet")
    priority: str = Field(..., description="Priority level (Low, Medium, High)", example="High")
    description: str = Field(..., description="Detailed description of the complaint", example="Wi-Fi router dead since morning")


class ResolveIssueRequest(BaseModel):
    warden_note: str = Field("", description="Action taken by hostel warden/technician", example="Replaced capacitor")


# ---------------------------------------------------------------------------
# Authentication Helpers & Dependencies
# ---------------------------------------------------------------------------
def verify_token(authorization: Optional[str] = Header(None), required: bool = True) -> Optional[str]:
    expected = os.environ.get("DEMO_API_KEY", "hostel-secret-123")
    if not authorization:
        if required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Missing Authorization header (expected Bearer token)",
            )
        return None

    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid API key",
        )
    return token


def optional_auth(authorization: Optional[str] = Header(None)) -> Optional[str]:
    return verify_token(authorization, required=False)


def required_auth(authorization: Optional[str] = Header(None)) -> Optional[str]:
    return verify_token(authorization, required=True)


# ---------------------------------------------------------------------------
# APIRouter & Demo Endpoints
# ---------------------------------------------------------------------------
router = APIRouter(tags=["CampusCare Demo API"])


@router.get("/api/issues", operation_id="list_hostel_issues", summary="List Hostel Issues")
def list_hostel_issues(
    status: Optional[str] = None,
    auth_token: Optional[str] = Depends(optional_auth),
):
    """Retrieve all hostel complaints, optionally filtered by status ('Open', 'Resolved')."""
    if status:
        filtered = [i for i in ISSUES_DB if i.get("status", "").lower() == status.lower()]
        return filtered
    return [dict(i) for i in ISSUES_DB]


@router.post("/api/issues", operation_id="report_hostel_issue", status_code=status.HTTP_201_CREATED, summary="Report Hostel Issue")
def report_hostel_issue(
    issue_data: CreateIssueRequest,
    auth_token: Optional[str] = Depends(required_auth),
):
    """Report a new hostel maintenance issue or student complaint."""
    new_id = max([i["id"] for i in ISSUES_DB], default=0) + 1
    new_issue = {
        "id": new_id,
        "room": issue_data.room,
        "category": issue_data.category,
        "priority": issue_data.priority,
        "description": issue_data.description,
        "status": "Open",
        "warden_note": "",
    }
    ISSUES_DB.append(new_issue)
    return new_issue


@router.delete("/api/issues/{issue_id}", operation_id="delete_hostel_issue", summary="Delete Hostel Issue")
def delete_hostel_issue(
    issue_id: int,
    auth_token: Optional[str] = Depends(required_auth),
):
    """Remove a hostel issue by its unique numeric ID."""
    for idx, item in enumerate(ISSUES_DB):
        if item["id"] == issue_id:
            deleted = ISSUES_DB.pop(idx)
            return {"success": True, "deleted_id": issue_id, "deleted_item": deleted}
    raise HTTPException(status_code=404, detail=f"Hostel issue with ID {issue_id} not found")


@router.patch("/api/issues/{issue_id}/resolve", operation_id="resolve_hostel_issue", summary="Resolve Hostel Issue")
def resolve_hostel_issue(
    issue_id: int,
    resolve_data: ResolveIssueRequest,
    auth_token: Optional[str] = Depends(required_auth),
):
    """Mark a hostel issue as Resolved with warden notes."""
    for item in ISSUES_DB:
        if item["id"] == issue_id:
            item["status"] = "Resolved"
            item["warden_note"] = resolve_data.warden_note
            return item
    raise HTTPException(status_code=404, detail=f"Hostel issue with ID {issue_id} not found")


@router.post("/api/reset", summary="Reset Issues Database")
def reset_issues_db():
    """Reset the in-memory database to the original 3 sample hostel issues."""
    global ISSUES_DB
    ISSUES_DB = [dict(i) for i in INITIAL_ISSUES]
    return {"status": "reset", "count": len(ISSUES_DB)}


# ---------------------------------------------------------------------------
# OpenAPI 3.0.3 Spec Templates
# ---------------------------------------------------------------------------
def _build_base_spec() -> Dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "CampusCare Hostel Issue Tracker API",
            "version": "1.0.0",
            "description": "Hostel complaint and maintenance management API for student residents and hostel wardens.",
        },
        "servers": [{"url": "http://localhost:8000"}],
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Hostel warden or admin API key",
                }
            },
            "schemas": {
                "HostelIssue": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "Unique identifier of the issue"},
                        "room": {"type": "string", "description": "Room number or hostel block location"},
                        "category": {"type": "string", "description": "Category: Internet, Plumbing, Electrical, General"},
                        "priority": {"type": "string", "description": "Priority: Low, Medium, High"},
                        "description": {"type": "string", "description": "Detailed explanation of the issue"},
                        "status": {"type": "string", "description": "Status: Open or Resolved"},
                        "warden_note": {"type": "string", "description": "Notes from the warden or technician"},
                    },
                    "required": ["id", "room", "category", "priority", "description", "status"],
                },
                "CreateIssueRequest": {
                    "type": "object",
                    "properties": {
                        "room": {"type": "string", "description": "Room number or hostel location"},
                        "category": {"type": "string", "description": "Category: Internet, Plumbing, Electrical, General"},
                        "priority": {"type": "string", "description": "Priority: Low, Medium, High"},
                        "description": {"type": "string", "description": "Detailed description of the issue"},
                    },
                    "required": ["room", "category", "priority", "description"],
                },
                "ResolveIssueRequest": {
                    "type": "object",
                    "properties": {
                        "warden_note": {"type": "string", "description": "Technician or warden resolution note"},
                    },
                    "required": ["warden_note"],
                },
            },
        },
        "paths": {
            "/api/issues": {
                "get": {
                    "operationId": "list_hostel_issues",
                    "summary": "List all hostel issues",
                    "description": "Get a list of all hostel complaints. Optionally filter by status ('Open' or 'Resolved').",
                    "parameters": [
                        {
                            "name": "status",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Filter issues by status: 'Open' or 'Resolved'",
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of hostel complaints",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/HostelIssue"},
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "operationId": "report_hostel_issue",
                    "summary": "Report a new hostel issue",
                    "description": "Submit a new hostel complaint with room number, category, priority, and description.",
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CreateIssueRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Issue successfully created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/HostelIssue"}
                                }
                            },
                        }
                    },
                },
            },
            "/api/issues/{issue_id}": {
                "delete": {
                    "operationId": "delete_hostel_issue",
                    "summary": "Delete a hostel issue",
                    "description": "Delete a hostel complaint by its unique numeric issue ID.",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "issue_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                            "description": "Numeric ID of the issue to delete",
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Issue deleted successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "deleted_id": {"type": "integer"},
                                        },
                                    }
                                }
                            },
                        },
                        "404": {"description": "Issue not found"},
                    },
                }
            },
        },
    }


def get_spec(version: str) -> Dict[str, Any]:
    """Return OpenAPI 3.0.3 specification dict for the specified version."""
    version = version.lower().strip()

    if version == "v1":
        # 3 endpoints: GET, POST, DELETE (omitting resolve)
        return _build_base_spec()

    elif version == "v2":
        # Full spec with all 4 endpoints (including resolve)
        spec = _build_base_spec()
        spec["info"]["version"] = "2.0.0"
        spec["paths"]["/api/issues/{issue_id}/resolve"] = {
            "patch": {
                "operationId": "resolve_hostel_issue",
                "summary": "Resolve hostel issue",
                "description": "Mark a hostel complaint as Resolved and record the warden's repair note.",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    {
                        "name": "issue_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "description": "Numeric ID of the issue to resolve",
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ResolveIssueRequest"}
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Updated hostel issue",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HostelIssue"}
                            }
                        },
                    },
                    "404": {"description": "Issue not found"},
                },
            }
        }
        return spec

    elif version == "messy":
        # Copy of v2 but with operationId stripped and cryptic descriptions
        spec = copy.deepcopy(get_spec("v2"))
        spec["info"]["title"] = "hostel_crud_internal"
        spec["info"]["description"] = "raw dump"
        for path_val in spec.get("paths", {}).values():
            for method_val in path_val.values():
                if isinstance(method_val, dict):
                    method_val.pop("operationId", None)
                    method_val["summary"] = "endpoint action"
                    method_val["description"] = "processes the hostel thing"
        return spec

    elif version == "external":
        # JSONPlaceholder external API spec
        return {
            "openapi": "3.0.3",
            "info": {
                "title": "JSONPlaceholder API",
                "version": "1.0.0",
                "description": "Fake online REST API for testing and prototyping.",
            },
            "servers": [{"url": "https://jsonplaceholder.typicode.com"}],
            "paths": {
                "/posts": {
                    "get": {
                        "operationId": "list_posts",
                        "summary": "Get list of posts",
                        "description": "Retrieve all public posts from JSONPlaceholder.",
                        "parameters": [
                            {
                                "name": "userId",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer"},
                                "description": "Filter posts by author user ID",
                            }
                        ],
                        "responses": {"200": {"description": "Array of posts"}},
                    },
                    "post": {
                        "operationId": "create_post",
                        "summary": "Create new post",
                        "description": "Submit a new blog post.",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "body": {"type": "string"},
                                            "userId": {"type": "integer"},
                                        },
                                        "required": ["title", "body", "userId"],
                                    }
                                }
                            },
                        },
                        "responses": {"201": {"description": "Created post"}},
                    },
                },
                "/posts/{id}": {
                    "get": {
                        "operationId": "get_post_by_id",
                        "summary": "Get post details",
                        "description": "Fetch a specific post by its ID.",
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer"},
                                "description": "Unique post ID",
                            }
                        ],
                        "responses": {"200": {"description": "Post details"}},
                    },
                    "delete": {
                        "operationId": "delete_post",
                        "summary": "Delete post",
                        "description": "Remove a post by ID.",
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer"},
                                "description": "Post ID to remove",
                            }
                        ],
                        "responses": {"200": {"description": "Post deleted"}},
                    },
                },
            },
        }

    else:
        raise HTTPException(status_code=404, detail=f"Spec version '{version}' not found. Available: v1, v2, messy, external.")


@router.get("/specs/{version}", summary="Get OpenAPI Specification Preset")
def get_spec_endpoint(version: str):
    """Retrieve OpenAPI 3.0.3 specification by preset name ('v1', 'v2', 'messy', 'external')."""
    return get_spec(version)
