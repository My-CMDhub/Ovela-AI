"""
Evaluation Runs API
===================
Serves persisted multi-agent evaluation run history from Appwrite.

Routes:
- GET /evaluations  - Paginated list sorted by timestamp DESC
"""

import logging
from fastapi import APIRouter, Depends, Query
import httpx

from core.auth import get_current_tenant_id
from core.config import settings
from appwrite.query import Query as AppwriteQuery

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evaluations"])

MOTEL_DB_ID = "6947b8300005f5863f96"
APPWRITE_ENDPOINT = settings.APPWRITE_ENDPOINT
APPWRITE_PROJECT_ID = settings.APPWRITE_PROJECT_ID
APPWRITE_API_KEY = settings.APPWRITE_API_KEY


# Whose runs these are. evaluation_runs docs carry no tenant_id: they are written
# by tests/run_multi_agent_evaluation.py, which only ever drives the Coal Creek
# agent (tenant "coalcreek", its prompt, its tools). So that tenant sees them and
# every other tenant sees an empty history, decided here rather than by an
# Appwrite query on an attribute the collection does not have. If runs ever get
# a tenant_id, filter on it in the query instead.
EVALUATION_TENANT_ID = "coalcreek"


def _appwrite_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "X-Appwrite-Project": APPWRITE_PROJECT_ID,
        "X-Appwrite-Key": APPWRITE_API_KEY,
    }


async def _appwrite_get(endpoint: str, queries: list = None) -> dict:
    url = f"{APPWRITE_ENDPOINT}{endpoint}"
    params: dict = {}
    if queries:
        for i, q in enumerate(queries):
            params[f"queries[{i}]"] = str(q)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=_appwrite_headers(), params=params)
            if response.status_code == 200:
                return response.json()
            logger.error(f"Appwrite GET error {response.status_code}: {response.text[:200]}")
            return {"error": f"Appwrite {response.status_code}"}
    except Exception as exc:
        logger.error(f"Appwrite GET failed: {exc}")
        return {"error": str(exc)}


@router.get("/evaluations")
async def get_evaluation_runs(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """
    Return paginated evaluation run history from `evaluation_runs` collection,
    sorted by timestamp DESC.

    Needs a signed-in user (Appwrite JWT): the runs are internal QA data (scores,
    per-scenario results and agent routing traces) and were readable by anyone.
    The evaluations page already sends the JWT through fetchWithAuth.
    """
    if tenant_id != EVALUATION_TENANT_ID:
        return {"success": True, "runs": [], "total": 0}
    try:
        endpoint = f"/databases/{MOTEL_DB_ID}/collections/evaluation_runs/documents"
        queries = [
            AppwriteQuery.order_desc("timestamp"),
            AppwriteQuery.limit(limit),
            AppwriteQuery.offset(offset),
        ]
        result = await _appwrite_get(endpoint, queries)

        if "error" in result:
            return {"success": False, "error": result["error"], "runs": [], "total": 0}

        documents = result.get("documents", [])

        runs = []
        for doc in documents:
            runs.append({
                "id": doc.get("$id"),
                "run_id": doc.get("run_id"),
                "timestamp": doc.get("timestamp"),
                "strategy": doc.get("strategy"),
                "noise_level": doc.get("noise_level"),
                "scenario_count": doc.get("scenario_count"),
                "baseline_avg": doc.get("baseline_avg"),
                "upgraded_avg": doc.get("upgraded_avg"),
                "delta": doc.get("delta"),
                "pass_rate": doc.get("pass_rate"),
                "notes": doc.get("notes"),
                # Full per-scenario detail for Tier 2 (matrix table) and Tier 3 (trace accordion)
                "scenarios_json": doc.get("scenarios_json"),
            })

        return {
            "success": True,
            "runs": runs,
            "total": result.get("total", len(runs)),
        }

    except Exception as exc:
        logger.error(f"Error fetching evaluation runs: {exc}")
        return {"success": False, "error": str(exc), "runs": [], "total": 0}
