from fastapi import APIRouter, HTTPException, status

from app.services.health import database_is_ready

router = APIRouter()


@router.get("/health")
async def health():
    if not await database_is_ready():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Serviço indisponível")
    return {"status": "ok", "database": "ok"}
