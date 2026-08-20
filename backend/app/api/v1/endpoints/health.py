from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db.session import AsyncSessionLocal

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/live")
async def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível") from exc
    return {"status": "ready", "database": "ok"}
