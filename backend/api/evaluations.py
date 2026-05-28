"""
Evaluation Runs API
===================
Serves persisted multi-agent evaluation run history from Appwrite.

Routes:
- GET /evaluations  - Paginated list sorted by timestamp DESC
"""

import logging
from fastapi import APIRouter, Query
import httpx

from core.config import settings
from appwrite.query import Query as AppwriteQuery

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evaluations"])

MOTEL_DB_ID = "6947b8300005f5863f96"
APPWRITE_ENDPOINT = settings.APPWRITE_ENDPOINT
APPWRITE_PROJECT_ID = settings.APPWRITE_PROJECT_ID
APPWRITE_API_KEY = settings.APPWRITE_API_KEY


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
):
    """
    Return paginated evaluation run history from `evaluation_runs` collection,
    sorted by timestamp DESC.
    """
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
            })

        return {
            "success": True,
            "runs": runs,
            "total": result.get("total", len(runs)),
        }

    except Exception as exc:
        logger.error(f"Error fetching evaluation runs: {exc}")
        return {"success": False, "error": str(exc), "runs": [], "total": 0}
