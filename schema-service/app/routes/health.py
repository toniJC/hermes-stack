"""Health check endpoint."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", status_code=200)
async def healthz() -> dict:
    """Return service liveness status."""
    return {"status": "ok"}
